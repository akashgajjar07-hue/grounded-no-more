-- Question: When the shelf is empty and stock cannot arrive in time, which AOG recovery route did the desk use,
--           at which station, how often, and how long did the aircraft wait for the part?
-- Assumptions:
--   * Source: material_requests.aog_route_result for unscheduled needs (planned brake changes are in query 12).
--     Routes (config aog_sourcing, all ASSUMED): local_borrow (outstation borrow / third-party loan), robbery
--     (from a same-type aircraft at AUH; engineering/quality approval required, a human decision), exchange_loan
--     (AOG exchange / loan market), local_buy (C/E local AOG buy), none (no route succeeded; normal supply).
--   * A failed route is retried while the need is open (R every 72 h, C/E every 24 h); attempts = tries made.
--   * wait = filled_h - need_h (need to part available, before fitting/RTS); route response = filled_h - aog_route_h
--     (start of the successful attempt to part available). Medians use quantile_cont. For a deferred D3/D10 need the
--     route is triggered only at deadline - route time - 24 h (V2-SIM-6), so its wait includes window slack and is
--     not downtime; downtime is in aog_events (query 01).
--   * One row per route and station, plus a station = 'ALL' row per route (network total).
--   * Cross-check: robbery and loan counts reconcile with the aog_robberies and aog_loans tables.
-- Provenance: SIMULATED history (route availability and response draws ASSUMED), aggregation DERIVED.
-- Example output (from `python sql/run_all.py --update-examples`):
-- <<EXAMPLE>>
--         route station  requests  pns  rotable_requests  d0_requests  mean_attempts  mean_wait_h  median_wait_h  mean_route_response_h  approval_flagged
--  local_borrow     ALL         8    5                 8            5           1.00         26.8            6.0                    5.8                 0
--  local_borrow     BOM         4    1                 4            4           1.00          6.3            6.0                    6.3                 0
--  local_borrow     CAI         3    3                 3            1           1.00         60.7            4.0                    4.7                 0
--  local_borrow     JED         1    1                 1            0           1.00          7.0            7.0                    7.0                 0
--       robbery     ALL        53   10                53            7           1.04         50.8            7.0                    9.5                53
--       robbery     AUH        53   10                53            7           1.04         50.8            7.0                    9.5                53
-- exchange_loan     ALL        46   11                46           15           1.04         91.4           44.0                   40.3                 0
-- exchange_loan     AUH        34   11                34            4           1.06        111.5           51.5                   42.3                 0
-- (15 rows in total; full result in sql/results/11_aog_recovery_routes.csv)
-- <</EXAMPLE>>
SELECT r.aog_route_result                                                      AS route,
       coalesce(r.station, 'ALL')                                              AS station,
       count(*)                                                                AS requests,
       count(DISTINCT r.pn)                                                    AS pns,
       sum(CASE WHEN pm.part_class = 'R' THEN 1 ELSE 0 END)                    AS rotable_requests,
       sum(CASE WHEN r.deadline_class = 'D0' THEN 1 ELSE 0 END)                AS d0_requests,
       round(avg(r.aog_route_attempts), 2)                                     AS mean_attempts,
       round(avg(r.filled_h - r.need_h), 1)                                    AS mean_wait_h,
       round(quantile_cont(r.filled_h - r.need_h, 0.5), 1)                     AS median_wait_h,
       round(avg(r.filled_h - r.aog_route_h), 1)                               AS mean_route_response_h,
       sum(CASE WHEN r.approval_flag IS NOT NULL THEN 1 ELSE 0 END)            AS approval_flagged
FROM material_requests r
JOIN part_master pm USING (pn)
WHERE r.source = 'unscheduled_removal'
  AND r.aog_route_result IS NOT NULL
GROUP BY GROUPING SETS ((r.aog_route_result), (r.aog_route_result, r.station))
ORDER BY CASE r.aog_route_result WHEN 'local_borrow' THEN 0 WHEN 'robbery' THEN 1 WHEN 'exchange_loan' THEN 2
                                 WHEN 'local_buy' THEN 3 ELSE 4 END,
         r.station NULLS FIRST;
