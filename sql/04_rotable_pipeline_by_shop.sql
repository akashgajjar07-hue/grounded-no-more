-- Question: Where is the rotable repair pipeline right now, by repair shop: removed and awaiting shipment,
--           in transit to the shop, in repair, and in transit back to AUH? What is it worth?
-- Assumptions:
--   * Uses the open (until_h IS NULL) row of serialised_components, i.e. each serial's state at the end of week 103.
--   * IN_TRANSIT location is 'FROM>TO'; a leg leaving a shop is a return, a leg arriving at a shop is inbound.
--   * REMOVED serials are attributed to the PN's repair_shop in part_master.
--   * Value = unit_cost_aed (replacement value, not book value).
-- Provenance: SIMULATED history, aggregation DERIVED.
-- Example output (from `python sql/run_all.py`):
-- <<EXAMPLE>>
--        shop  awaiting_shipment  in_transit_to_shop  in_repair  in_transit_to_auh  pipeline_units  pns  pipeline_value_aed
-- AUH_INHOUSE                  0                   0         81                  0              81   19          10332714.0
--   EU_VENDOR                  4                   0         33                  3              40   10           2899565.0
-- (2 rows in total; full result in sql/results/04_rotable_pipeline_by_shop.csv)
-- <</EXAMPLE>>
WITH cur AS (
    SELECT sc.serial, sc.pn, sc.state, sc.location, pm.repair_shop, pm.unit_cost_aed
    FROM serialised_components sc
    JOIN part_master pm USING (pn)
    WHERE sc.until_h IS NULL
      AND sc.state IN ('REMOVED', 'IN_TRANSIT', 'IN_REPAIR')
),
tagged AS (
    SELECT *,
           CASE
             WHEN state = 'IN_REPAIR' THEN location
             WHEN state = 'IN_TRANSIT' AND split_part(location, '>', 1) IN ('AUH_INHOUSE', 'EU_VENDOR')
                  THEN split_part(location, '>', 1)
             WHEN state = 'IN_TRANSIT' AND split_part(location, '>', 2) IN ('AUH_INHOUSE', 'EU_VENDOR')
                  THEN split_part(location, '>', 2)
             ELSE repair_shop
           END AS shop,
           CASE
             WHEN state = 'IN_REPAIR' THEN 'in_repair'
             WHEN state = 'REMOVED' THEN 'awaiting_shipment'
             WHEN split_part(location, '>', 1) IN ('AUH_INHOUSE', 'EU_VENDOR') THEN 'returning'
             WHEN split_part(location, '>', 2) IN ('AUH_INHOUSE', 'EU_VENDOR') THEN 'to_shop'
             ELSE 'station_transfer'
           END AS bucket
    FROM cur
)
SELECT shop,
       sum(CASE WHEN bucket = 'awaiting_shipment' THEN 1 ELSE 0 END) AS awaiting_shipment,
       sum(CASE WHEN bucket = 'to_shop' THEN 1 ELSE 0 END)           AS in_transit_to_shop,
       sum(CASE WHEN bucket = 'in_repair' THEN 1 ELSE 0 END)         AS in_repair,
       sum(CASE WHEN bucket = 'returning' THEN 1 ELSE 0 END)         AS in_transit_to_auh,
       count(*)                                                      AS pipeline_units,
       count(DISTINCT pn)                                            AS pns,
       round(sum(unit_cost_aed), 0)                                  AS pipeline_value_aed
FROM tagged
WHERE bucket <> 'station_transfer'
GROUP BY shop
ORDER BY pipeline_units DESC;
