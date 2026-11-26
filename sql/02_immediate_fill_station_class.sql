-- Question: What share of material requests is filled immediately from local stock, by station and part class
--           (C consumable, E expendable, R rotable), and how does the D0 (no-go) subset fare?
-- Assumptions:
--   * Source: material_requests, weeks 0-103 under P0. immediate_fill is the simulator's flag
--     (request issued from the requesting station's own shelf at need time).
--   * D0/D3/D10 are hypothetical simulation deadline classes, not MEL categories.
-- Provenance: SIMULATED history, aggregation DERIVED.
-- Example output (from `python sql/run_all.py`):
-- <<EXAMPLE>>
-- station part_class  requests  filled_immediately  immediate_fill_rate  d0_requests  d0_immediate_fill_rate
--     AUH          C     17763               16969               0.9553          375                  0.9440
--     AUH          E      2161                1708               0.7904           25                  0.8800
--     AUH          R      1523                1387               0.9107          147                  0.9592
--     BOM          C      4067                4062               0.9988           68                  1.0000
--     BOM          E        25                  25               1.0000            3                  1.0000
--     BOM          R        52                  17               0.3269           42                  0.4048
--     CAI          C      3035                3035               1.0000           46                  1.0000
--     CAI          E        30                  30               1.0000            9                  1.0000
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
