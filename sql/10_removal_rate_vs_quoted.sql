-- Question: For which rotables and expendables is the vendor-quoted MTBUR (mean time between unscheduled
--           removals) most optimistic compared with what the fleet actually experienced?
-- Assumptions:
--   * Exposure = sum over legs of installed qty per aircraft x FH (driver FH) or FC (driver FC),
--     from flight_exposure x part_applicability, weeks 0-103.
--   * Observed MTBUR = exposure / unscheduled removals (removal_events). A simple MLE, no prior and no CI;
--     the planning pipeline uses a Gamma-Poisson posterior instead (inventory-policy note), so values differ slightly.
--   * Only PNs with at least 10 removals. quoted_vs_observed > 1 means the quote is optimistic.
-- Provenance: SIMULATED history; quoted MTBUR is SIMULATED master data; ratio DERIVED.
-- Example output (from `python sql/run_all.py`):
-- <<EXAMPLE>>
--         pn                    description part_class driver  removals  exposure  mtbur_quoted  mtbur_observed  quoted_vs_observed planted
-- GN-29-E007                 Hydraulic fuse          E     FH        68 1106125.0       43014.0         16267.0                2.64        
-- GN-34-R022    Radio altimeter transceiver          R     FH        26  537598.0       52288.0         20677.0                2.53        
-- GN-24-R017     Transformer rectifier unit          R     FH        34  721952.0       53075.0         21234.0                2.50        
-- GN-32-E009         Wheel speed transducer          E     FC        78  290166.0        9163.0          3720.0                2.46        
-- GN-34-R012      Weather radar transceiver          R     FH        45  368708.0       19877.0          8194.0                2.43        
-- GN-32-R018            Main wheel assembly          R     FC        30  205056.0       15528.0          6835.0                2.27        
-- GN-32-R014          Carbon brake assembly          R     FC        87  410112.0       10500.0          4714.0                2.23     PS1
-- GN-21-E029 Ram air inlet actuator rod end          E     FH        54  368708.0       14061.0          6828.0                2.06        
-- (15 rows in total; full result in sql/results/10_removal_rate_vs_quoted.csv)
-- <</EXAMPLE>>
WITH exposure AS (
    SELECT pa.pn,
           sum(pa.qty_per_aircraft * CASE WHEN pm.driver = 'FH' THEN fe.fh ELSE fe.fc END) AS exposure
    FROM flight_exposure fe
    JOIN aircraft_master am USING (tail)
    JOIN part_applicability pa ON pa.archetype = am.archetype
    JOIN part_master pm ON pm.pn = pa.pn
    WHERE pm.part_class IN ('R', 'E') AND pm.driver IN ('FH', 'FC')
    GROUP BY pa.pn
),
removals AS (
    SELECT pn, count(*) AS removals FROM removal_events GROUP BY pn
)
SELECT pm.pn,
       pm.description,
       pm.part_class,
       pm.driver,
       r.removals,
       round(e.exposure, 0)                                 AS exposure,
       round(pm.mtbur_quoted, 0)                            AS mtbur_quoted,
       round(e.exposure / r.removals, 0)                    AS mtbur_observed,
       round(pm.mtbur_quoted / (e.exposure / r.removals), 2) AS quoted_vs_observed,
       coalesce(pm.planted, '')                             AS planted
FROM exposure e
JOIN removals r USING (pn)
JOIN part_master pm USING (pn)
WHERE r.removals >= 10
ORDER BY quoted_vs_observed DESC
LIMIT 15;
