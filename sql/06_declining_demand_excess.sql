-- Question: Which consumables and expendables show declining demand while the network keeps a lot of stock
--           (excess / obsolescence candidates)?
-- Assumptions:
--   * Demand = material_requests.qty (unconstrained demand) for part classes C and E.
--   * Year over year: recent = the last 52 weeks before the as-of hour 17,472, prior = the 52 weeks before that
--     (the Planner Action Centre rule; a 26/26 split missed the gradual PS3 trend).
--   * Network on-hand = sum of stock_snapshots.on_hand over all stations at week 103.
--   * Weeks of cover = on-hand / recent weekly usage (NULL = no recent demand at all, i.e. unlimited cover).
--   * Flag: recent < 75% of prior and cover > 26 weeks. PS3 (part_master.planted) should surface.
-- Provenance: SIMULATED history, ratios DERIVED.
-- Example output (from `python sql/run_all.py --update-examples`):
-- <<EXAMPLE>>
--         pn                              description part_class  prior_52w_qty  recent_52w_qty  recent_vs_prior  network_on_hand  weeks_cover_at_recent_rate  on_hand_value_aed planted
-- GN-49-E030                APU ignition exciter (WB)          E              3               0             0.00               10                         NaN            31336.0        
-- GN-24-E021 Remote power distribution unit card (WB)          E              8               3             0.38               12                       208.0            48910.0        
-- GN-28-E023                 Fuel quantity probe (WB)          E              6               3             0.50               12                       208.0            86936.0        
-- GN-38-E017          Water quantity transmitter (NB)          E             12               7             0.58                6                        44.6            34163.0        
-- GN-20-C040                     Self-locking nut kit          C           1489             934             0.63             1765                        98.3           238293.0     PS3
-- GN-34-E012         Total air temperature probe (NB)          E             19              13             0.68               11                        44.0           213637.0        
-- GN-32-E027            Brake temperature sensor (WB)          E              7               5             0.71               11                       114.4            88929.0        
-- (7 rows in total; full result in sql/results/06_declining_demand_excess.csv)
-- <</EXAMPLE>>
WITH params AS (SELECT 17472 AS as_of_h, 52 * 168 AS win_h),
usage AS (
    SELECT r.pn,
           sum(CASE WHEN r.need_h >= p.as_of_h - 2 * p.win_h AND r.need_h < p.as_of_h - p.win_h
                    THEN r.qty ELSE 0 END)                                  AS prior_52w_qty,
           sum(CASE WHEN r.need_h >= p.as_of_h - p.win_h AND r.need_h < p.as_of_h
                    THEN r.qty ELSE 0 END)                                  AS recent_52w_qty
    FROM material_requests r CROSS JOIN params p
    GROUP BY r.pn
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
       u.prior_52w_qty,
       u.recent_52w_qty,
       round(u.recent_52w_qty / nullif(u.prior_52w_qty, 0), 2)               AS recent_vs_prior,
       s.network_on_hand,
       round(s.network_on_hand / nullif(u.recent_52w_qty / 52.0, 0), 1)      AS weeks_cover_at_recent_rate,
       round(s.network_on_hand * pm.unit_cost_aed, 0)                        AS on_hand_value_aed,
       coalesce(pm.planted, '')                                              AS planted
FROM usage u
JOIN stock s USING (pn)
JOIN part_master pm USING (pn)
WHERE pm.part_class IN ('C', 'E')
  AND u.recent_52w_qty < 0.75 * u.prior_52w_qty
  AND (u.recent_52w_qty = 0 OR s.network_on_hand / (u.recent_52w_qty / 52.0) > 26)
ORDER BY recent_vs_prior, u.pn;
