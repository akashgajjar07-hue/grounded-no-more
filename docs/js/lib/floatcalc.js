// Float calculator maths — mirror of src/gnm/policy/analytic.py (tested in tests/test_floatcalc_mirror.py).
// Palm's theorem: pipeline X ~ Poisson(lambda * TAT). Availability P(X<S); EBO(S)=E[max(X-S,0)].

function lgamma(n) { // n is a non-negative integer here
  let s = 0;
  for (let i = 2; i <= n; i++) s += Math.log(i);
  return s;
}

export function poissonPmf(k, mu) {
  if (mu <= 0) return k === 0 ? 1 : 0;
  return Math.exp(k * Math.log(mu) - mu - lgamma(k));
}

export function poissonCdf(k, mu) {
  if (k < 0) return 0;
  let s = 0;
  for (let i = 0; i <= k; i++) s += poissonPmf(i, mu);
  return s;
}

export const pipelineMean = (ratePer30d, tatDays) => (ratePer30d / 30) * tatDays;
export const availability = (S, mu) => poissonCdf(S - 1, mu);

export function ebo(S, mu) {
  if (S <= 0) return mu;
  let tail = 0;
  for (let x = 0; x < S; x++) tail += (S - x) * poissonPmf(x, mu);
  return mu - S + tail;
}

export function floatCalc(ratePer30d, tatDays, spares, unitCostAed) {
  const mu = pipelineMean(ratePer30d, tatDays);
  const lam = ratePer30d / 30;
  return {
    pipeline_mean: mu,
    availability: availability(spares, mu),
    ebo: ebo(spares, mu),
    expected_wait_days: lam > 0 ? ebo(spares, mu) / lam : 0,
    capital_aed: spares * unitCostAed,
  };
}

export function compareLevers(ratePer30d, tatDays, spares, unitCostAed, tatCutDays, extraSpares, accelCostPerDayPerUnit) {
  const base = floatCalc(ratePer30d, tatDays, spares, unitCostAed);
  const more = floatCalc(ratePer30d, tatDays, spares + extraSpares, unitCostAed);
  const faster = floatCalc(ratePer30d, Math.max(tatDays - tatCutDays, 0), spares, unitCostAed);
  const annualRemovals = (ratePer30d * 365) / 30;
  return {
    base,
    extra_spares: { ...more, incremental_capital_aed: extraSpares * unitCostAed, incremental_annual_aed: 0 },
    tat_cut: { ...faster, incremental_capital_aed: 0, incremental_annual_aed: annualRemovals * tatCutDays * accelCostPerDayPerUnit },
  };
}

export function pmfSeries(mu, kMax) {
  const out = [];
  for (let k = 0; k <= kMax; k++) out.push({ k, p: poissonPmf(k, mu) });
  return out;
}
