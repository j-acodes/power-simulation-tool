/**
 * Human-readable property labels, shared by the palette catalogue preview,
 * custom-equipment forms and the inspector — always "Name (symbol, unit)",
 * never a bare symbol.
 */
export const LABEL = {
  brand: 'Brand',
  sRatedKva: 'Rated power S (kVA)',
  ukPercent: 'Short-circuit voltage uk (%)',
  pkKw: 'Load losses Pk (kW)',
  p0Kw: 'No-load losses P0 (kW)',
  i0Percent: 'No-load current i0 (%)',
  hvKv: 'HV side (kV)',
  lvKv: 'LV side (kV)',
  lengthM: 'Length (m)',
  crossSectionMm2: 'Cross-section (mm²)',
  ratedCurrentA: 'Rated current (A)',
  currentA: 'Current (A)',
  utilizationPct: 'Utilization (%)',
  powerFactor: 'Power factor',
  activePowerKw: 'Active power P (kW)',
  activePowerMw: 'Active power P (MW)',
  reactivePowerKvar: 'Reactive power Q (kvar)',
  reactivePowerMvar: 'Reactive power Q (Mvar)',
  apparentPowerKva: 'Apparent power S (kVA)',
  apparentPowerMva: 'Apparent power S (MVA)',
} as const
