from __future__ import annotations

import pandas as pd

LEAKAGE_COLUMNS = {
    "arr_delay", "arr_time", "dep_time", "dep_delay", "taxi_out", "taxi_in",
    "wheels_off", "wheels_on", "actual_elapsed_time", "air_time", "cancelled",
    "diverted", "cancellation_code", "carrier_delay", "weather_delay", "nas_delay",
    "security_delay", "late_aircraft_delay", "is_delayed",
}
CATEGORICAL_FEATURES = ["reporting_airline", "origin", "dest", "day_of_week", "month", "dep_hour", "arr_hour"]
NUMERIC_FEATURES = ["distance", "crs_elapsed_time", "prior_origin_delay_rate", "prior_route_delay_rate"]
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def prepare_flights(frame: pd.DataFrame) -> pd.DataFrame:
    """Create delay labels and schedule-time features, excluding cancellations/diversions."""
    data = frame.copy()
    data["flight_date"] = pd.to_datetime(data["flight_date"], errors="coerce")
    for column in ("cancelled", "diverted", "arr_delay"):
        if column in data:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["is_cancelled"] = data["cancelled"].fillna(0).eq(1)
    data["is_diverted"] = data["diverted"].fillna(0).eq(1)
    data["is_operated"] = ~data["is_cancelled"] & ~data["is_diverted"]
    data["is_delayed"] = data["arr_delay"].ge(15).astype("int8")
    # Keep non-operated rows for operational reporting, but only operated rows with a known
    # arrival delay have a classifier label.
    dep = pd.to_numeric(data["crs_dep_time"], errors="coerce")
    arr = pd.to_numeric(data["crs_arr_time"], errors="coerce")
    data["dep_hour"] = (dep // 100).where(dep.notna())
    data["arr_hour"] = (arr // 100).where(arr.notna())
    data["month"] = data["flight_date"].dt.month
    data["day_of_week"] = data["flight_date"].dt.dayofweek
    data["distance"] = pd.to_numeric(data["distance"], errors="coerce")
    data["crs_elapsed_time"] = pd.to_numeric(data["crs_elapsed_time"], errors="coerce")
    valid = data.loc[data["is_operated"] & data["arr_delay"].notna()].copy()
    valid.sort_values(["flight_date", "origin", "dest", "reporting_airline"], inplace=True)
    valid["route_key"] = valid["origin"].astype(str) + "_" + valid["dest"].astype(str) + "_" + valid["reporting_airline"].astype(str)
    for name, keys in (("origin", ["origin"]), ("route", ["route_key"])):
        # Aggregate a whole local-date first, then shift by date within each group. Every
        # flight on a given date therefore sees only completed earlier dates, not a peer
        # outcome later on the same day.
        daily = valid.groupby(keys + ["flight_date"], sort=True, observed=True)["is_delayed"].agg(["sum", "count"]).reset_index()
        grouped = daily.groupby(keys, sort=False, observed=True)
        prior_delayed = grouped["sum"].cumsum() - daily["sum"]
        prior_total = grouped["count"].cumsum() - daily["count"]
        daily[f"prior_{name}_delay_rate"] = prior_delayed / prior_total.replace(0, pd.NA)
        valid = valid.merge(daily[keys + ["flight_date", f"prior_{name}_delay_rate"]], on=keys + ["flight_date"], how="left", validate="many_to_one")
    valid["prior_origin_delay_rate"] = pd.to_numeric(valid["prior_origin_delay_rate"], errors="coerce").fillna(0.0)
    valid["prior_route_delay_rate"] = pd.to_numeric(valid["prior_route_delay_rate"], errors="coerce").fillna(0.0)
    return valid


def assert_no_target_leakage(feature_names: list[str] = FEATURES) -> None:
    leaked = LEAKAGE_COLUMNS.intersection(feature_names)
    if leaked:
        raise ValueError(f"Post-outcome fields cannot be model features: {sorted(leaked)}")
