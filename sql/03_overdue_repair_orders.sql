-- Question: Which repair orders are still open past the shop's quoted due date at the end of history,
--           and how late are they?
-- Assumptions:
--   * As-of time = end of week 103 = hour 17,472 (104 x 168 h).
--   * Open = no return yet and not condemned (condemned ROs close without a return).
--   * Lateness is measured against repair_orders.quoted_due_h, i.e. what the shop promised.
--   * PS2 (planted situation 2) is RO 1564, GN-28-R031 at EU_VENDOR, removed week 84, quoted due week 93.
-- Provenance: SIMULATED history, lateness DERIVED.
-- Example output (from `python sql/run_all.py`):
-- <<EXAMPLE>>
--  ro_id           serial         pn deadline_class        shop  removed_week  quoted_due_week  quoted_days_in_shop  days_in_shop_so_far  weeks_late  unit_cost_aed planted
--   1564 GN-28-R031-S0159 GN-28-R031             D0   EU_VENDOR            84               93                 64.0                136.0        10.3        55687.0     PS2
--   1626 GN-32-R019-S0053 GN-32-R019             D3   EU_VENDOR            87               94                 49.1                112.8         9.1        22903.0        
--   1577 GN-36-R010-S0133 GN-36-R010            D10 AUH_INHOUSE            85               95                 71.8                132.9         8.7       184971.0        
--   1607 GN-21-R002-S0015 GN-21-R002            D10 AUH_INHOUSE            85               95                 60.2                121.0         8.7        26869.0        
--   1604 GN-28-R031-S0092 GN-28-R031             D0   EU_VENDOR            86               95                 64.0                121.9         8.3        55687.0     PS2
--   1635 GN-24-R039-S0025 GN-24-R039            D10 AUH_INHOUSE            88               98                 67.2                108.1         5.8        17143.0        
--   1677 GN-29-R028-S0094 GN-29-R028            D10 AUH_INHOUSE            92               98                 43.2                 82.4         5.6        17356.0        
--   1638 GN-34-R001-S0086 GN-34-R001            D10   EU_VENDOR            88               98                 65.6                104.1         5.5        73798.0        
-- (33 rows in total; full result in sql/results/03_overdue_repair_orders.csv)
-- <</EXAMPLE>>
WITH params AS (SELECT 17472 AS as_of_h)
SELECT ro.ro_id,
       ro.serial,
       ro.pn,
       pm.deadline_class,
       ro.shop,
       ro.removed_h // 168                                    AS removed_week,
       ro.quoted_due_h // 168                                 AS quoted_due_week,
       round((ro.quoted_due_h - ro.shop_in_h) / 24.0, 1)      AS quoted_days_in_shop,
       round((p.as_of_h - ro.shop_in_h) / 24.0, 1)            AS days_in_shop_so_far,
       round((p.as_of_h - ro.quoted_due_h) / 168.0, 1)        AS weeks_late,
       round(pm.unit_cost_aed, 0)                             AS unit_cost_aed,
       coalesce(pm.planted, '')                               AS planted
FROM repair_orders ro
CROSS JOIN params p
JOIN part_master pm USING (pn)
WHERE ro.return_h IS NULL
  AND NOT ro.condemned
  AND ro.quoted_due_h < p.as_of_h
ORDER BY weeks_late DESC, ro.ro_id;
