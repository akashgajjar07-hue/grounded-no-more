-- Question: Which consumables and expendables show declining demand while the network keeps a lot of stock
--           (excess / obsolescence candidates)?
-- Assumptions:
--   * Demand = material_requests.qty (unconstrained demand) for part classes C and E.
--   * Recent = weeks 78-103 (26 weeks), prior = weeks 52-77 (26 weeks).
--   * Network on-hand = sum of stock_snapshots.on_hand over all stations at week 103.
--   * Weeks of cover = on-hand / recent weekly usage.
--   * Flag: recent < 75% of prior and cover > 26 weeks (the planner action rule). PS3 (GN-21-C010) should surface.
-- Provenance: SIMULATED history, ratios DERIVED.
-- Example output (from `python sql/run_all.py`):
-- <<EXAMPLE>>
--         pn                  description part_class  prior_26w_qty  recent_26w_qty  recent_vs_prior  network_on_hand  weeks_cover_at_recent_rate  on_hand_value_aed planted
-- GN-24-E013          Current transformer          E             12               4             0.33               12                        78.0            72155.0        
-- GN-49-E022 APU igniter plug – variant B          E              8               4             0.50                8                        52.0            20193.0        
-- GN-34-C019   Antenna gasket – variant B          C             47              24             0.51               39                        42.3             6314.0        
-- GN-27-E030        Slat proximity sensor          E             15               8             0.53               15                        48.8            77158.0        
-- GN-21-C010          Duct clamp seal kit          C            506             341             0.67              614                        46.8            42434.0     PS3
-- GN-32-E021        Gear proximity switch          E              6               4             0.67                9                        58.5             5303.0        
-- GN-49-E032 APU igniter plug – variant C          E              3               2             0.67                8                       104.0            45962.0        
-- (7 rows in total; full result in sql/results/06_declining_demand_excess.csv)
-- <</EXAMPLE>>
WITH usage AS (
    SELECT pn,
           sum(CASE WHEN week BETWEEN 52 AND 77 THEN qty ELSE 0 END)  AS prior_26w_qty,
           sum(CASE WHEN week BETWEEN 78 AND 103 THEN qty ELSE 0 END) AS recent_26w_qty
    FROM material_requests
    GROUP BY pn
),
stock AS (
    SELECT pn, sum(on_hand) AS network_on_hand
    FROM stock_snapshots
    WHERE week = 103
    GROUP BY pn
)
SELECT u.pn,
       pm.description,
       pm.part_class,
       u.prior_26w_qty,
       u.recent_26w_qty,
       round(u.recent_26w_qty / nullif(u.prior_26w_qty, 0), 2)               AS recent_vs_prior,
       s.network_on_hand,
       round(s.network_on_hand / nullif(u.recent_26w_qty / 26.0, 0), 1)      AS weeks_cover_at_recent_rate,
       round(s.network_on_hand * pm.unit_cost_aed, 0)                        AS on_hand_value_aed,
       coalesce(pm.planted, '')                                              AS planted
FROM usage u
JOIN stock s USING (pn)
JOIN part_master pm USING (pn)
WHERE pm.part_class IN ('C', 'E')
  AND u.recent_26w_qty < 0.75 * u.prior_26w_qty
  AND s.network_on_hand / nullif(u.recent_26w_qty / 26.0, 0) > 26
ORDER BY recent_vs_prior, u.pn;
