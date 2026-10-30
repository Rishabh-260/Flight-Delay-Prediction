import pandas as pd

from flight_delay.eda import summarize


def test_eda_delay_rate_excludes_cancelled_flights(tmp_path):
    frame = pd.DataFrame({
        "flight_date": ["2025-01-01", "2025-01-02", "2025-01-03"],
        "reporting_airline": ["AA"] * 3,
        "origin": ["JFK"] * 3, "dest": ["LAX"] * 3,
        "crs_dep_time": [800, 900, 1000],
        "arr_delay": [20, 0, None], "cancelled": [0, 0, 1], "diverted": [0, 0, 0],
    })
    outputs = summarize(frame, tmp_path)
    monthly = pd.read_csv(outputs["monthly"])
    assert monthly.loc[0, "flights"] == 3
    assert monthly.loc[0, "delay_rate"] == 0.5
    assert monthly.loc[0, "cancellation_rate"] == 1 / 3
