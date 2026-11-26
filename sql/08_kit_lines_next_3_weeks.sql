-- Question: Which A-check kit lines fall due in the next 3 weeks, and does AUH hold enough stock to cover them?
-- Assumptions:
--   * The history ends at week 103 and contains no check scheduled after it, so the query is run "as of"
--     the start of week 100 (hour 16,800) and looks 21 days ahead (weeks 100-102). Change as_of_week to re-run.
--   * Only lines already notified at the as-of time (notice_h <= as_of_h) are counted: a planner cannot see more.
--   * Kits are drawn at AUH (all A-checks run at the hub). Cover is compared with the AUH on-hand in the week
--     before the as-of week (stock_snapshots), ignoring line usage and inbound POs, so it is a first screen only.
-- Provenance: SIMULATED history, cover DERIVED.
-- Example output (from `python sql/run_all.py`):
-- <<EXAMPLE>>
--         pn                          description part_class  kit_lines  aircraft  qty_due  first_due_week  last_due_week  auh_on_hand  auh_after_kits  status
-- GN-34-C023  Connector backshell kit – variant B          C          6         6       15             100            102            0             -15   SHORT
-- GN-24-C020                           Fuse (5 A)          C          2         2        5             100            102            9               4 covered
-- GN-21-C002     Recirculation air filter element          C          5         5       10             100            102           17               7 covered
-- GN-29-C028 Hydraulic filter element – variant B          C          7         7       14             100            102           22               8 covered
-- GN-33-C030                  Cabin lighting lamp          C          7         7       20             100            102           29               9 covered
-- GN-33-C025                   Reading light lamp          C          9         9       26             100            101           38              12 covered
-- GN-30-C037             Rain repellent cartridge          C          2         2        5             100            101           18              13 covered
-- GN-27-C021   Grease cartridge (flight controls)          C          7         7       17             100            101           32              15 covered
-- (29 rows in total; full result in sql/results/08_kit_lines_next_3_weeks.csv)
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
