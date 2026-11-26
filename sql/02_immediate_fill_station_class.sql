-- Question: What share of material requests is filled immediately from local stock, by station and part class
--           (C consumable, E expendable, R rotable), and how does the D0 subset fare?
-- Assumptions:
--   * Source: material_requests, weeks 0-103 under P0. immediate_fill is the simulator's flag
--     (request issued from the requesting station's own shelf at need time). Includes line usage, A-check kit
--     lines, unscheduled removals and wear-planned brake changes.
--   * D0/D3/D10 are hypothetical rectification windows (0/72/240 h). D3/D10 are simplified analogues of MEL
--     repair-interval categories B and C, not operator MEL decisions. Servicing fluids carry class NONE.
-- Provenance: SIMULATED history, aggregation DERIVED.
-- Example output (from `python sql/run_all.py --update-examples`):
-- <<EXAMPLE>>
-- station part_class  requests  filled_immediately  immediate_fill_rate  d0_requests  d0_immediate_fill_rate
--     AUH          C     18130               18130               1.0000            0                     NaN
--     AUH          E      1676                1595               0.9517          130                  0.8923
--     AUH          R      1548                1387               0.8960          355                  0.9099
--     BOM          C      4439                4439               1.0000            0                     NaN
--     BOM          E        43                  43               1.0000           31                  1.0000
--     BOM          R        47                  13               0.2766           39                  0.3333
--     CAI          C      3291                3290               0.9997            0                     NaN
--     CAI          E        34                  34               1.0000           28                  1.0000
-- (21 rows in total; full result in sql/results/02_immediate_fill_station_class.csv)
-- <</EXAMPLE>>
SELECT r.station,
       pm.part_class,
       count(*)                                                       AS requests,
       sum(CASE WHEN r.immediate_fill THEN 1 ELSE 0 END)              AS filled_immediately,
       round(avg(CASE WHEN r.immediate_fill THEN 1.0 ELSE 0.0 END), 4) AS immediate_fill_rate,
       sum(CASE WHEN r.deadline_class = 'D0' THEN 1 ELSE 0 END)       AS d0_requests,
       round(avg(CASE WHEN r.deadline_class = 'D0'
                      THEN CASE WHEN r.immediate_fill THEN 1.0 ELSE 0.0 END END), 4) AS d0_immediate_fill_rate
FROM material_requests r
JOIN part_master pm USING (pn)
GROUP BY r.station, pm.part_class
ORDER BY CASE WHEN r.station = 'AUH' THEN 0 ELSE 1 END, r.station, pm.part_class;
