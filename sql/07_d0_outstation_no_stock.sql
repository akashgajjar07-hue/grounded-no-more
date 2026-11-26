-- Question: Where do D0 (no-go) requests arrive at an outstation with no local serviceable stock, and how many
--           AOG hours follow? (PS1: the carbon brake GN-32-R014 at BOM.)
-- Assumptions:
--   * Outstation = any station other than the AUH hub.
--   * "No local serviceable stock" = the request was not filled immediately from the station's shelf.
--   * AOG hours: aog_events at the same station that list the PN, split equally across listed PNs.
--   * p0_base_stock / p0_order_up_to = the legacy P0 target held at that station (policy_p0_stock_params).
-- Provenance: SIMULATED history, aggregation DERIVED.
-- Example output (from `python sql/run_all.py`):
-- <<EXAMPLE>>
--         pn           description part_class station  d0_requests  d0_without_local_stock  share_without_stock  aog_events  aog_hours  p0_base_stock  p0_order_up_to planted
-- GN-32-R014 Carbon brake assembly          R     BOM           16                      16                1.000          16      144.0              0               0     PS1
-- GN-32-R014 Carbon brake assembly          R     CAI           10                      10                1.000           9       99.0              0               0     PS1
-- GN-32-R014 Carbon brake assembly          R     JED           10                      10                1.000          10       90.0              0               0     PS1
-- GN-28-R031       Fuel boost pump          R     FRA            6                       6                1.000           6      119.0              0               0     PS2
-- GN-36-R007       Bleed air valve          R     FRA            6                       6                1.000           6       84.0              0               0        
-- GN-36-R007       Bleed air valve          R     LHR            5                       5                1.000           5       80.0              0               0        
-- GN-32-R014 Carbon brake assembly          R     SIN            5                       5                1.000           5       65.0              0               0     PS1
-- GN-28-R031       Fuel boost pump          R     CAI           26                       5                0.192           5       55.0              1               0     PS2
-- (20 rows in total; full result in sql/results/07_d0_outstation_no_stock.csv)
-- <</EXAMPLE>>
WITH d0 AS (
    SELECT pn, station,
           count(*)                                              AS d0_requests,
           sum(CASE WHEN NOT immediate_fill THEN 1 ELSE 0 END)   AS d0_without_local_stock
    FROM material_requests
    WHERE deadline_class = 'D0' AND station <> 'AUH'
    GROUP BY pn, station
),
aog AS (
    SELECT trim(p.pn) AS pn, a.station,
           count(*) AS aog_events,
           sum(a.hours / len(string_split(a.pns, ','))) AS aog_hours
    FROM aog_events a, unnest(string_split(a.pns, ',')) AS p(pn)
    WHERE a.station <> 'AUH'
    GROUP BY ALL
)
SELECT d.pn,
       pm.description,
       pm.part_class,
       d.station,
       d.d0_requests,
       d.d0_without_local_stock,
       round(d.d0_without_local_stock / d.d0_requests, 3)            AS share_without_stock,
       coalesce(a.aog_events, 0)                                     AS aog_events,
       round(coalesce(a.aog_hours, 0), 1)                            AS aog_hours,
       sp.base_stock                                                 AS p0_base_stock,
       sp.order_up_to_S                                              AS p0_order_up_to,
       coalesce(pm.planted, '')                                      AS planted
FROM d0 d
JOIN part_master pm USING (pn)
LEFT JOIN aog a USING (pn, station)
LEFT JOIN policy_p0_stock_params sp USING (pn, station)
WHERE d.d0_without_local_stock > 0
ORDER BY d.d0_without_local_stock DESC, aog_hours DESC, d.pn, d.station
LIMIT 20;
