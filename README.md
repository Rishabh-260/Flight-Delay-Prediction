# Flight Delay Prediction & Operational Analytics

An end-to-end project using the BTS Reporting Carrier On-Time Performance dataset. It ingests 2025 monthly BTS files into PostgreSQL, explores delay patterns, trains schedule-time arrival-delay classifiers, and serves Power BI reporting views.

The prediction target is an arrival delay of **15 or more minutes**. BTS describes its flight-level dataset as monthly domestic nonstop operations reported by carriers, with schedule/actual times, cancellations, diversions, delay causes, and distance. Only the actual arrival outcome creates the target; post-departure and delay-cause columns are excluded from model inputs. [BTS dataset profile](https://transtats.bts.gov/TableInfo.asp?QO_fu146_anzr=b0-gvzr&V0s1_b0yB=D&gnoyr_VQ=FGJ) · [BTS delay definition](https://www.transtats.bts.gov/ot_delay/)

## Quick start (PowerShell)

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
docker compose up -d db
```

Apply the schema and reporting views:

```powershell
Get-Content sql/01_schema.sql | docker compose exec -T db psql -U flight_user -d flight_delay
Get-Content sql/02_power_bi_views.sql | docker compose exec -T db psql -U flight_user -d flight_delay
```

Run ingestion, EDA, and modeling:

```powershell
python -m flight_delay.cli all --year 2025
```

The source monthly ZIPs are downloaded from BTS TranStats' official PREZIP directory. Each month is stored under `data/raw/` and can be rerun; ingestion replaces rows for that month before inserting the refreshed copy. The BTS archive currently uses this naming pattern: `On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2025_1.zip` through `_2025_12.zip`.

## Pipeline commands

- `python -m flight_delay.cli ingest --year 2025`: download and load monthly CSVs to `raw_bts_flights`.
- `python -m flight_delay.cli eda --year 2025`: write monthly, airport, route, carrier, and departure-hour summaries plus a monthly trend plot under `artifacts/eda/`.
- `python -m flight_delay.cli train --year 2025`: generate labels and past-only historical delay rates, compare Logistic Regression, Random Forest, and XGBoost, and save metrics, selected model, and feature importance under `artifacts/models/`.
- `python -m flight_delay.cli all --year 2025`: run all steps.

The model uses January–September for training, October for threshold selection, and November–December as the final test period. Training is capped at a deterministic stratified sample of 300,000 flights for local runtime; validation and test use all eligible rows. Logistic Regression and Random Forest use class weights; XGBoost uses `scale_pos_weight`. The final model is selected by holdout ROC-AUC, while its threshold is selected using validation F1.

## Data and output

- PostgreSQL `raw_bts_flights`: selected source fields used for prediction and reporting.
- `v_flight_analytics`: flight-grain dataset with target, operating, cancellation, and diversion flags.
- `v_monthly_performance`, `v_airport_performance`, `v_route_performance`, `v_carrier_performance`, `v_departure_hour_performance`: dashboard aggregates.
- `artifacts/eda/`: CSV summaries and PNG charts for monthly, airport, route, and departure-hour delay patterns.
- `artifacts/models/`: model comparison, metrics JSON/CSV, selected `.joblib`, and permutation importance CSV.

See [Power BI setup and report design](powerbi/README.md). Reports distinguish operated-flight delay/on-time rates from scheduled-flight cancellation rates. BTS data and Power BI Desktop are external dependencies; an internet connection is needed for first-time data acquisition. The report handoff consists of SQL views, DAX measures, and page instructions, not a generated `.pbix` file.

## Tests

```powershell
python -m pytest
```

Tests cover the 15-minute label boundary, cancellation exclusion, past-only historical rates, permitted missing features, leakage guard, and chronological split.
