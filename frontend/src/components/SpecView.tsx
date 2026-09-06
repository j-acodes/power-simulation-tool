import { fmt, ratingAtAmbients } from '../format'
import { Row, SectionTitle } from './DetailRows'
import type { BessSolutionInfo, TransformerInfo } from '../types'

/** The catalogue-backed thing SpecView is showing. A BESS solution and a BESS
 * station transformer carry different simulated blocks and different typed
 * groupings, so the view branches on this discriminant rather than trying to
 * force one shape over both. */
export type SpecViewTarget =
  | { kind: 'bess_solution'; item: BessSolutionInfo }
  | { kind: 'bess_transformer'; item: TransformerInfo }

/** Read-only, full-screen catalogue specification (ticket 04). Renders inside
 * a `<ModalShell size="full">` — this component owns no overlay of its own.
 *
 * Layout, fixed: header, then the simulated block (what the engine reads —
 * leading on purpose, see CONTEXT.md's "Simulated parameter / typed
 * parameter" entry), then the typed specification grouped as the datasheet
 * groups it, then pairings (both directions), then the datasheet link. A
 * `null` typed field is omitted from its group; a group with nothing set is
 * omitted entirely. */
export function SpecView({
  target,
  solutions,
  transformers,
}: {
  target: SpecViewTarget
  /** Every BESS solution in the catalogue — used to resolve a station
   * transformer's paired solution keys to display names. */
  solutions: BessSolutionInfo[]
  /** Every BESS station transformer in the catalogue — used to find which
   * ones a solution is paired with (the reverse direction has no index of
   * its own; it's the same pairing read from the other side). */
  transformers: TransformerInfo[]
}) {
  const isSolution = target.kind === 'bess_solution'
  const item = target.item
  const preliminary = isSolution && (item as BessSolutionInfo).preliminary
  const datasheetUrl = item.datasheet_url
  const datasheetVersion = isSolution ? (item as BessSolutionInfo).datasheet_version : null

  return (
    <div className="spec-view">
      <div className="spec-view-header">
        <h2>{item.display_name}</h2>
        {item.brand && <p className="panel-hint">{item.brand}</p>}
        {preliminary && <p className="spec-view-preliminary">Preliminary</p>}
      </div>

      <SectionTitle>What the simulation uses</SectionTitle>
      <div className="spec-view-simulated">
        {target.kind === 'bess_solution' ? (
          <SimulatedBessSolution item={target.item} />
        ) : (
          <SimulatedBessTransformer item={target.item} />
        )}
      </div>

      {target.kind === 'bess_solution' ? (
        <BessSolutionSpec item={target.item} />
      ) : (
        <BessTransformerSpec item={target.item} />
      )}

      <PairingsSection target={target} solutions={solutions} transformers={transformers} />

      {/* Provenance shows whenever there is any of it. A transcription with a
        * version but no public URL — which is the shipped Sungrow entry — still
        * has to say which revision it was read off, or the numbers cannot be
        * defended later. The link itself appears only with a URL behind it. */}
      {(datasheetUrl || datasheetVersion) && (
        <>
          <SectionTitle>Datasheet</SectionTitle>
          {datasheetVersion && <Row label="Version" value={datasheetVersion} />}
          {datasheetUrl && (
            <p>
              <a href={datasheetUrl} target="_blank" rel="noreferrer">
                View datasheet
              </a>
            </p>
          )}
        </>
      )}
    </div>
  )
}

function SimulatedBessSolution({ item }: { item: BessSolutionInfo }) {
  return (
    <>
      <Row label="Nominal energy" value={`${fmt(item.e_nominal_kwh)} kWh`} />
      <Row label="PCS rating" value={`${fmt(item.pcs_s_kva)} kVA x ${item.pcs_count}`} />
      <Row label="LV voltage" value={`${fmt(item.pcs_lv_kv, 2)} kV`} />
      <Row label="Discharge duration" value={`${fmt(item.duration_h, 2)} h`} />
      <Row
        label="Auxiliary draw"
        value={
          item.aux_p_kw == null || item.aux_q_kvar == null
            ? 'Not published'
            : `${fmt(item.aux_p_kw, 1)} kW / ${fmt(item.aux_q_kvar, 1)} kvar`
        }
      />
    </>
  )
}

function SimulatedBessTransformer({ item }: { item: TransformerInfo }) {
  return (
    <>
      {item.brand && <Row label="Brand" value={item.brand} />}
      <Row label="Rated power" value={ratingAtAmbients(item)} />
      <Row label="uk%" value={fmt(item.uk_percent, 2)} />
      <Row label="Pk" value={`${fmt(item.pk_kw, 2)} kW`} />
      <Row label="P0" value={`${fmt(item.p0_kw, 2)} kW`} />
      <Row label="i0%" value={fmt(item.i0_percent, 2)} />
      <Row label="HV voltage" value={item.hv_kv != null ? `${fmt(item.hv_kv, 2)} kV` : '—'} />
      <Row label="LV voltage" value={item.lv_kv != null ? `${fmt(item.lv_kv, 2)} kV` : '—'} />
    </>
  )
}

/** One row per non-null field; renders nothing when every field in the group
 * is null (a `Row[]` swallowed by `.filter(Boolean)` at the call site). */
function optionalRow(label: string, value: string | null) {
  return value == null ? null : <Row key={label} label={label} value={value} />
}

function BessSolutionSpec({ item }: { item: BessSolutionInfo }) {
  const dcRows = [
    optionalRow('Cell chemistry', item.cell_type),
    item.dc_v_min != null || item.dc_v_max != null
      ? optionalRow('DC voltage window', `${fmt(item.dc_v_min, 1)} – ${fmt(item.dc_v_max, 1)} V`)
      : null,
  ].filter(Boolean)

  const acRows = [
    item.ac_v_min != null || item.ac_v_max != null
      ? optionalRow('AC voltage window', `${fmt(item.ac_v_min, 1)} – ${fmt(item.ac_v_max, 1)} V`)
      : null,
    optionalRow('AC current (per PCS)', item.ac_i_a != null ? `${fmt(item.ac_i_a, 1)} A` : null),
    optionalRow('Power factor at nominal', item.pf_at_nominal != null ? `> ${fmt(item.pf_at_nominal, 2)}` : null),
    optionalRow('Reactive power range', item.q_range_percent != null ? `±${fmt(item.q_range_percent, 0)}%` : null),
    optionalRow('Nominal frequency', item.f_nominal_hz != null ? `${item.f_nominal_hz} Hz` : null),
    optionalRow('Current distortion (THDi)', item.thdi_percent != null ? `< ${fmt(item.thdi_percent, 1)}%` : null),
    optionalRow('Isolation', item.isolation),
  ].filter(Boolean)

  const hasDimensions = item.width_mm != null || item.height_mm != null || item.depth_mm != null
  const physicalRows = [
    hasDimensions
      ? optionalRow(
          'Dimensions (W x H x D)',
          `${fmt(item.width_mm)} x ${fmt(item.height_mm)} x ${fmt(item.depth_mm)} mm`,
        )
      : null,
    optionalRow('Weight', item.weight_kg != null ? `${fmt(item.weight_kg)} kg` : null),
    optionalRow('Ingress protection', item.ip_rating),
    optionalRow('Corrosion class', item.corrosion_class),
  ].filter(Boolean)

  const hasTemp = item.temp_min_c != null || item.temp_max_c != null
  const hasHumidity = item.humidity_min_pct != null || item.humidity_max_pct != null
  const environmentalRows = [
    hasTemp
      ? optionalRow('Operating temperature', `${fmt(item.temp_min_c, 1)} – ${fmt(item.temp_max_c, 1)} °C`)
      : null,
    hasHumidity
      ? optionalRow('Operating humidity', `${fmt(item.humidity_min_pct, 0)} – ${fmt(item.humidity_max_pct, 0)}%`)
      : null,
    optionalRow('Maximum altitude', item.altitude_max_m != null ? `${fmt(item.altitude_max_m)} m` : null),
    optionalRow('Cooling', item.cooling),
  ].filter(Boolean)

  return (
    <>
      {dcRows.length > 0 && (
        <>
          <SectionTitle>DC side</SectionTitle>
          {dcRows}
        </>
      )}
      {acRows.length > 0 && (
        <>
          <SectionTitle>AC side</SectionTitle>
          {acRows}
        </>
      )}
      {physicalRows.length > 0 && (
        <>
          <SectionTitle>Physical</SectionTitle>
          {physicalRows}
        </>
      )}
      {environmentalRows.length > 0 && (
        <>
          <SectionTitle>Environmental</SectionTitle>
          {environmentalRows}
        </>
      )}
    </>
  )
}

function BessTransformerSpec({ item }: { item: TransformerInfo }) {
  const transformerRows = [
    optionalRow('Model', item.model),
    optionalRow('Vector group', item.vector_group),
    item.mv_kv_min != null || item.mv_kv_max != null
      ? optionalRow('MV voltage range', `${fmt(item.mv_kv_min, 2)} – ${fmt(item.mv_kv_max, 2)} kV`)
      : null,
    optionalRow('LV winding count', String(item.lv_winding_count)),
    optionalRow('Insulation level', item.insulation_level),
    optionalRow('Nominal frequency', item.f_nominal != null ? `${item.f_nominal} Hz` : null),
    optionalRow('uk% tolerance', item.uk_tolerance_pct != null ? `±${fmt(item.uk_tolerance_pct, 1)}%` : null),
    optionalRow('MV winding material', item.winding_material_mv),
    optionalRow('LV winding material', item.winding_material_lv),
    optionalRow('IP rating (transformer)', item.ip_rating_transformer),
    optionalRow('IP rating (enclosure)', item.ip_rating_enclosure),
  ].filter(Boolean)

  const hasRmuRange = item.rmu_kv_min != null || item.rmu_kv_max != null
  const rmuRows = [
    hasRmuRange
      ? optionalRow('RMU voltage range', `${fmt(item.rmu_kv_min, 2)} – ${fmt(item.rmu_kv_max, 2)} kV`)
      : null,
    optionalRow('RMU rated current', item.rmu_rated_current_a != null ? `${fmt(item.rmu_rated_current_a, 0)} A` : null),
    optionalRow('RMU units', item.rmu_units),
    optionalRow('RMU relay protection', item.rmu_relay_protection),
    optionalRow('RMU short-time withstand', item.rmu_short_time_withstand),
  ].filter(Boolean)

  const cabinetRows = [
    optionalRow('Cabinet protection', item.cabinet_protection),
    optionalRow('Surge protection', item.surge_protection),
    optionalRow('AC insulation detection', item.ac_insulation_detection),
    optionalRow('Cabinet temperature control', item.cabinet_temp_control),
    optionalRow('UPS', item.ups),
  ].filter(Boolean)

  const hasDimensions = item.width_mm != null || item.height_mm != null || item.depth_mm != null
  const hasTemp = item.temp_min_c != null || item.temp_max_c != null
  const hasHumidity = item.humidity_min_pct != null || item.humidity_max_pct != null
  const generalRows = [
    optionalRow('Cooling', item.cooling),
    hasDimensions
      ? optionalRow(
          'Dimensions (W x H x D)',
          `${fmt(item.width_mm)} x ${fmt(item.height_mm)} x ${fmt(item.depth_mm)} mm`,
        )
      : null,
    optionalRow('Weight', item.weight_kg != null ? `${fmt(item.weight_kg)} kg` : null),
    optionalRow('Cable entry', item.cable_entry),
    optionalRow('Corrosion class', item.corrosion_class),
    hasTemp
      ? optionalRow('Operating temperature', `${fmt(item.temp_min_c, 1)} – ${fmt(item.temp_max_c, 1)} °C`)
      : null,
    hasHumidity
      ? optionalRow('Operating humidity', `${fmt(item.humidity_min_pct, 0)} – ${fmt(item.humidity_max_pct, 0)}%`)
      : null,
    optionalRow('Maximum altitude', item.altitude_max_m != null ? `${fmt(item.altitude_max_m)} m` : null),
    optionalRow('Communication', item.communication),
    optionalRow('Standards', item.standards),
    item.preliminary ? optionalRow('Preliminary', 'Yes') : null,
  ].filter(Boolean)

  return (
    <>
      {transformerRows.length > 0 && (
        <>
          <SectionTitle>Transformer</SectionTitle>
          {transformerRows}
        </>
      )}
      {rmuRows.length > 0 && (
        <>
          <SectionTitle>RMU</SectionTitle>
          {rmuRows}
        </>
      )}
      {cabinetRows.length > 0 && (
        <>
          <SectionTitle>Control cabinet</SectionTitle>
          {cabinetRows}
        </>
      )}
      {generalRows.length > 0 && (
        <>
          <SectionTitle>General data</SectionTitle>
          {generalRows}
        </>
      )}
    </>
  )
}

function PairingsSection({
  target,
  solutions,
  transformers,
}: {
  target: SpecViewTarget
  solutions: BessSolutionInfo[]
  transformers: TransformerInfo[]
}) {
  const rows =
    target.kind === 'bess_solution'
      ? transformers
          .filter((tx) => target.item.key in tx.paired_solutions)
          .map((tx) => (
            <Row
              key={tx.key}
              label={tx.display_name}
              value={`${tx.paired_solutions[target.item.key]} container(s)`}
            />
          ))
      : Object.entries(target.item.paired_solutions).map(([solutionKey, count]) => {
          const sol = solutions.find((s) => s.key === solutionKey)
          return <Row key={solutionKey} label={sol?.display_name ?? solutionKey} value={`${count} container(s)`} />
        })

  if (rows.length === 0) return null

  return (
    <>
      <SectionTitle>{target.kind === 'bess_solution' ? 'Sold with these station transformers' : 'Sold with these solutions'}</SectionTitle>
      {rows}
    </>
  )
}
