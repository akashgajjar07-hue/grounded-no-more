-- Question: What do emergency (AOG) transfers cost by lane, and how does that compare with routine replenishment?
-- Assumptions:
--   * Source: transfers, weeks 0-103 under P0. Emergency cost uses the engine's public formula
--     (economics.emergency_logistics_aed scaled by distance, ASSUMED AED 2,000-15,000); routine = AED 150 per line (ASSUMED).
--   * Hours = arrive_h - ship_h. Per-year = two-year totals / 2.
-- Provenance: SIMULATED history; unit costs ASSUMED; aggregation DERIVED.
-- Example output (from `python sql/run_all.py`):
-- <<EXAMPLE>>
--    lane  emergency_transfers  emergency_units  emergency_cost_aed  emergency_cost_aed_per_year  cost_per_emergency_aed  emergency_mean_hours  routine_transfers  routine_mean_days
-- AUH>FRA                   18               18            106200.0                      53100.0                  5900.0                  14.0                377                3.9
-- AUH>CAI                   23               23             90850.0                      45425.0                  3950.0                  11.0                534                4.0
-- AUH>BOM                   28               28             74200.0                      37100.0                  2650.0                   9.0                688                4.0
-- AUH>LHR                   10               10             72000.0                      36000.0                  7200.0                  16.0                416                4.0
-- AUH>JED                   24               24             63600.0                      31800.0                  2650.0                   9.0                548                3.9
-- AUH>SIN                    9                9             47250.0                      23625.0                  5250.0                  13.0                384                4.1
-- (6 rows in total; full result in sql/results/09_emergency_transfer_cost_by_lane.csv)
-- <</EXAMPLE>>
SELECT from_station || '>' || to_station                                         AS lane,
       sum(CASE WHEN kind = 'emergency' THEN 1 ELSE 0 END)                         AS emergency_transfers,
       sum(CASE WHEN kind = 'emergency' THEN qty ELSE 0 END)                       AS emergency_units,
       round(sum(CASE WHEN kind = 'emergency' THEN cost_aed ELSE 0 END), 0)        AS emergency_cost_aed,
       round(sum(CASE WHEN kind = 'emergency' THEN cost_aed ELSE 0 END) / 2, 0)    AS emergency_cost_aed_per_year,
       round(avg(CASE WHEN kind = 'emergency' THEN cost_aed END), 0)               AS cost_per_emergency_aed,
       round(avg(CASE WHEN kind = 'emergency' THEN arrive_h - ship_h END), 1)      AS emergency_mean_hours,
       sum(CASE WHEN kind = 'routine' THEN 1 ELSE 0 END)                           AS routine_transfers,
       round(avg(CASE WHEN kind = 'routine' THEN arrive_h - ship_h END) / 24, 1)   AS routine_mean_days
FROM transfers
GROUP BY ALL
HAVING emergency_transfers > 0
ORDER BY emergency_cost_aed DESC;
