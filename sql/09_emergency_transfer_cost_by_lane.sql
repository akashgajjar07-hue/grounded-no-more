-- Question: What do emergency (AOG) transfers cost by lane, and how does that compare with routine replenishment?
-- Assumptions:
--   * Source: transfers, weeks 0-103 under P0. Kinds: emergency, routine, loan_return (shipping a serviceable own
--     unit out to replace a borrowed one; counted separately here).
--   * Emergency cost uses the engine's public formula (economics.emergency_logistics_aed scaled by distance,
--     ASSUMED); routine cost is ASSUMED per line.
--   * Hours = arrive_h - ship_h. Per-year = two-year totals / 2.
-- Provenance: SIMULATED history; unit costs ASSUMED; aggregation DERIVED.
-- Example output (from `python sql/run_all.py --update-examples`):
-- <<EXAMPLE>>
--    lane  emergency_transfers  emergency_units  emergency_cost_aed  emergency_cost_aed_per_year  cost_per_emergency_aed  emergency_mean_hours  routine_transfers  routine_mean_days  loan_return_transfers
-- AUH>LHR                   17               17            122400.0                      61200.0                  7200.0                  16.0                108                3.9                      0
-- AUH>CAI                   28               28            110600.0                      55300.0                  3950.0                  11.0                146                4.1                      7
-- AUH>SIN                   18               18             94500.0                      47250.0                  5250.0                  13.0                118                3.9                      0
-- AUH>JED                   26               26             68900.0                      34450.0                  2650.0                   9.0                169                3.9                      5
-- AUH>BOM                   23               23             60950.0                      30475.0                  2650.0                   9.0                228                3.8                      7
-- AUH>FRA                   10               10             59000.0                      29500.0                  5900.0                  14.0                108                3.9                      0
-- FRA>AUH                    1                1              5900.0                       2950.0                  5900.0                  14.0                  5                3.8                      0
-- (7 rows in total; full result in sql/results/09_emergency_transfer_cost_by_lane.csv)
-- <</EXAMPLE>>
SELECT from_station || '>' || to_station                                         AS lane,
       sum(CASE WHEN kind = 'emergency' THEN 1 ELSE 0 END)                         AS emergency_transfers,
       sum(CASE WHEN kind = 'emergency' THEN qty ELSE 0 END)                       AS emergency_units,
       round(sum(CASE WHEN kind = 'emergency' THEN cost_aed ELSE 0 END), 0)        AS emergency_cost_aed,
       round(sum(CASE WHEN kind = 'emergency' THEN cost_aed ELSE 0 END) / 2, 0)    AS emergency_cost_aed_per_year,
       round(avg(CASE WHEN kind = 'emergency' THEN cost_aed END), 0)               AS cost_per_emergency_aed,
       round(avg(CASE WHEN kind = 'emergency' THEN arrive_h - ship_h END), 1)      AS emergency_mean_hours,
       sum(CASE WHEN kind = 'routine' THEN 1 ELSE 0 END)                           AS routine_transfers,
       round(avg(CASE WHEN kind = 'routine' THEN arrive_h - ship_h END) / 24, 1)   AS routine_mean_days,
       sum(CASE WHEN kind = 'loan_return' THEN 1 ELSE 0 END)                       AS loan_return_transfers
FROM transfers
GROUP BY ALL
HAVING emergency_transfers > 0
ORDER BY emergency_cost_aed DESC;
