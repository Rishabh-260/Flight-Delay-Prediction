import pandas as pd

from flight_delay.features import FEATURES, LEAKAGE_COLUMNS, assert_no_target_leakage, prepare_flights


def example_frame():
    return pd.DataFrame({
        "flight_date": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"],
        "reporting_airline": ["AA"] * 4,
        "origin": ["JFK", "JFK", "JFK", "JFK"], "dest": ["LAX"] * 4,
        "crs_dep_time": [800, 900, 1000, 1100], "crs_arr_time": [1100, 1200, 1300, 1400],
        "crs_elapsed_time": [300] * 4, "distance": [2475] * 4,
        "arr_delay": [14, 15, 30, None], "cancelled": [0, 0, 0, 1], "diverted": [0, 0, 0, 0],
    })


def test_target_uses_inclusive_fifteen_minute_threshold_and_excludes_cancelled():
    result = prepare_flights(example_frame())
    assert result["is_delayed"].tolist() == [0, 1, 1]
    assert not result["is_cancelled"].any()


def test_prior_delay_rates_are_strictly_past_only():
    result = prepare_flights(example_frame())
    assert result.iloc[0]["prior_origin_delay_rate"] == 0
    assert result.iloc[1]["prior_origin_delay_rate"] == 0
    assert result.iloc[2]["prior_origin_delay_rate"] == 0.5


def test_model_features_exclude_outcome_and_post_departure_fields():
    assert_no_target_leakage(FEATURES)
    assert not LEAKAGE_COLUMNS.intersection(FEATURES)


def test_missing_schedule_values_are_permitted_for_imputation():
    frame = example_frame()
    frame.loc[0, "crs_dep_time"] = None
    result = prepare_flights(frame)
    assert pd.isna(result.iloc[0]["dep_hour"])
