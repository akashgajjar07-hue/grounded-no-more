-- Question: On which parts are recent purchase-order lead times drifting above the lead time the supplier quoted?
-- Assumptions:
--   * Non-expedite POs only (reorder and condemn_replacement); expedite POs follow the AOG-desk cap, not the quote.
--   * Realised lead = receipt - order; a PO still open and past its due date counts at its age so far
--     (right-censored, so the realised figure is a lower bound).
--   * "Recent" = received, or open past due, in the last 34 weeks (weeks 70-103), matching the planner
--     action rule; "earlier" = received before that.
--   * Quoted lead = part_master.lead_time_mean_d (the master data figure the legacy planner uses).
--   * Flag when recent / quoted >= 1.5 with at least 2 recent POs. PS4 (GN-30-E025) should surface.
-- Provenance: SIMULATED history, ratios DERIVED.
-- Example output (from `python sql/run_all.py`):
-- <<EXAMPLE>>
--         pn            description part_class  quoted_lead_d  earlier_pos  earlier_mean_lead_d  recent_pos  recent_open_past_due  recent_mean_lead_d  recent_vs_quoted planted
-- GN-30-E025 Windshield wiper motor          E           65.2            7                 71.2           3                     1               133.6              2.05     PS4
-- GN-34-E023     Static port heater          E           88.4            5                 86.1           3                     0               149.6              1.69        
-- (2 rows in total; full result in sql/results/05_lead_time_drift.csv)
-- <</EXAMPLE>>
WITH params AS (SELECT 17472 AS as_of_h, 17472 - 34 * 168 AS recent_from_h),
po AS (
    SELECT p.pn, p.po_id, p.order_h, p.due_h, p.receipt_h,
           CASE WHEN p.receipt_h IS NOT NULL THEN p.receipt_h ELSE pr.as_of_h END AS end_h,
           (p.receipt_h IS NULL AND p.due_h < pr.as_of_h)                         AS open_past_due,
           CASE WHEN coalesce(p.receipt_h, pr.as_of_h) >= pr.recent_from_h
                     AND (p.receipt_h IS NOT NULL OR p.due_h < pr.as_of_h) THEN 'recent'
                WHEN p.receipt_h IS NOT NULL THEN 'earlier' END                    AS win
    FROM purchase_orders p CROSS JOIN params pr
    WHERE p.reason <> 'expedite'
)
SELECT po.pn,
       pm.description,
       pm.part_class,
       round(pm.lead_time_mean_d, 1)                                                   AS quoted_lead_d,
       sum(CASE WHEN win = 'earlier' THEN 1 ELSE 0 END)                             AS earlier_pos,
       round(avg(CASE WHEN win = 'earlier' THEN (end_h - order_h) / 24.0 END), 1)   AS earlier_mean_lead_d,
       sum(CASE WHEN win = 'recent' THEN 1 ELSE 0 END)                              AS recent_pos,
       sum(CASE WHEN win = 'recent' AND open_past_due THEN 1 ELSE 0 END)            AS recent_open_past_due,
       round(avg(CASE WHEN win = 'recent' THEN (end_h - order_h) / 24.0 END), 1)    AS recent_mean_lead_d,
       round(avg(CASE WHEN win = 'recent' THEN (end_h - order_h) / 24.0 END)
             / pm.lead_time_mean_d, 2)                                                 AS recent_vs_quoted,
       coalesce(pm.planted, '')                                                        AS planted
FROM po
JOIN part_master pm USING (pn)
GROUP BY po.pn, pm.description, pm.part_class, pm.lead_time_mean_d, pm.planted
HAVING recent_pos >= 2 AND recent_vs_quoted >= 1.5
ORDER BY recent_vs_quoted DESC;
