-- Question: Where do D0 requests (0 h rectification window: the aircraft cannot depart without the part) arrive at
--           an outstation with no local serviceable stock, and how much material-related downtime follows?
--           PS1 (part_master.planted: the unscheduled D0 LRU that legacy provisioning holds none of at its
--           outstation) should come first.
-- Assumptions:
--   * Outstation = any station other than the AUH hub.
--   * "No local serviceable stock" = the request was not filled immediately from the station's shelf.
--   * AOG hours: aog_events at the same station that list the PN (';'-separated), split equally across listed PNs.
--   * p0_base_stock / p0_order_up_to = the legacy P0 target held at that station (policy_p0_stock_params).
-- Provenance: SIMULATED history, aggregation DERIVED.
-- Example output (from `python sql/run_all.py --update-examples`):
-- <<EXAMPLE>>
--         pn                       description part_class station  d0_requests  d0_without_local_stock  share_without_stock  aog_events  aog_hours  p0_base_stock  p0_order_up_to planted
-- GN-32-R014 Nose wheel steering actuator (NB)          R     BOM           14                      14                  1.0          14      266.0              0               0     PS1
-- GN-32-R014 Nose wheel steering actuator (NB)          R     CAI            9                       9                  1.0           9      206.0              0               0     PS1
-- GN-32-R015 Main wheel and tyre assembly (NB)          R     CAI            9                       9                  1.0           9      159.0              0               0        
-- GN-32-R014 Nose wheel steering actuator (NB)          R     JED            9                       9                  1.0           9      137.0              0               0     PS1
-- GN-27-R006       Elevator servo control (NB)          R     JED            8                       8                  1.0           8      104.0              0               0        
-- GN-27-R032   Aileron power control unit (WB)          R     LHR            6                       6                  1.0           6      114.0              0               0        
-- GN-32-R016 Nose wheel and tyre assembly (NB)          R     CAI            6                       6                  1.0           6       86.0              0               0        
-- GN-27-R031  Elevator power control unit (WB)          R     LHR            5                       5                  1.0           5       99.0              0               0        
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
           sum(a.hours / len(string_split(a.pns, ';'))) AS aog_hours
    FROM aog_events a, unnest(string_split(a.pns, ';')) AS p(pn)
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
