from __future__ import annotations

import logging
import csv
import zipfile
from io import StringIO
from pathlib import Path

import pandas as pd
import psycopg
import requests

from flight_delay.config import BTS_FIELDS, DATA_DIR, DATABASE_URL, RAW_COLUMNS, YEAR

LOG = logging.getLogger(__name__)
BTS_PREZIP = "https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
TABLE = "raw_bts_flights"
REQUIRED_BTS_FIELDS = {"FlightDate", "Reporting_Airline", "Origin", "Dest", "CRSDepTime", "CRSArrTime", "ArrDelay", "Cancelled", "Diverted"}
DUPLICATE_KEY = ["flight_date", "reporting_airline", "flight_number", "origin", "dest", "crs_dep_time", "crs_arr_time"]
INTEGER_COLUMNS = ["flight_number", "crs_dep_time", "crs_arr_time", "dep_time", "wheels_off", "wheels_on", "arr_time"]


def download_month(year: int, month: int, data_dir: Path = DATA_DIR) -> Path:
    """Download and extract the official BTS monthly pre-zipped CSV."""
    data_dir.mkdir(parents=True, exist_ok=True)
    zip_path = data_dir / f"bts_on_time_{year}_{month:02d}.zip"
    csv_path = data_dir / f"bts_on_time_{year}_{month:02d}.csv"
    if csv_path.exists() and csv_path.stat().st_size:
        return csv_path
    url = BTS_PREZIP.format(year=year, month=month)
    response = requests.get(url, timeout=(30, 180), stream=True)
    response.raise_for_status()
    with zip_path.open("wb") as out:
        for part in response.iter_content(chunk_size=1024 * 1024):
            if part:
                out.write(part)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if not members:
                raise ValueError(f"No CSV found in BTS archive: {zip_path}")
            with archive.open(members[0]) as source, csv_path.open("wb") as dest:
                while part := source.read(1024 * 1024):
                    dest.write(part)
    except Exception:
        zip_path.unlink(missing_ok=True)
        raise
    return csv_path


def _read_month(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, usecols=lambda name: name in BTS_FIELDS, low_memory=False)
    missing = sorted(set(BTS_FIELDS) - set(frame.columns))
    absent_required = sorted(REQUIRED_BTS_FIELDS.intersection(missing))
    if absent_required:
        raise ValueError(f"BTS CSV is missing required fields: {absent_required}")
    # BTS occasionally omits wholly empty columns from a monthly CSV; provide them as nulls.
    for name in missing:
        frame[name] = pd.NA
    frame = frame[BTS_FIELDS].rename(columns={
        "FlightDate": "flight_date", "Reporting_Airline": "reporting_airline",
        "Flight_Number_Reporting_Airline": "flight_number", "Origin": "origin",
        "OriginCityName": "origin_city", "OriginState": "origin_state",
        "Dest": "dest", "DestCityName": "dest_city", "DestState": "dest_state",
        "CRSDepTime": "crs_dep_time", "CRSArrTime": "crs_arr_time",
        "CRSElapsedTime": "crs_elapsed_time", "Distance": "distance",
        "DepTime": "dep_time", "DepDelay": "dep_delay", "TaxiOut": "taxi_out",
        "WheelsOff": "wheels_off", "WheelsOn": "wheels_on", "TaxiIn": "taxi_in",
        "ArrTime": "arr_time", "ArrDelay": "arr_delay", "Cancelled": "cancelled",
        "CancellationCode": "cancellation_code", "Diverted": "diverted",
        "ActualElapsedTime": "actual_elapsed_time", "AirTime": "air_time",
        "CarrierDelay": "carrier_delay", "WeatherDelay": "weather_delay",
        "NASDelay": "nas_delay", "SecurityDelay": "security_delay",
        "LateAircraftDelay": "late_aircraft_delay",
    })
    frame["flight_date"] = pd.to_datetime(frame["flight_date"], errors="coerce").dt.date
    for column in RAW_COLUMNS:
        if column not in {"flight_date", "reporting_airline", "flight_number", "origin", "origin_city", "origin_state", "dest", "dest_city", "dest_state", "cancellation_code"}:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in INTEGER_COLUMNS:
        frame[column] = frame[column].round().astype("Int64")
    return frame[RAW_COLUMNS]


def deduplicate_month(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop exact scheduled-flight key duplicates within a monthly source extract."""
    return frame.drop_duplicates(subset=DUPLICATE_KEY, keep="last").reset_index(drop=True)


def ingest_year(year: int = YEAR, data_dir: Path = DATA_DIR, database_url: str = DATABASE_URL) -> int:
    """Load monthly BTS CSVs into PostgreSQL. Reruns replace that month's rows."""
    conninfo = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    total = 0
    with psycopg.connect(conninfo) as conn:
        for month in range(1, 13):
            path = download_month(year, month, data_dir)
            frame = deduplicate_month(_read_month(path))
            start = f"{year}-{month:02d}-01"
            end = f"{year + (month == 12)}-{(month % 12) + 1:02d}-01"
            columns = ", ".join(RAW_COLUMNS)
            copy_sql = f"COPY {TABLE} ({columns}) FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', NULL '\\N')"
            # One transaction per month makes retries safe while PostgreSQL COPY avoids
            # thousands of multi-row INSERT statements for the BTS-scale monthly extracts.
            with conn.transaction():
                with conn.cursor() as cursor:
                    cursor.execute(f"DELETE FROM {TABLE} WHERE flight_date >= %s AND flight_date < %s", (start, end))
                    with cursor.copy(copy_sql) as copy:
                        for offset in range(0, len(frame), 25_000):
                            chunk = frame.iloc[offset:offset + 25_000]
                            buffer = StringIO()
                            chunk.to_csv(buffer, sep="\t", index=False, header=False, na_rep=r"\N", quoting=csv.QUOTE_MINIMAL)
                            copy.write(buffer.getvalue())
            total += len(frame)
            LOG.info("Loaded %s flights for %d-%02d", len(frame), year, month)
    return total
