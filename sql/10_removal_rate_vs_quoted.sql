-- Question: For which rotables and expendables is the vendor-quoted MTBUR (mean time between unscheduled
--           removals) most optimistic compared with what the fleet actually experienced?
-- Assumptions:
--   * Unscheduled-removal parts only: the wear-planned carbon brakes (part_master.removal_mode) are planned
--     changes, not unscheduled removals, and are excluded.
--   * Exposure = sum over legs of installed qty per aircraft x FH (driver FH) or FC (driver FC),
--     from flight_exposure x part_applicability, weeks 0-103.
--   * Observed MTBUR = exposure / removals (removal_events), NFF removals included because they still consume a
--     spare. A simple MLE, no prior and no CI; the planning pipeline uses a gamma-Poisson posterior instead
--     (inventory-policy note), so values differ slightly.
--   * Only PNs with at least 10 removals. quoted_vs_observed > 1 means the quote is optimistic.
-- Provenance: SIMULATED history; quoted MTBUR is SIMULATED master data; ratio DERIVED.
-- Example output (from `python sql/run_all.py --update-examples`):
-- <<EXAMPLE>>
--         pn                       description part_class driver  removals  exposure  mtbur_quoted  mtbur_observed  quoted_vs_observed planted
-- GN-32-R014 Nose wheel steering actuator (NB)          R     FC        56   74158.0        3250.0          1324.0                2.45     PS1
-- GN-21-E002      Pack outlet check valve (NB)          E     FH        38  368708.0       22564.0          9703.0                2.33        
-- GN-21-R001      Pack flow control valve (NB)          R     FH        24  368708.0       31795.0         15363.0                2.07        
-- GN-32-E010     Brake temperature sensor (NB)          E     FC        60  296632.0        8370.0          4944.0                1.69        
-- GN-33-E033      Emergency light battery pack          E     FH       249 2795019.0       18218.0         11225.0                1.62     PS4
-- GN-32-R015 Main wheel and tyre assembly (NB)          R     FC        75  296632.0        6332.0          3955.0                1.60        
-- GN-27-R008        Spoiler servo control (NB)          R     FH       101 1843541.0       29025.0         18253.0                1.59        
-- GN-34-R021                  Pitot probe (NB)          R     FH       112  553062.0        7818.0          4938.0                1.58        
-- (15 rows in total; full result in sql/results/10_removal_rate_vs_quoted.csv)
-- <</EXAMPLE>>
WITH exposure AS (
    SELECT pa.pn,
           sum(pa.qty_per_aircraft * CASE WHEN pm.driver = 'FH' THEN fe.fh ELSE fe.fc END) AS exposure
    FROM flight_exposure fe
    JOIN aircraft_master am USING (tail)
    JOIN part_applicability pa ON pa.archetype = am.archetype
    JOIN part_master pm ON pm.pn = pa.pn
    WHERE pm.part_class IN ('R', 'E') AND pm.driver IN ('FH', 'FC') AND pm.removal_mode = 'unscheduled'
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
