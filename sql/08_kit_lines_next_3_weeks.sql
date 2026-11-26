-- Question: Which A-check kit lines fall due in the next 3 weeks, and does AUH hold enough stock to cover them?
-- Assumptions:
--   * The history ends at week 103 and contains no check scheduled after it, so the query is run "as of"
--     the start of week 100 (hour 16,800) and looks 21 days ahead (weeks 100-102). Change as_of_week to re-run.
--   * Only A-check lines already notified at the as-of time (notice_h <= as_of_h) are counted: a planner cannot
--     see more. Wear-planned brake changes are not kit lines (see 12_brake_changes_sourced_at_notice.sql).
--   * Kits are drawn at AUH (all A-checks run at the hub). Cover is compared with the AUH on-hand in the week
--     before the as-of week (stock_snapshots), ignoring line usage and inbound POs, so it is a first screen only.
-- Provenance: SIMULATED history, cover DERIVED.
-- Example output (from `python sql/run_all.py --update-examples`):
-- <<EXAMPLE>>
--         pn                            description part_class  kit_lines  aircraft  qty_due  first_due_week  last_due_week  auh_on_hand  auh_after_kits  status
-- GN-21-C024 Cabin air compressor inlet filter (WB)          C          5         5       12             100            102          126             114 covered
-- GN-29-C027          Hydraulic filter element (WB)          C          5         5       12             100            102          139             127 covered
-- GN-32-C009               Tyre valve core kit (NB)          C          8         8       20             100            102          157             137 covered
-- GN-36-C012          Pneumatic duct seal ring (NB)          C          6         6       16             100            101          199             183 covered
-- GN-36-C013                      V-band clamp (NB)          C          9         9       23             100            101          352             329 covered
-- GN-49-C032            APU oil filter element (WB)          C          5         5       15             100            102          369             354 covered
-- GN-32-C029               Tyre valve core kit (WB)          C          5         5       11             100            102          449             438 covered
-- GN-29-C006              Hydraulic O-ring kit (NB)          C          7         7       13             100            102          473             460 covered
-- (19 rows in total; full result in sql/results/08_kit_lines_next_3_weeks.csv)
-- <</EXAMPLE>>
WITH params AS (SELECT 100 AS as_of_week, 100 * 168 AS as_of_h, 100 * 168 + 21 * 24 AS horizon_h),
due AS (
    SELECT m.pn,
           count(*)                     AS kit_lines,
           count(DISTINCT m.tail)       AS aircraft,
           sum(m.qty)                   AS qty_due,
           min(m.due_h) // 168          AS first_due_week,
           max(m.due_h) // 168          AS last_due_week
    FROM maintenance_schedule m CROSS JOIN params p
    WHERE m.notice_h <= p.as_of_h
      AND m.due_h >= p.as_of_h
      AND m.due_h < p.horizon_h
      AND m.station = 'AUH'
      AND m.check_type = 'A-check'
    GROUP BY m.pn
)
SELECT d.pn,
       pm.description,
       pm.part_class,
       d.kit_lines,
       d.aircraft,
       d.qty_due,
       d.first_due_week,
       d.last_due_week,
       s.on_hand                                                AS auh_on_hand,
       s.on_hand - d.qty_due                                    AS auh_after_kits,
       CASE WHEN s.on_hand < d.qty_due THEN 'SHORT' ELSE 'covered' END AS status
FROM due d
CROSS JOIN params p
JOIN part_master pm USING (pn)
LEFT JOIN stock_snapshots s ON s.pn = d.pn AND s.station = 'AUH' AND s.week = p.as_of_week - 1
ORDER BY (s.on_hand - d.qty_due), d.qty_due DESC, d.pn;
