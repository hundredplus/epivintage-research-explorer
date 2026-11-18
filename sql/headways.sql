-- All input trips represent ONE active service day; no calendar expansion.
-- This screens scheduled spacing within each route/direction/stop group.
-- It does not infer signalling feasibility or shared-track conflicts.
WITH ordered AS (
    SELECT *, LAG(departure_seconds) OVER (
        PARTITION BY route_id, direction_id, stop_id
        ORDER BY departure_seconds, trip_id
    ) AS previous_departure_seconds
    FROM departures
), measured AS (
    SELECT *, departure_seconds - previous_departure_seconds AS headway_seconds
    FROM ordered
)
SELECT trip_id, stop_id, route_id, direction_id, departure_seconds,
       previous_departure_seconds, headway_seconds,
       CASE WHEN headway_seconds < :minimum_seconds THEN 1 ELSE 0 END AS below_threshold
FROM measured
ORDER BY route_id, direction_id, stop_id, departure_seconds, trip_id;
