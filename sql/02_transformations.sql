USE railway_dw;

-- =========================================================
-- VIEW 1: Stations present in ORIGINAL route but missing in DIVERTED route
-- =========================================================
CREATE OR REPLACE VIEW vw_skipped_stations AS
SELECT
    t.train_number,
    t.train_name,
    orig.station_name AS skipped_station,
    orig.sequence_no AS original_stop_number
FROM route_stations orig
INNER JOIN trains t
    ON orig.train_number = t.train_number
LEFT JOIN route_stations div_rt
    ON orig.train_number = div_rt.train_number
    AND div_rt.route_type = 'DIVERTED'
    AND orig.station_name = div_rt.station_name
WHERE orig.route_type = 'ORIGINAL'
  AND div_rt.id IS NULL;

-- =========================================================
-- VIEW 2: Stations added in DIVERTED route that were not in ORIGINAL route
-- =========================================================
CREATE OR REPLACE VIEW vw_added_stations AS
SELECT
    t.train_number,
    t.train_name,
    div_rt.station_name AS added_station,
    div_rt.sequence_no AS diverted_stop_number
FROM route_stations div_rt
INNER JOIN trains t
    ON div_rt.train_number = t.train_number
LEFT JOIN route_stations orig
    ON div_rt.train_number = orig.train_number
    AND orig.route_type = 'ORIGINAL'
    AND div_rt.station_name = orig.station_name
WHERE div_rt.route_type = 'DIVERTED'
  AND orig.id IS NULL;