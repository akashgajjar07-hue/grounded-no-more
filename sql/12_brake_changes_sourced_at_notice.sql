-- Question: For the wear-planned carbon brake changes, how was the replacement unit secured during the notice
--           window, and did any change still cause material-related downtime?
-- Assumptions:
--   * Brakes have removal_mode = 'wear_planned' in part_master: the change is known 5-10 days ahead (known_h) and
--     done at AUH on the next hub arrival. There is no wear model; cost-per-landing brake contracts are not modelled.
--   * At notice the engine projects AUH stock at the due time. If short it sources then (V2-SIM-13), traced in
--     aog_route_result: planned_covered (hub stock projected sufficient), planned_transfer (transfer from another
--     station ordered at notice), planned_loan (pre-arranged exchange / loan fitted at the change), otherwise the
--     need falls back to the AOG routes (robbery / exchange_loan / none) at the due time.
--   * Downtime: aog_events whose request_ids contain the request (one id per event in v2).
-- Provenance: SIMULATED history (notice window and route draws ASSUMED), aggregation DERIVED.
-- Example output (from `python sql/run_all.py --update-examples`):
-- <<EXAMPLE>>
--         pn                description       sourced_as  planned_changes  mean_notice_days  fitted_from_stock_on_the_day  mean_wait_after_due_h  downtime_events  downtime_hours
-- GN-32-R013 Carbon brake assembly (NB)  planned_covered               80               7.3                            80                    0.0                0             0.0
-- GN-32-R013 Carbon brake assembly (NB) planned_transfer               10               7.1                            10                    0.0                0             0.0
-- GN-32-R013 Carbon brake assembly (NB)     planned_loan               11               7.2                             0                    0.0                0             0.0
-- GN-32-R013 Carbon brake assembly (NB)          robbery                1               9.5                             0                   78.0                1            83.0
-- GN-32-R036 Carbon brake assembly (WB)  planned_covered               88               7.5                            88                    0.0                0             0.0
-- GN-32-R036 Carbon brake assembly (WB) planned_transfer               17               7.0                            17                    0.0                0             0.0
-- GN-32-R036 Carbon brake assembly (WB)     planned_loan                6               7.7                             0                    0.0                0             0.0
-- GN-32-R036 Carbon brake assembly (WB)          robbery                2               8.9                             0                    7.5                2            25.0
-- (9 rows in total; full result in sql/results/12_brake_changes_sourced_at_notice.csv)
-- <</EXAMPLE>>
WITH brake AS (
    SELECT r.*, pm.description
    FROM material_requests r
    JOIN part_master pm USING (pn)
    WHERE pm.removal_mode = 'wear_planned' AND r.source = 'planned_removal'
),
aog AS (
    SELECT trim(x.rid)::BIGINT AS request_id, sum(a.hours) AS aog_hours
    FROM aog_events a, unnest(string_split(a.request_ids, ';')) AS x(rid)
    GROUP BY ALL
)
SELECT b.pn,
       b.description,
       b.aog_route_result                                                       AS sourced_as,
       count(*)                                                                 AS planned_changes,
       round(avg((b.need_h - b.known_h) / 24.0), 1)                             AS mean_notice_days,
       sum(CASE WHEN b.immediate_fill THEN 1 ELSE 0 END)                        AS fitted_from_stock_on_the_day,
       round(avg(b.filled_h - b.need_h), 1)                                     AS mean_wait_after_due_h,
       count(a.request_id)                                                      AS downtime_events,
       round(coalesce(sum(a.aog_hours), 0), 1)                                  AS downtime_hours
FROM brake b
LEFT JOIN aog a USING (request_id)
GROUP BY b.pn, b.description, b.aog_route_result
ORDER BY b.pn,
         CASE b.aog_route_result WHEN 'planned_covered' THEN 0 WHEN 'planned_transfer' THEN 1 WHEN 'planned_loan' THEN 2
                         ELSE 3 END;
