import pandas as pd

from flight_delay.model import chronological_split


def test_chronological_split_keeps_final_months_out_of_training():
    data = pd.DataFrame({"flight_date": pd.date_range("2025-01-01", "2025-12-31", freq="D")})
    train, validation, test = chronological_split(data)
    assert pd.to_datetime(train.flight_date).max().month == 9
    assert set(pd.to_datetime(validation.flight_date).dt.month) == {10}
    assert set(pd.to_datetime(test.flight_date).dt.month) == {11, 12}
