/**
 * TS mirror of the diagram JSON schema (see powertool/graph.py module docstring)
 * and of the /api/solve response (SolveResponse in backend/schemas.py, built by
 * powertool.graph.map_results). Shapes are taken from tests/test_graph.py
 * fixtures, not invented — keep this file in sync with graph.py if either
 * changes.
 */

export type NodeKind = 'poc' | 'hv_tx' | 'busbar' | 'station' | 'aux'
/** Which fleet a station or busbar belongs to — mirrors FLEET_KINDS in
 *  powertool/graph.py. Absent props read as 'pv', the pre-hybrid default. */
export type FleetKind = 'pv' | 'bess'
/** The set of fleet kinds a design is permitted to contain — declared at
 *  creation, authoritative over the diagram, changed only by cloning. Mirrors
 *  Technology in backend/schemas.py. See docs/adr/0002-technology-declared-not-derived.md
 *  and CONTEXT.md's Technology entry — never "project type". */
export type Technology = 'pv' | 'bess' | 'hybrid'
export type Tier = 'lv' | 'mv' | 'hv'

// --- diagram (canvas payload) ------------------------------------------------

/** Props are permissive (server-side parsing ignores unknown keys) — kept as a
 * plain record rather than a kind-keyed union so the editor can read/write
 * without a discriminated-union dance. Inspector.tsx knows which keys apply
 * per kind. */
export type NodeProps = Record<string, unknown>

export interface DiagramNode {
  id: string
  kind: NodeKind
  x: number
  y: number
  props: NodeProps
}

export type Sizing = { mode: 'auto' } | { mode: 'forced'; cable: string }

export interface DiagramEdge {
  id: string
  source: string
  target: string
  tier: Tier
  length_m?: number
  sizing: Sizing
}

export interface TierSettings {
  lv_kv: number
  mv_kv: number
  hv_kv: number | null // null -> MV interconnection, no MV/HV transformer
}

/** One fleet's compliance figures. Emitted for every design, single-fleet
 *  included, so compliance has one shape to read rather than one per plant. */
export interface BranchSummary {
  kind: FleetKind
  p_inv_kw: number
  q_inv_kvar: number
  s_inv_kva: number
  pf_inv: number
  p_inv_refined_kw: number
  q_inv_refined_kvar: number
  s_inv_refined_kva: number
  correction_factor: number
  p_poc_target_kw: number | null
  p_poc_delivered_kw: number
  p_poc_refined_delivered_kw: number | null
  n_stations: number
  n_circuits: number
  circuit_sizes: number[]
  s_fleet_kva: number
  fleet_loading: number
  loading_ok: boolean
  max_loading: number
  /** Container auxiliaries this fleet needs supplied. Reported, never sized
   *  against: they are fed separately, never by the PCS. */
  bess_aux_p_kw: number
  bess_aux_q_kvar: number
  /** BESS only; null for a PV fleet, and null when no discharge duration is
   *  set — the energy gate then has nothing to judge against. */
  containers: number | null
  e_delivered_kwh: number | null
  e_required_kwh: number | null
  energy_ok: boolean | null
}

export interface RuleSettings {
  max_utilization: number
  collection_loss_pct: number
  export_loss_pct_per_km: number
  max_circuit_current_a: number
  /** Plant-wide fleet loading limit. */
  max_loading?: number
  /** Per-fleet overrides; each falls back to `max_loading` when unset. */
  max_loading_pv?: number
  max_loading_bess?: number
  /** Discharge duration [h]. Restricted to the durations available among the
   *  solutions paired with every drawn BESS station's own station
   *  transformer; unset means the energy gate does not apply. */
  discharge_hours?: number
  /** The ambient a design sizes its transformer stations against — see
   *  ADR-0004 and CONTEXT.md's "AC power at ambient" entry. A fixed choice
   *  (never a free number): unset means 40, matching every design saved
   *  before this setting existed. */
  ambient_temp_c?: 30 | 40
}

export interface DiagramSettings {
  tiers: TierSettings
  rules: RuleSettings
}

export interface Diagram {
  schema_version: 1
  settings: DiagramSettings
  nodes: DiagramNode[]
  edges: DiagramEdge[]
}

// --- /api/solve response ----------------------------------------------------

/** One validation problem (from validate_graph) or result warning (from
 * map_results), pointing at the offending canvas element. */
export interface Issue {
  code: string
  message: string
  node_id: string | null
  edge_id: string | null
}

export interface EdgeResult {
  cable: string | null
  cable_label: string
  n_parallel: number
  forced: boolean
  sized: boolean
  length_m: number
  p_kw: number
  q_kvar: number
  s_kva: number
  dp_kw: number
  dq_series_kvar: number
  q_charging_kvar: number
  current_a: number | null
  utilization: number | null
  loss_percent: number | null
  vdrop_percent: number | null
}

export interface StationNodeResult {
  /** The canvas node type — the discriminator this union narrows on. */
  kind: 'station'
  /** Which fleet the station belongs to. A separate axis from `kind`: the
   *  sizing physics is identical either way, so this is a label, not an
   *  input. Absent on results produced before the fleet kind was wired. */
  fleet_kind?: FleetKind
  /** Containers per station, defaulted from the pairing on this station's own
   *  chosen station transformer and overridable (`containers_override`).
   *  Absent for a PV station, and absent when no discharge duration is set. */
  containers?: number
  circuit: number
  position: number
  model: string
  s_rated_kva: number
  loading: number
  p_lv_kw: number
  q_lv_kvar: number
  s_lv_kva: number
  dp_tx_kw: number
  dq_tx_kvar: number
  p_mv_kw: number
  q_mv_kvar: number
  s_mv_kva: number
  i_a: number
}

export interface BusbarNodeResult {
  kind: 'busbar'
  p_kw: number
  q_kvar: number
  s_kva: number
  n_circuits: number
  circuit_sizes: number[]
  v_kv: number
}

export interface AuxNodeResult {
  kind: 'aux'
  p_kw?: number
  q_kvar?: number
}

export interface HvTxNodeResult {
  kind: 'hv_tx'
  mode: string
  name: string | null
  s_rated_kva: number | null
  n_parallel: number
  s_through_kva: number
  dp_kw: number
  dq_kvar: number
  v_hv_kv: number
}

export interface PocNodeResult {
  kind: 'poc'
  p_target_kw: number
  pf_target: number
  p_delivered_kw: number
  q_delivered_kvar: number
  p_refined_delivered_kw: number | null
  meets_target: boolean
}

export type NodeResult =
  | StationNodeResult
  | BusbarNodeResult
  | AuxNodeResult
  | HvTxNodeResult
  | PocNodeResult

export interface ResultsSummary {
  /** Per-fleet figures, always present — see BranchSummary. */
  branches: BranchSummary[]
  p_inv_kw: number
  q_inv_kvar: number
  s_inv_kva: number
  pf_inv: number
  p_inv_refined_kw: number
  q_inv_refined_kvar: number
  s_inv_refined_kva: number
  correction_factor: number
  p_poc_target_kw: number
  p_poc_delivered_kw: number
  q_poc_delivered_kvar: number
  p_poc_refined_delivered_kw: number | null
  n_stations: number
  n_circuits: number
  circuit_sizes: number[]
  s_fleet_kva: number
  fleet_loading: number
  loading_ok: boolean
  total_cable_loss_kw: number
  total_transformer_loss_kw: number
  total_active_loss_kw: number
  loss_percent_of_p_inv: number | null
  worst_trunk_current_a: number
  max_circuit_current_a: number
  all_current_ok: boolean
  power_balance_ok: boolean
  v_mv_kv: number
  v_hv_kv: number | null
}

export interface SolveResults {
  edges: Record<string, EdgeResult>
  nodes: Record<string, NodeResult>
  summary: ResultsSummary
  warnings: Issue[]
}

export interface SolveResponse {
  issues: Issue[]
  results: SolveResults | null
}

// --- /api/catalogue response -------------------------------------------------

export interface TransformerInfo {
  key: string
  display_name: string
  s_rated_kva_at_40c: number
  /** `null` means the entry publishes no 30C figure — see ADR-0004 and
   *  CONTEXT.md's "AC power at ambient" entry; the design falls back to the
   *  40C figure and is warned. */
  s_rated_kva_at_30c: number | null
  hv_kv: number | null
  lv_kv: number | null
  brand: string | null
  uk_percent: number
  pk_kw: number
  p0_kw: number
  i0_percent: number
  /** Typed parameters (never computed with) — see CONTEXT.md's "Simulated
   *  parameter / typed parameter" entry. `null` means the datasheet is
   *  silent on that field, not that the value is zero. Unset for every PV
   *  transformer, which has no transcribed datasheet behind it. */
  model: string | null
  vector_group: string | null
  cooling: string | null
  datasheet_url: string | null
  mv_kv_min: number | null
  mv_kv_max: number | null
  lv_winding_count: number
  insulation_level: string | null
  f_nominal: string | null
  uk_tolerance_pct: number | null
  winding_material_mv: string | null
  winding_material_lv: string | null
  ip_rating_transformer: string | null
  ip_rating_enclosure: string | null
  rmu_kv_min: number | null
  rmu_kv_max: number | null
  rmu_rated_current_a: number | null
  rmu_units: string | null
  rmu_relay_protection: string | null
  rmu_short_time_withstand: string | null
  cabinet_protection: string | null
  surge_protection: string | null
  ac_insulation_detection: string | null
  cabinet_temp_control: string | null
  ups: string | null
  width_mm: number | null
  height_mm: number | null
  depth_mm: number | null
  weight_kg: number | null
  cable_entry: string | null
  corrosion_class: string | null
  temp_min_c: number | null
  temp_max_c: number | null
  humidity_min_pct: number | null
  humidity_max_pct: number | null
  altitude_max_m: number | null
  communication: string | null
  standards: string | null
  datasheet_version: string | null
  preliminary: boolean
  /** BESS solution key -> containers per station: the solutions this station
   *  transformer is sold with. Always empty for a PV transformer. */
  paired_solutions: Record<string, number>
}

export interface CableInfo {
  name: string
  cross_section_mm2: number | null
  rated_current_a: number | null
}

export interface BessSolutionInfo {
  key: string
  display_name: string
  brand: string
  series: string
  model: string
  e_nominal_kwh: number
  pcs_s_kva: number
  pcs_count: number
  pcs_lv_kv: number
  duration_h: number
  /** `null` means the datasheet publishes no auxiliary figure — the engine
   *  sums it as zero but raises an informational notice; `0` means the
   *  datasheet states the draw as zero. */
  aux_p_kw: number | null
  aux_q_kvar: number | null
  datasheet_version: string | null
  preliminary: boolean
  datasheet_url: string | null
  /** Typed specification (never computed with) — see CONTEXT.md's "Simulated
   *  parameter / typed parameter" entry. `null` means the datasheet is
   *  silent on that field, not that the value is zero. */
  cell_type: string | null
  dc_v_min: number | null
  dc_v_max: number | null
  ac_v_min: number | null
  ac_v_max: number | null
  ac_i_a: number | null
  pf_at_nominal: number | null
  q_range_percent: number | null
  f_nominal_hz: string | null
  thdi_percent: number | null
  isolation: string | null
  width_mm: number | null
  height_mm: number | null
  depth_mm: number | null
  weight_kg: number | null
  ip_rating: string | null
  corrosion_class: string | null
  temp_min_c: number | null
  temp_max_c: number | null
  humidity_min_pct: number | null
  humidity_max_pct: number | null
  altitude_max_m: number | null
  cooling: string | null
}

export interface CatalogueDefaults {
  tiers: { lv_kv: number; mv_kv: number; hv_kv: number }
  rules: RuleSettings
}

export interface CatalogueResponse {
  transformers: TransformerInfo[]
  cables: Record<string, CableInfo[]> // keyed by rated_voltage_kv formatted "%g"
  defaults: CatalogueDefaults
  bess_solutions: BessSolutionInfo[]
  bess_transformers: TransformerInfo[]
}

// --- Projects / Designs (M4 persistence) ------------------------------------
// Mirrors backend/schemas.py's Project/Design Pydantic models.

export interface ProjectSummary {
  id: number
  name: string
  created_at: string
  design_count: number
}

export interface DesignSummary {
  id: number
  name: string
  technology: Technology
  version: number
  last_edited_by: string
  updated_at: string
}

export interface ProjectDetail {
  id: number
  name: string
  created_at: string
  designs: DesignSummary[]
}

export interface DesignFull {
  id: number
  project_id: number
  name: string
  technology: Technology
  payload: Diagram
  version: number
  last_edited_by: string
  created_at: string
  updated_at: string
}

// --- Seed wizard (POST /api/seed) -------------------------------------------
// Mirrors backend/schemas.py SeedRequest. The response is a bare Diagram dict
// (see backend/seed.py), not a wrapped shape.

export interface SeedParams {
  p_poc_mw: number
  pf_target: number
  interconnection: 'HV' | 'MV'
  v_hv_kv?: number | null
  export_m: number
  v_mv_kv: number
  station_model: string
  max_loading: number
  trunk_m: number
  spacing_m: number
  max_circuit_current_a: number
  aux_p_kw?: number
  aux_q_kvar?: number
}

// --- Stage-1 conceptual sizing (POST /api/stage1) ---------------------------
// Mirrors backend/schemas.py: TransformerElement/CableSectionElement/
// AuxLoadElement, Stage1Request, LossItem, Stage1Response. Temporary page —
// see pages/Stage1Page.tsx.

export interface Stage1TransformerElement {
  type: 'Transformer'
  component: string
  v_kv: number
  n_parallel: number
  label?: string | null
}

export interface Stage1CableSectionElement {
  type: 'Cable section'
  v_kv: number
  label?: string | null
}

export interface Stage1AuxLoadElement {
  type: 'Aux load'
  v_kv: number
  p_kw: number
  q_kvar: number
  label?: string | null
}

export type Stage1Element = Stage1TransformerElement | Stage1CableSectionElement | Stage1AuxLoadElement

export interface Stage1Request {
  p_poc_kw: number
  pf_target: number
  interconnection: 'HV' | 'MV'
  v_export_kv: number
  export_m: number
  elements: Stage1Element[]
}

export interface Stage1LossItem {
  label: string
  dp_kw: number
  dq_kvar: number
}

export interface Stage1Response {
  p_inv_kw: number
  q_inv_kvar: number
  s_inv_kva: number
  pf_inv: number
  losses: Stage1LossItem[]
  power_balance_ok: boolean
}
