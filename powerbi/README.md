# Power BI handoff

## Connect

1. Start the PostgreSQL service using the root `compose.yaml` and run `sql/01_schema.sql` followed by `sql/02_power_bi_views.sql`.
2. In Power BI Desktop, select **Get Data → PostgreSQL database**. Connect to `localhost:5432`, database `flight_delay`, and choose **Import** for the initial portfolio dashboard.
3. Load `v_flight_analytics`, `v_monthly_performance`, `v_airport_performance`, `v_route_performance`, `v_carrier_performance`, and `v_departure_hour_performance`.
4. Use `v_flight_analytics[flight_date]` as the date relationship. Airport views are airport-grain for comparing origin and destination airports; flight details remain one row per BTS flight record.

## Suggested pages

- **Executive overview:** scheduled flights, operated flights, delay rate, on-time rate, cancellation rate, monthly delay trend, delay rate by carrier.
- **Airport operations:** airport comparison table, top airports by volume, delay rate and cancellations, origin/destination slicer.
- **Routes & schedule:** route table/map, delay rate by scheduled departure hour, month and day-of-week comparisons.

## Measures (DAX)

```DAX
Scheduled Flights = COUNTROWS(v_flight_analytics)
Operated Flights = CALCULATE([Scheduled Flights], v_flight_analytics[is_operated] = TRUE())
Known Outcome Flights = CALCULATE([Scheduled Flights], v_flight_analytics[is_operated] = TRUE(), NOT ISBLANK(v_flight_analytics[is_delayed]))
Delayed Flights = CALCULATE([Scheduled Flights], v_flight_analytics[is_delayed] = TRUE())
Cancelled Flights = CALCULATE([Scheduled Flights], v_flight_analytics[is_cancelled] = TRUE())
Delay Rate = DIVIDE([Delayed Flights], [Known Outcome Flights])
On-Time Flights = CALCULATE([Scheduled Flights], v_flight_analytics[is_operated] = TRUE(), v_flight_analytics[is_delayed] = FALSE())
On-Time Performance = DIVIDE([On-Time Flights], [Known Outcome Flights])
Cancellation Rate = DIVIDE([Cancelled Flights], [Scheduled Flights])
```

Delay and on-time rates use operated flights with an observed arrival outcome; cancellations are shown separately. Add an `is_diverted` filter to exclude diversions from operated-flight comparisons if the report should match the classifier cohort exactly.
