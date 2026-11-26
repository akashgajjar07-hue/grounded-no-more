-- Question: Which part numbers, at which stations, drive the most material AOG (aircraft on ground) hours?
-- Assumptions:
--   * Source: aog_events (material-related downtime, already merged per aircraft by the simulator), weeks 0-103
--     of the v2 history under the legacy policy P0 ("OEM-recommended provisioning on quoted data").
--   * v2 counts downtime only when the part is late: from need + rectification window to fill + fitting/RTS.
--   * aog_events.pns is ';'-separated; an event's hours are split equally across its PNs
--     (same attribution rule as docs/data/parts.json aog_hours_hist_per_yr).
--   * Per-year figures divide the two-year history by 2.
--   * planted comes from part_master.planted (metadata), never from a hard-coded PN.
-- Provenance: SIMULATED history (fictional Falcon Hub Airways), aggregation DERIVED.
-- Example output (from `python sql/run_all.py --update-examples`):
-- <<EXAMPLE>>
--         pn                       description part_class station  aog_events  aog_hours  aog_hours_per_year  d0_no_stock_events  deadline_expired_events planted
-- GN-32-R014 Nose wheel steering actuator (NB)          R     BOM          14      266.0               133.0                  14                        0     PS1
-- GN-32-R014 Nose wheel steering actuator (NB)          R     CAI           9      206.0               103.0                   9                        0     PS1
-- GN-32-R014 Nose wheel steering actuator (NB)          R     AUH           9      162.0                81.0                   9                        0     PS1
-- GN-32-R015 Main wheel and tyre assembly (NB)          R     CAI           9      159.0                79.5                   9                        0        
-- GN-32-R014 Nose wheel steering actuator (NB)          R     JED           9      137.0                68.5                   9                        0     PS1
-- GN-27-R032   Aileron power control unit (WB)          R     LHR           6      114.0                57.0                   6                        0        
-- GN-35-E032    Crew quick-donning oxygen mask          E     AUH          14      114.0                57.0                  14                        0        
-- GN-27-R007        Aileron servo control (NB)          R     JED           4      111.0                55.5                   4                        0        
-- (20 rows in total; full result in sql/results/01_top_aog_drivers.csv)
-- <</EXAMPLE>>
WITH exploded AS (
    SELECT a.aog_id, a.station, a.trigger, a.hours,
           trim(p.pn) AS pn,
           len(string_split(a.pns, ';')) AS n_pns
    FROM aog_events a, unnest(string_split(a.pns, ';')) AS p(pn)
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
