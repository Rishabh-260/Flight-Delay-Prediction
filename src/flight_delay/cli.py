from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from flight_delay.config import ARTIFACT_DIR, DATABASE_URL, DATA_DIR, YEAR
from flight_delay.eda import summarize
from flight_delay.features import prepare_flights
from flight_delay.ingest import ingest_year
from flight_delay.model import train_and_evaluate


def _load_raw(year: int, database_url: str) -> pd.DataFrame:
    engine = create_engine(database_url)
    try:
        columns = "flight_date, reporting_airline, origin, dest, crs_dep_time, crs_arr_time, crs_elapsed_time, distance, arr_delay, cancelled, diverted"
        return pd.read_sql(text(f"SELECT {columns} FROM raw_bts_flights WHERE flight_date >= :start AND flight_date < :end ORDER BY flight_date"), engine, params={"start": f"{year}-01-01", "end": f"{year + 1}-01-01"})
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="BTS flight delay analytics pipeline")
    parser.add_argument("command", choices=["ingest", "eda", "train", "all"])
    parser.add_argument("--year", type=int, default=YEAR)
    parser.add_argument("--database-url", default=DATABASE_URL)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--artifacts-dir", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command in {"ingest", "all"}:
        count = ingest_year(args.year, args.data_dir, args.database_url)
        logging.info("Ingested %s source rows", count)
    if args.command in {"eda", "train", "all"}:
        raw = _load_raw(args.year, args.database_url)
        if args.command in {"eda", "all"}:
            paths = summarize(raw, args.artifacts_dir / "eda")
            logging.info("EDA outputs: %s", paths)
        if args.command in {"train", "all"}:
            prepared = prepare_flights(raw)
            metrics, importance = train_and_evaluate(prepared, args.artifacts_dir / "models")
            logging.info("Model comparison:\n%s", metrics.to_string(index=False))
            logging.info("Top factors:\n%s", importance.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
