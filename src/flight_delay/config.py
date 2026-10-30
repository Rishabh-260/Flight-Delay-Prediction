from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)

YEAR = int(os.getenv("YEAR", "2025"))
DATA_DIR = Path(os.getenv("DATA_DIR", "data/raw"))
ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "artifacts"))
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://flight_user:flight_local_password@localhost:5432/flight_delay",
)

# Minimal BTS fields needed for the label, pre-departure prediction, and reporting.
BTS_FIELDS = [
    "FlightDate", "Reporting_Airline", "Flight_Number_Reporting_Airline",
    "Origin", "OriginCityName", "OriginState", "Dest", "DestCityName",
    "DestState", "CRSDepTime", "CRSArrTime", "CRSElapsedTime", "Distance",
    "DepTime", "DepDelay", "TaxiOut", "WheelsOff", "WheelsOn", "TaxiIn",
    "ArrTime", "ArrDelay", "Cancelled", "CancellationCode", "Diverted",
    "ActualElapsedTime", "AirTime", "CarrierDelay", "WeatherDelay",
    "NASDelay", "SecurityDelay", "LateAircraftDelay",
]

RAW_COLUMNS = [
    "flight_date", "reporting_airline", "flight_number", "origin",
    "origin_city", "origin_state", "dest", "dest_city", "dest_state",
    "crs_dep_time", "crs_arr_time", "crs_elapsed_time", "distance",
    "dep_time", "dep_delay", "taxi_out", "wheels_off", "wheels_on",
    "taxi_in", "arr_time", "arr_delay", "cancelled", "cancellation_code",
    "diverted", "actual_elapsed_time", "air_time", "carrier_delay",
    "weather_delay", "nas_delay", "security_delay", "late_aircraft_delay",
]
