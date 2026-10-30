import pandas as pd
import pytest

from flight_delay.ingest import _read_month, deduplicate_month


def test_bts_csv_parsing_and_duplicate_removal(tmp_path):
    path = tmp_path / "sample.csv"
    pd.DataFrame({
        "FlightDate": ["2025-01-01", "2025-01-01"],
        "Reporting_Airline": ["AA", "AA"],
        "Flight_Number_Reporting_Airline": [100, 100],
        "Origin": ["JFK", "JFK"], "Dest": ["LAX", "LAX"],
        "CRSDepTime": [800, 800], "CRSArrTime": [1100, 1100],
        "CRSElapsedTime": [300, 300], "Distance": [2475, 2475],
        "ArrDelay": [15, 15], "Cancelled": [0, 0], "Diverted": [0, 0],
    }).to_csv(path, index=False)
    parsed = _read_month(path)
    unique = deduplicate_month(parsed)
    assert len(parsed) == 2
    assert len(unique) == 1
    assert unique.iloc[0].flight_date == pd.Timestamp("2025-01-01").date()
    assert unique.iloc[0].arr_delay == 15


def test_bts_csv_requires_core_target_and_schedule_fields(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"FlightDate": ["2025-01-01"], "Origin": ["JFK"]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing required fields"):
        _read_month(path)
