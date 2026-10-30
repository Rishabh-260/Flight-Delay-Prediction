from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def summarize(frame: pd.DataFrame, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    data = frame.copy()
    data["flight_date"] = pd.to_datetime(data["flight_date"])
    data["month"] = data["flight_date"].dt.month
    data["dep_hour"] = pd.to_numeric(data["crs_dep_time"], errors="coerce") // 100
    data["is_cancelled"] = pd.to_numeric(data["cancelled"], errors="coerce").fillna(0).eq(1)
    data["is_diverted"] = pd.to_numeric(data["diverted"], errors="coerce").fillna(0).eq(1)
    data["is_operated"] = ~data["is_cancelled"] & ~data["is_diverted"]
    arr_delay = pd.to_numeric(data["arr_delay"], errors="coerce")
    data["is_delayed"] = (arr_delay.ge(15) & data["is_operated"]).where(arr_delay.notna() & data["is_operated"])
    summaries = {
        "monthly": data.groupby("month", as_index=False).agg(flights=("flight_date", "size"), delay_rate=("is_delayed", "mean"), cancellation_rate=("is_cancelled", "mean")),
        "airport": data.groupby("origin", as_index=False).agg(flights=("flight_date", "size"), delay_rate=("is_delayed", "mean"), cancellation_rate=("is_cancelled", "mean")).sort_values("flights", ascending=False),
        "route": data.groupby(["origin", "dest"], as_index=False).agg(flights=("flight_date", "size"), delay_rate=("is_delayed", "mean")).sort_values("flights", ascending=False),
        "departure_hour": data.groupby("dep_hour", as_index=False).agg(flights=("flight_date", "size"), delay_rate=("is_delayed", "mean")),
        "carrier": data.groupby("reporting_airline", as_index=False).agg(flights=("flight_date", "size"), delay_rate=("is_delayed", "mean"), cancellation_rate=("is_cancelled", "mean")).sort_values("flights", ascending=False),
    }
    outputs = {}
    for name, summary in summaries.items():
        path = output_dir / f"{name}.csv"
        summary.to_csv(path, index=False)
        outputs[name] = path
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=summaries["monthly"], x="month", y="delay_rate", marker="o", ax=ax)
    ax.set(title="Arrival delay rate by month (15+ minutes)", xlabel="Month", ylabel="Delay rate")
    fig.tight_layout()
    path = output_dir / "monthly_delay_rate.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["monthly_plot"] = path
    airport_plot_data = summaries["airport"].head(20).sort_values("delay_rate")
    fig, ax = plt.subplots(figsize=(10, 7))
    sns.barplot(data=airport_plot_data, x="delay_rate", y="origin", color="#3975a8", ax=ax)
    ax.set(title="Arrival delay rate at 20 busiest origin airports", xlabel="Delay rate", ylabel="Origin airport")
    fig.tight_layout()
    path = output_dir / "airport_delay_rate.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["airport_plot"] = path
    route_plot_data = summaries["route"].head(20).copy()
    route_plot_data["route"] = route_plot_data["origin"] + "–" + route_plot_data["dest"]
    route_plot_data.sort_values("delay_rate", inplace=True)
    fig, ax = plt.subplots(figsize=(10, 7))
    sns.barplot(data=route_plot_data, x="delay_rate", y="route", color="#bf7042", ax=ax)
    ax.set(title="Arrival delay rate on 20 busiest routes", xlabel="Delay rate", ylabel="Route")
    fig.tight_layout()
    path = output_dir / "route_delay_rate.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["route_plot"] = path
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=summaries["departure_hour"], x="dep_hour", y="delay_rate", marker="o", ax=ax)
    ax.set(title="Arrival delay rate by scheduled departure hour", xlabel="Scheduled departure hour (local)", ylabel="Delay rate", xticks=range(0, 24, 2))
    fig.tight_layout()
    path = output_dir / "departure_hour_delay_rate.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    outputs["departure_hour_plot"] = path
    return outputs
