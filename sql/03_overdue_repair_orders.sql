-- Question: Which rotable units are stuck at the end of history: repair orders still open past the shop's quoted
--           due date, and condemned cores whose replacement purchase order is still open?
-- Assumptions:
--   * As-of time = end of week 103 = hour 17,472 (104 x 168 h).
--   * Overdue repair: no return yet, not condemned, quoted_due_h before the as-of time. Lateness is measured
--     against repair_orders.quoted_due_h, i.e. what the shop promised.
--   * Condemned core awaiting replacement: a CONDEMN inventory transaction (ref_id 'RO<n>') links the repair order
--     to the condemn_replacement PO for the same PN raised at the same hour; the PO is open at the as-of time.
--     weeks_late is NULL while that PO is still inside its quoted due date.
--   * Same rules as the Planner Action Centre types OVERDUE_REPAIR and CONDEMNED_AWAITING_REPLACEMENT.
--   * PS2 (planted situation 2, read from part_master.planted) is a long-TAT EU-vendor rotable. In v2 its planted
--     stuck unit was condemned, so it shows up as overdue repair orders plus a replacement PO, not as one RO.
-- Provenance: SIMULATED history, lateness DERIVED.
-- Example rows: 18
-- Example output (from `python sql/run_all.py --update-examples`):
-- <<EXAMPLE>>
--                 status  ro_id  po_id           serial         pn deadline_class     held_at  event_week  quoted_due_week  weeks_late  unit_cost_aed planted
--         overdue_repair   1466   <NA> GN-21-R025-S0030 GN-21-R025             D3 AUH_INHOUSE          81               93        10.7       122141.0        
--         overdue_repair   1625   <NA> GN-34-R018-S0121 GN-34-R018            D10   EU_VENDOR          90               99         4.1       171115.0     PS2
--         overdue_repair   1650   <NA> GN-21-R026-S0003 GN-21-R026            D10 AUH_INHOUSE          92              100         3.7       157905.0        
--         overdue_repair   1612   <NA> GN-27-R009-S0016 GN-27-R009             D3   EU_VENDOR          89              100         3.3       189077.0        
--         overdue_repair   1639   <NA> GN-34-R039-S0005 GN-34-R039             D3   EU_VENDOR          91              101         2.6       103557.0        
--         overdue_repair   1648   <NA> GN-34-R018-S0081 GN-34-R018            D10   EU_VENDOR          91              101         2.4       171115.0     PS2
--         overdue_repair   1605   <NA> GN-28-R010-S0074 GN-28-R010             D3   EU_VENDOR          88              102         1.7       171818.0        
--         overdue_repair   1635   <NA> GN-27-R009-S0041 GN-27-R009             D3   EU_VENDOR          90              102         1.7       189077.0        
--         overdue_repair   1668   <NA> GN-34-R018-S0149 GN-34-R018            D10   EU_VENDOR          93              102         1.3       171115.0     PS2
--         overdue_repair   1690   <NA> GN-34-R019-S0076 GN-34-R019             D3   EU_VENDOR          94              103         0.9       190848.0        
--         overdue_repair   1717   <NA> GN-28-R033-S0044 GN-28-R033             D3   EU_VENDOR          96              103         0.8       212879.0        
--         overdue_repair   1784   <NA> GN-29-R012-S0010 GN-29-R012            D10 AUH_INHOUSE         100              103         0.8       152096.0        
--         overdue_repair   1642   <NA> GN-32-R036-S0037 GN-32-R036             D0   EU_VENDOR          91              103         0.4       270041.0        
--         overdue_repair   1638   <NA> GN-32-R013-S0014 GN-32-R013             D0   EU_VENDOR          91              103         0.3       149600.0        
--         overdue_repair   1687   <NA> GN-27-R032-S0005 GN-27-R032             D0   EU_VENDOR          93              103         0.3       169624.0        
-- replacement_po_overdue   1528    418 GN-34-R018-S0102 GN-34-R018            D10         AUH          85               95         8.2       171115.0     PS2
-- replacement_po_overdue   1510    410 GN-32-R013-S0111 GN-32-R013             D0         AUH          84              103         0.2       149600.0        
--    replacement_po_open   1502    403 GN-24-R004-S0011 GN-24-R004             D3         AUH          83              105         NaN       332910.0        
-- (26 rows in total; full result in sql/results/03_overdue_repair_orders.csv)
-- <</EXAMPLE>>
WITH params AS (SELECT 17472 AS as_of_h),
overdue AS (
    SELECT 'overdue_repair'                                       AS status,
           ro.ro_id,
           NULL::BIGINT                                           AS po_id,
           ro.serial,
           ro.pn,
           ro.shop                                                AS held_at,
           ro.removed_h // 168                                    AS event_week,
           ro.quoted_due_h // 168                                 AS quoted_due_week,
           round((p.as_of_h - ro.quoted_due_h) / 168.0, 1)        AS weeks_late
    FROM repair_orders ro CROSS JOIN params p
    WHERE ro.return_h IS NULL AND NOT ro.condemned AND ro.quoted_due_h < p.as_of_h
),
replacement AS (
    SELECT CASE WHEN po.due_h < p.as_of_h THEN 'replacement_po_overdue'
                ELSE 'replacement_po_open' END                    AS status,
           ro.ro_id,
           po.po_id,
           ro.serial,
           ro.pn,
           po.station                                             AS held_at,
           po.order_h // 168                                      AS event_week,
           po.due_h // 168                                        AS quoted_due_week,
           CASE WHEN po.due_h < p.as_of_h
                THEN round((p.as_of_h - po.due_h) / 168.0, 1) END AS weeks_late
    FROM repair_orders ro
    CROSS JOIN params p
    JOIN inventory_transactions t
      ON t.txn_type = 'CONDEMN' AND t.ref_id = 'RO' || ro.ro_id::VARCHAR
    JOIN purchase_orders po
      ON po.pn = ro.pn AND po.reason = 'condemn_replacement' AND po.order_h = t.t_h
    WHERE ro.condemned
      AND po.order_h < p.as_of_h
      AND (po.receipt_h IS NULL OR po.receipt_h >= p.as_of_h)
)
SELECT x.status,
       x.ro_id,
       x.po_id,
       x.serial,
       x.pn,
       pm.deadline_class,
       x.held_at,
       x.event_week,
       x.quoted_due_week,
       x.weeks_late,
       round(pm.unit_cost_aed, 0)                                 AS unit_cost_aed,
       coalesce(pm.planted, '')                                   AS planted
FROM (SELECT * FROM overdue UNION ALL SELECT * FROM replacement) x
JOIN part_master pm USING (pn)
ORDER BY CASE x.status WHEN 'overdue_repair' THEN 0 WHEN 'replacement_po_overdue' THEN 1 ELSE 2 END,
         x.weeks_late DESC NULLS LAST, x.ro_id;
