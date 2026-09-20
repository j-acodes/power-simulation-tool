import { fmt, ratingAtAmbients } from '../format'
import { Row, SectionTitle } from './DetailRows'
import type { ReactNode } from 'react'
import type { BessSolutionInfo, FleetKind, PvInverterInfo, TransformerInfo } from '../types'

/** The catalogue-backed product SpecView is showing. The transformer-station
 * target is shared by both fleet kinds; callers identify the fleet without
 * pretending a PV product is a BESS product. */
export type SpecViewTarget =
  | { kind: 'bess_solution'; item: BessSolutionInfo }
  | { kind: 'pv_inverter'; item: PvInverterInfo }
  | { kind: 'transformer_station'; fleet_kind: FleetKind; item: TransformerInfo }

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
  pvInverters = [],
  pvTransformers = [],
}: {
  target: SpecViewTarget
  /** Every BESS solution in the catalogue — used to resolve a station
   * transformer's paired solution keys to display names. */
  solutions: BessSolutionInfo[]
  /** Every BESS station transformer in the catalogue — used to find which
   * ones a solution is paired with (the reverse direction has no index of
   * its own; it's the same pairing read from the other side). */
  transformers: TransformerInfo[]
  pvInverters?: PvInverterInfo[]
  pvTransformers?: TransformerInfo[]
}) {
  const item = target.item
  const preliminary = item.preliminary
  const datasheetUrl = item.datasheet_url
  const datasheetVersion = item.datasheet_version
  const presentation = targetPresentation(
    target, solutions, transformers, pvInverters, pvTransformers,
  )

  return (
    <div className="spec-view">
      <div className="spec-view-header">
        <h2>{item.display_name}</h2>
        {item.brand && <p className="panel-hint">{item.brand}</p>}
        {preliminary && <p className="spec-view-preliminary">Preliminary</p>}
      </div>

      <SectionTitle>What the simulation uses</SectionTitle>
      <div className="spec-view-simulated">
        {presentation.simulated}
      </div>

      {presentation.typed}

      {presentation.pairingRows.length > 0 && (
        <>
          <SectionTitle>{presentation.pairingTitle}</SectionTitle>
          {presentation.pairingRows}
        </>
      )}

      {/* Provenance shows whenever there is any of it. A transcription with a
        * version but no public URL — which is the shipped Sungrow entry — still
        * has to say which revision it was read off, or the numbers cannot be
        * defended later. The link itself appears only with a URL behind it. */}
      {(datasheetUrl || datasheetVersion) && (
        <>
          <SectionTitle>Datasheet</SectionTitle>
          {datasheetVersion && <Row label="Version" value={datasheetVersion} />}
          {presentation.datasheetDate && <Row label="Date" value={presentation.datasheetDate} />}
          {presentation.market && <Row label="Market" value={presentation.market} />}
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

function SimulatedPvInverter({ item }: { item: PvInverterInfo }) {
  const power = item.power_kw_at_30c == null
    ? `${fmt(item.power_kw_at_40c)} kW / kVA @ 40 °C`
    : `${fmt(item.power_kw_at_30c)} kW / kVA @ 30 °C; ${fmt(item.power_kw_at_40c)} kW / kVA @ 40 °C`
  return (
    <>
      <Row label="Power at ambient" value={power} />
      <Row label="Power provenance" value={item.power_provenance} />
      <Row label="Nominal AC voltage" value={`${fmt(item.nominal_ac_voltage_kv, 2)} kV`} />
      <Row label="Minimum power factor" value={item.minimum_power_factor == null ? 'Not published' : fmt(item.minimum_power_factor, 2)} />
    </>
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

/** The switchgear rated current, marked when it came from the ADR-0006
 *  fallback rather than a datasheet — a defaulted figure must never read as a
 *  supplier claim. */
function switchgearRatedCurrent(item: TransformerInfo) {
  const value = `${fmt(item.switchgear_rated_current_a, 0)} A`
  return item.switchgear_rating_published ? value : `${value} (not published — standard rating assumed)`
}

function SimulatedTransformerStation({ item }: { item: TransformerInfo }) {
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
      <Row label="Switchgear rated current" value={switchgearRatedCurrent(item)} />
    </>
  )
}

/** One row per non-null field; renders nothing when every field in the group
 * is null (a `Row[]` swallowed by `.filter(Boolean)` at the call site). */
function optionalRow(label: string, value: string | null) {
  return value == null ? null : <Row key={label} label={label} value={value} />
}

function typedRow(label: string, value: string | null | undefined, showMissing = true) {
  return optionalRow(label, value ?? (showMissing ? 'Not published' : null))
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

function PvInverterSpec({ item }: { item: PvInverterInfo }) {
  const efficiencyRows = [
    typedRow('Maximum efficiency', item.maximum_efficiency_percent == null ? null : `${fmt(item.maximum_efficiency_percent, 2)} %`),
    typedRow('European efficiency', item.european_efficiency_percent == null ? null : `${fmt(item.european_efficiency_percent, 2)} %`),
  ].filter(Boolean)
  const dcRows = [
    typedRow('DC voltage range', item.dc_voltage_min_v == null || item.dc_voltage_max_v == null ? null : `${fmt(item.dc_voltage_min_v)} – ${fmt(item.dc_voltage_max_v)} V`),
    typedRow('Start voltage', item.start_voltage_v == null ? null : `${fmt(item.start_voltage_v)} V`),
    typedRow('Nominal DC voltage', item.dc_voltage_nominal_v == null ? null : `${fmt(item.dc_voltage_nominal_v)} V`),
    typedRow('MPPTs', item.mppt_count == null ? null : String(item.mppt_count)),
    typedRow('PV inputs per MPPT', item.pv_inputs_per_mppt ?? (item.strings_per_mppt == null ? null : String(item.strings_per_mppt))),
    typedRow('Input current per MPPT', item.input_current_per_mppt_a == null ? null : `${fmt(item.input_current_per_mppt_a)} A`),
    typedRow('Short-circuit current per MPPT', item.short_circuit_current_per_mppt_a == null ? null : `${fmt(item.short_circuit_current_per_mppt_a)} A`),
  ].filter(Boolean)
  const acRows = [
    typedRow('Rated AC power', item.rated_ac_power_kw == null ? null : `${fmt(item.rated_ac_power_kw)} kW`),
    typedRow('Maximum active power', item.max_ac_active_power_kw == null ? null : `${fmt(item.max_ac_active_power_kw)} kW`),
    typedRow('Maximum apparent power', item.max_ac_apparent_power_kva == null ? null : `${fmt(item.max_ac_apparent_power_kva)} kVA`),
    typedRow('Nominal AC current', item.nominal_ac_current_a == null ? null : `${fmt(item.nominal_ac_current_a, 1)} A`),
    typedRow('Maximum AC current', item.max_ac_current_a == null ? null : `${fmt(item.max_ac_current_a, 1)} A`),
    typedRow('Grid frequency', item.rated_grid_frequency),
    typedRow('Adjustable power factor', item.adjustable_power_factor),
    typedRow('THDi', item.thdi_percent == null ? null : `< ${fmt(item.thdi_percent, 1)} %`),
  ].filter(Boolean)
  const protectionRows = [typedRow('Protection', item.protection)].filter(Boolean)
  const connectionRows = [
    typedRow('Communication', item.communication),
    typedRow('DC connector', item.dc_connector),
    typedRow('AC connector', item.ac_connector),
  ].filter(Boolean)
  const mechanicalRows = [
    typedRow('Dimensions', item.width_mm == null || item.height_mm == null || item.depth_mm == null ? null : `${fmt(item.width_mm)} × ${fmt(item.height_mm)} × ${fmt(item.depth_mm)} mm`),
    typedRow('Weight', item.weight_specification ?? (item.weight_kg == null ? null : `${fmt(item.weight_kg)} kg`)),
    typedRow('Isolation', item.isolation),
    typedRow('Ingress protection', item.ip_rating),
    typedRow('Corrosion class', item.corrosion_class),
    typedRow('Operating temperature', item.temp_min_c == null || item.temp_max_c == null ? null : `${fmt(item.temp_min_c)} – ${fmt(item.temp_max_c)} °C`),
    typedRow('Relative humidity', item.relative_humidity),
    typedRow('Maximum altitude', item.altitude_max_m == null ? null : `${fmt(item.altitude_max_m)} m`),
    typedRow('Cooling', item.cooling),
  ].filter(Boolean)
  const standardsRows = [typedRow('Standards', item.standards), typedRow('Grid support', item.grid_support)].filter(Boolean)
  return <>{specGroup('Efficiency', efficiencyRows)}{specGroup('DC input', dcRows)}{specGroup('AC output and grid support', acRows)}{specGroup('Protection', protectionRows)}{specGroup('Communications and connectors', connectionRows)}{specGroup('General and environmental', mechanicalRows)}{specGroup('Standards', standardsRows)}</>
}

function specGroup(title: string, rows: Array<ReturnType<typeof optionalRow>>) {
  return rows.length === 0 ? null : <><SectionTitle>{title}</SectionTitle>{rows}</>
}

function TransformerStationSpec({ item, showMissing }: { item: TransformerInfo; showMissing: boolean }) {
  const inputRows = [
    typedRow('Maximum input current', item.maximum_input_current, showMissing),
    typedRow('LV panel segregation', item.lv_panel_segregation, showMissing),
    typedRow('LV main switches', item.lv_main_switches, showMissing),
    typedRow('LV inverter switches', item.lv_inverter_switches, showMissing),
  ].filter(Boolean)
  const transformerRows = [
    typedRow('Series', item.series, showMissing),
    typedRow('Model', item.model, showMissing),
    typedRow('Transformer type', item.transformer_type, showMissing),
    typedRow('Vector group', item.vector_group, showMissing),
    item.mv_kv_min != null || item.mv_kv_max != null
      ? typedRow('MV voltage range', `${fmt(item.mv_kv_min, 2)} – ${fmt(item.mv_kv_max, 2)} kV`, showMissing)
      : typedRow('MV voltage range', null, showMissing),
    typedRow('LV winding count', String(item.lv_winding_count), showMissing),
    typedRow('Tappings', item.transformer_tappings, showMissing),
    typedRow('Oil type', item.transformer_oil_type, showMissing),
    typedRow('Efficiency', item.transformer_efficiency, showMissing),
    typedRow('Insulation level', item.insulation_level, showMissing),
    typedRow('Nominal frequency', item.f_nominal != null ? `${item.f_nominal} Hz` : null, showMissing),
    typedRow('uk% tolerance', item.uk_tolerance_pct != null ? `±${fmt(item.uk_tolerance_pct, 1)}%` : null, showMissing),
    typedRow('MV winding material', item.winding_material_mv, showMissing),
    typedRow('LV winding material', item.winding_material_lv, showMissing),
    typedRow('IP rating (transformer)', item.ip_rating_transformer, showMissing),
    typedRow('IP rating (enclosure)', item.ip_rating_enclosure, showMissing),
  ].filter(Boolean)

  const hasRmuRange = item.rmu_kv_min != null || item.rmu_kv_max != null
  const rmuRows = [
    hasRmuRange
      ? typedRow('RMU voltage range', `${fmt(item.rmu_kv_min, 2)} – ${fmt(item.rmu_kv_max, 2)} kV`, showMissing)
      : typedRow('RMU voltage range', null, showMissing),
    typedRow('RMU units', item.rmu_units, showMissing),
    typedRow('RMU relay protection', item.rmu_relay_protection, showMissing),
    typedRow('RMU short-time withstand', item.rmu_short_time_withstand, showMissing),
  ].filter(Boolean)

  const cabinetRows = [
    typedRow('AC input protection', item.ac_input_protection, showMissing),
    typedRow('Transformer protection', item.transformer_protection, showMissing),
    typedRow('Internal arc classification', item.internal_arc_classification, showMissing),
    typedRow('Surge protection', item.surge_protection, showMissing),
    typedRow('Optional features', item.optional_features, showMissing),
  ].filter(Boolean)

  const auxiliaryRows = [
    typedRow('Auxiliary transformer', item.auxiliary_transformer, showMissing),
    typedRow('Auxiliary output voltage', item.auxiliary_output_voltage, showMissing),
  ].filter(Boolean)

  const hasDimensions = item.width_mm != null || item.height_mm != null || item.depth_mm != null
  const hasTemp = item.temp_min_c != null || item.temp_max_c != null
  const hasHumidity = item.humidity_min_pct != null || item.humidity_max_pct != null
  const generalRows = [
    typedRow('Cooling', item.cooling, showMissing),
    hasDimensions
      ? typedRow(
          'Dimensions (W x H x D)',
          `${fmt(item.width_mm)} x ${fmt(item.height_mm)} x ${fmt(item.depth_mm)} mm`,
          showMissing,
        )
      : typedRow('Dimensions (W x H x D)', null, showMissing),
    typedRow('Weight', item.weight_specification ?? (item.weight_kg != null ? `${fmt(item.weight_kg)} kg` : null), showMissing),
    typedRow('Cable entry', item.cable_entry, showMissing),
    typedRow('Corrosion class', item.corrosion_class, showMissing),
    hasTemp
      ? typedRow('Operating temperature', `${fmt(item.temp_min_c, 1)} – ${fmt(item.temp_max_c, 1)} °C`, showMissing)
      : typedRow('Operating temperature', null, showMissing),
    hasHumidity
      ? typedRow('Operating humidity', `${fmt(item.humidity_min_pct, 0)} – ${fmt(item.humidity_max_pct, 0)}%`, showMissing)
      : typedRow('Operating humidity', null, showMissing),
    typedRow('Maximum altitude', item.altitude_max_m != null ? `${fmt(item.altitude_max_m)} m` : null, showMissing),
    item.preliminary ? optionalRow('Preliminary', 'Yes') : null,
  ].filter(Boolean)

  const communicationsRows = [
    typedRow('Communication', item.communication, showMissing),
    typedRow('Standards', item.standards, showMissing),
  ].filter(Boolean)

  return (
    <>
      {inputRows.length > 0 && <>{<SectionTitle>Input and LV panel</SectionTitle>}{inputRows}</>}
      {transformerRows.length > 0 && (
        <>
          <SectionTitle>Output transformer</SectionTitle>
          {transformerRows}
        </>
      )}
      {rmuRows.length > 0 && (
        <>
          <SectionTitle>RMU</SectionTitle>
          {rmuRows}
        </>
      )}
      {auxiliaryRows.length > 0 && <>{<SectionTitle>Auxiliary transformer</SectionTitle>}{auxiliaryRows}</>}
      {cabinetRows.length > 0 && (
        <>
          <SectionTitle>Protection and options</SectionTitle>
          {cabinetRows}
        </>
      )}
      {generalRows.length > 0 && (
        <>
          <SectionTitle>General and environmental</SectionTitle>
          {generalRows}
        </>
      )}
      {communicationsRows.length > 0 && <>{<SectionTitle>Communications and standards</SectionTitle>}{communicationsRows}</>}
    </>
  )
}

interface TargetPresentation {
  simulated: ReactNode
  typed: ReactNode
  pairingTitle: string
  pairingRows: ReactNode[]
  datasheetDate?: string | null
  market?: string | null
}

function pairingValue(maximumCount: number, provenance: string) {
  return `1–${maximumCount} inverter(s); stations deploy full. ${provenance}`
}

/** Keep the product-kind switch in one place so the shared page structure
 * cannot drift between its simulated, typed, pairing, and provenance blocks. */
function targetPresentation(
  target: SpecViewTarget,
  solutions: BessSolutionInfo[],
  transformers: TransformerInfo[],
  pvInverters: PvInverterInfo[],
  pvTransformers: TransformerInfo[],
): TargetPresentation {
  if (target.kind === 'bess_solution') {
    return {
      simulated: <SimulatedBessSolution item={target.item} />,
      typed: <BessSolutionSpec item={target.item} />,
      pairingTitle: 'Sold with these station transformers',
      pairingRows: transformers
        .filter((tx) => target.item.key in tx.paired_solutions)
        .map((tx) => (
          <Row
            key={tx.key}
            label={tx.display_name}
            value={`${tx.paired_solutions[target.item.key]} container(s)`}
          />
        )),
    }
  }
  if (target.kind === 'pv_inverter') {
    return {
      simulated: <SimulatedPvInverter item={target.item} />,
      typed: <PvInverterSpec item={target.item} />,
      pairingTitle: 'Paired PV Transformer Stations',
      pairingRows: pvTransformers
        .filter((tx) => target.item.key in tx.paired_inverters)
        .map((tx) => {
          const pairing = tx.paired_inverters[target.item.key]
          return <Row key={tx.key} label={tx.display_name} value={pairingValue(
            pairing.maximum_count, pairing.count_provenance,
          )} />
        }),
      datasheetDate: target.item.datasheet_date,
      market: target.item.market,
    }
  }
  if (target.fleet_kind === 'bess') {
    return {
      simulated: <SimulatedTransformerStation item={target.item} />,
      typed: <TransformerStationSpec item={target.item} showMissing={false} />,
      pairingTitle: 'Sold with these solutions',
      pairingRows: Object.entries(target.item.paired_solutions).map(([solutionKey, count]) => {
        const sol = solutions.find((s) => s.key === solutionKey)
        return <Row key={solutionKey} label={sol?.display_name ?? solutionKey} value={`${count} container(s)`} />
      }),
      datasheetDate: target.item.datasheet_date,
      market: target.item.market,
    }
  }
  return {
    simulated: <SimulatedTransformerStation item={target.item} />,
    typed: <TransformerStationSpec item={target.item} showMissing />,
    pairingTitle: 'Paired PV inverters',
    pairingRows: Object.entries(target.item.paired_inverters).map(([inverterKey, pairing]) => {
      const inverter = pvInverters.find((candidate) => candidate.key === inverterKey)
      return <Row key={inverterKey} label={inverter?.display_name ?? inverterKey} value={pairingValue(
        pairing.maximum_count, pairing.count_provenance,
      )} />
    }),
    datasheetDate: target.item.datasheet_date,
    market: target.item.market,
  }
}
