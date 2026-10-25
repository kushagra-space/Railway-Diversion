USE railway_dw;

-- 1. Which stations are skipped for each train?
SELECT
    train_number,
    train_name,
    skipped_station,
    original_stop_number
FROM vw_skipped_stations
ORDER BY train_number, original_stop_number;

-- 2. Which new stations were added on the diverted route?
SELECT
    train_number,
    train_name,
    added_station,
    diverted_stop_number
FROM vw_added_stations
ORDER BY train_number, diverted_stop_number;

-- 3. Which stations are most frequently skipped across all diverted trains?
SELECT
    skipped_station AS station_name,
    COUNT(DISTINCT train_number) AS affected_trains_count
FROM vw_skipped_stations
GROUP BY skipped_station
ORDER BY affected_trains_count DESC, station_name ASC;

-- 4. CTE + CASE WHEN + WINDOW FUNCTION (DENSE_RANK):
-- Rank trains by the percentage of original stations skipped
WITH route_totals AS (
    SELECT
        train_number,
        COUNT(*) AS total_original_stops
    FROM route_stations
    WHERE route_type = 'ORIGINAL'
    GROUP BY train_number
)
SELECT
    t.train_number,
    t.train_name,
    rt.total_original_stops,
    de.skipped_count,
    de.added_count,
    ROUND((de.skipped_count * 100.0) / rt.total_original_stops, 1) AS pct_stations_skipped,
    CASE
        WHEN de.skipped_count = 0 AND de.added_count = 0 THEN 'No Change'
        WHEN de.skipped_count >= 3 THEN 'High Impact'
        ELSE 'Moderate Impact'
    END AS impact_category,
    DENSE_RANK() OVER (
        ORDER BY (de.skipped_count * 1.0 / rt.total_original_stops) DESC
    ) AS disruption_rank
FROM trains t
INNER JOIN diversion_events de
    ON t.train_number = de.train_number
INNER JOIN route_totals rt
    ON t.train_number = rt.train_number;

-- 5. WINDOW FUNCTIONS (LAG & LEAD):
-- Show previous station and next station for each stop on the original route
SELECT
    train_number,
    sequence_no,
    LAG(station_name, 1, 'START') OVER (
        PARTITION BY train_number ORDER BY sequence_no
    ) AS previous_station,
    station_name AS current_station,
    LEAD(station_name, 1, 'END') OVER (
        PARTITION BY train_number ORDER BY sequence_no
    ) AS next_station
FROM route_stations
WHERE route_type = 'ORIGINAL'
ORDER BY train_number, sequence_no;