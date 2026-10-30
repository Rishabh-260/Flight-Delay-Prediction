-- Power BI can connect to these reporting views using PostgreSQL's native connector.
CREATE OR REPLACE VIEW v_flight_analytics AS
SELECT
    flight_date,
    reporting_airline,
    origin,
    origin_city,
    origin_state,
    dest,
    dest_city,
    dest_state,
    crs_dep_time,
    crs_arr_time,
    distance,
    COALESCE(cancelled, 0) = 1 AS is_cancelled,
    COALESCE(diverted, 0) = 1 AS is_diverted,
    COALESCE(cancelled, 0) <> 1 AND COALESCE(diverted, 0) <> 1 AS is_operated,
    CASE WHEN COALESCE(cancelled, 0) <> 1 AND COALESCE(diverted, 0) <> 1 AND arr_delay IS NOT NULL
         THEN arr_delay >= 15 END AS is_delayed,
    arr_delay,
    cancellation_code
FROM raw_bts_flights;

CREATE OR REPLACE VIEW v_monthly_performance AS
SELECT date_trunc('month', flight_date)::date AS month_start,
       COUNT(*) AS scheduled_flights,
       COUNT(*) FILTER (WHERE is_operated) AS operated_flights,
       COUNT(*) FILTER (WHERE is_cancelled) AS cancelled_flights,
       COUNT(*) FILTER (WHERE is_diverted) AS diverted_flights,
       COUNT(*) FILTER (WHERE is_delayed) AS delayed_flights,
       AVG(is_delayed::int) FILTER (WHERE is_operated AND is_delayed IS NOT NULL) AS delay_rate,
       AVG((NOT is_delayed)::int) FILTER (WHERE is_operated AND is_delayed IS NOT NULL) AS on_time_rate,
       AVG(is_cancelled::int) AS cancellation_rate
FROM v_flight_analytics
GROUP BY 1;

CREATE OR REPLACE VIEW v_airport_performance AS
SELECT airport_code, airport_city, airport_state,
       COUNT(*) AS scheduled_flights,
       COUNT(*) FILTER (WHERE is_operated) AS operated_flights,
       COUNT(*) FILTER (WHERE is_cancelled) AS cancelled_flights,
       COUNT(*) FILTER (WHERE is_delayed) AS delayed_flights,
       AVG(is_delayed::int) FILTER (WHERE is_operated AND is_delayed IS NOT NULL) AS delay_rate,
       AVG((NOT is_delayed)::int) FILTER (WHERE is_operated AND is_delayed IS NOT NULL) AS on_time_rate
FROM (
    SELECT origin AS airport_code, origin_city AS airport_city, origin_state AS airport_state,
           is_operated, is_cancelled, is_delayed FROM v_flight_analytics
    UNION ALL
    SELECT dest, dest_city, dest_state,
           is_operated, is_cancelled, is_delayed FROM v_flight_analytics
) airports
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW v_route_performance AS
SELECT origin, dest, reporting_airline,
       COUNT(*) AS scheduled_flights,
       COUNT(*) FILTER (WHERE is_operated) AS operated_flights,
       COUNT(*) FILTER (WHERE is_cancelled) AS cancelled_flights,
       COUNT(*) FILTER (WHERE is_delayed) AS delayed_flights,
       AVG(is_delayed::int) FILTER (WHERE is_operated AND is_delayed IS NOT NULL) AS delay_rate,
       AVG(arr_delay) FILTER (WHERE is_operated AND arr_delay IS NOT NULL) AS avg_arrival_delay_minutes
FROM v_flight_analytics
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW v_carrier_performance AS
SELECT reporting_airline,
       COUNT(*) AS scheduled_flights,
       COUNT(*) FILTER (WHERE is_operated) AS operated_flights,
       COUNT(*) FILTER (WHERE is_cancelled) AS cancelled_flights,
       COUNT(*) FILTER (WHERE is_delayed) AS delayed_flights,
       AVG(is_delayed::int) FILTER (WHERE is_operated AND is_delayed IS NOT NULL) AS delay_rate,
       AVG(is_cancelled::int) AS cancellation_rate
FROM v_flight_analytics
GROUP BY 1;

CREATE OR REPLACE VIEW v_departure_hour_performance AS
SELECT (crs_dep_time / 100) AS scheduled_departure_hour,
       COUNT(*) AS scheduled_flights,
       COUNT(*) FILTER (WHERE is_delayed) AS delayed_flights,
       AVG(is_delayed::int) FILTER (WHERE is_operated AND is_delayed IS NOT NULL) AS delay_rate
FROM v_flight_analytics
WHERE crs_dep_time BETWEEN 0 AND 2359
GROUP BY 1;
