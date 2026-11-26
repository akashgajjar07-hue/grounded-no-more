-- Question: Which part numbers, at which stations, drive the most material AOG (aircraft on ground) hours?
-- Assumptions:
--   * Source: aog_events (groundings already merged per aircraft by the simulator), weeks 0-103 under policy P0.
--   * aog_events.pns can list several PNs; an event's hours are split equally across its PNs
--     (same attribution rule as docs/data/parts.json aog_hours_hist_per_yr).
--   * Per-year figures divide the two-year history by 2.
-- Provenance: SIMULATED history (fictional Falcon Hub Airways), aggregation DERIVED.
-- Example output (from `python sql/run_all.py`):
-- <<EXAMPLE>>
--         pn                         description part_class station  aog_events  aog_hours  aog_hours_per_year  d0_no_stock_events  deadline_expired_events planted
-- GN-34-C023 Connector backshell kit – variant B          C     AUH          20      921.0               460.5                  20                        0        
-- GN-36-R024           Bleed monitoring computer          R     AUH           7      336.0               168.0                   0                        7        
-- GN-34-R012           Weather radar transceiver          R     AUH           7      331.0               165.5                   0                        7        
-- GN-49-R038               APU fuel control unit          R     AUH           3      318.0               159.0                   3                        0        
-- GN-36-R007                     Bleed air valve          R     AUH           2      240.0               120.0                   2                        0        
-- GN-29-C015                     Backup ring kit          C     JED           4      215.0               107.5                   0                        4        
-- GN-29-C015                     Backup ring kit          C     LHR           4      194.0                97.0                   0                        4        
-- GN-29-R005        Engine-driven hydraulic pump          R     AUH           6      180.0                90.0                   0                        6        
-- (20 rows in total; full result in sql/results/01_top_aog_drivers.csv)
-- <</EXAMPLE>>
WITH exploded AS (
    SELECT a.aog_id, a.station, a.trigger, a.hours,
           trim(p.pn) AS pn,
           len(string_split(a.pns, ',')) AS n_pns
    FROM aog_events a, unnest(string_split(a.pns, ',')) AS p(pn)
)
SELECT e.pn,
       pm.description,
       pm.part_class,
       e.station,
       count(*)                                           AS aog_events,
       round(sum(e.hours / e.n_pns), 1)                   AS aog_hours,
       round(sum(e.hours / e.n_pns) / 2, 1)               AS aog_hours_per_year,
       sum(CASE WHEN e.trigger = 'D0_no_stock' THEN 1 ELSE 0 END)      AS d0_no_stock_events,
       sum(CASE WHEN e.trigger = 'deadline_expired' THEN 1 ELSE 0 END) AS deadline_expired_events,
       coalesce(pm.planted, '')                           AS planted
FROM exploded e
JOIN part_master pm USING (pn)
GROUP BY ALL
ORDER BY aog_hours DESC, e.pn, e.station
LIMIT 20;
