import { useState } from 'react'
import { fmt, kvGroupKey, pct, powerFactor, ratingAtAmbients } from '../format'
import { CollapsiblePanel } from './CollapsiblePanel'
import { LABEL } from '../labels'
import { useCatalogue } from '../hooks/useCatalogue'
import { useStore } from '../store'
import { permitsFleetKind } from '../technology'
import { defaultInverterSelection } from '../inverterDefaults'
import { Row, SectionTitle } from '../components/DetailRows'
import { ModalShell, useConfirmDialog } from '../components/Modal'
import { SpecView } from '../components/SpecView'
import type { SpecViewTarget } from '../components/SpecView'
import type { Diagram, DiagramEdge, DiagramNode, EdgeResult, NodeResult, TransformerInfo } from '../types'

/** Standard busbar-switchgear rating ladder (ADR-0007) — mirrors
 * BUSBAR_SWITCHGEAR_LADDER_A in powertool/components.py. Offered as pin
 * choices alongside "Sized". */
const SWITCHGEAR_LADDER_A = [630, 800, 1250, 1600, 2000, 2500, 3150, 4000] as const

/** A busbar's trunk edges: the edges straight off the busbar that feed a
 * station (the circuit's first cable — see powertool/graph.py's
 * `segment_edge_ids[(c, 1)]`), in the diagram's own edge order, which is
 * also circuit order. What a feeder pin is keyed by. */
function trunkEdgesOf(diagram: Diagram, busbarId: string): DiagramEdge[] {
  const stationIds = new Set(diagram.nodes.filter((n) => n.kind === 'station').map((n) => n.id))
  return diagram.edges.filter(
    (e) => (e.source === busbarId && stationIds.has(e.target))
      || (e.target === busbarId && stationIds.has(e.source)),
  )
}

/** One pin control: "Sized" clears the pin (patches the key to `null`), or a
 * standard ladder rating pins it exactly (ADR-0007, ticket 04). */
function SwitchgearPinSelect({
  label,
  pinnedA,
  onChange,
}: {
  label: string
  pinnedA: number | null
  onChange: (value: number | null) => void
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select
        value={pinnedA != null ? String(pinnedA) : ''}
        onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
      >
        <option value="">Sized</option>
        {SWITCHGEAR_LADDER_A.map((a) => (
          <option key={a} value={a}>{a} A</option>
        ))}
      </select>
    </label>
  )
}

function NumberField({
  label,
  value,
  onChange,
  step = 1,
  min,
  max,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  step?: number
  min?: number
  max?: number
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type="number" step={step} min={min} max={max} value={Number.isFinite(value) ? value : ''} onChange={(e) => onChange(e.target.valueAsNumber)} />
    </label>
  )
}

function CustomTransformerFields({
  props,
  onChange,
}: {
  props: Record<string, unknown>
  onChange: (patch: Record<string, unknown>) => void
}) {
  return (
    <>
      <label className="field">
        <span>Name</span>
        <input type="text" value={String(props.name ?? '')} onChange={(e) => onChange({ name: e.target.value })} />
      </label>
      <NumberField label={LABEL.sRatedKva} value={Number(props.s_rated_kva ?? 0)} onChange={(v) => onChange({ s_rated_kva: v })} />
      <NumberField label={LABEL.ukPercent} value={Number(props.uk_percent ?? 0)} step={0.1} onChange={(v) => onChange({ uk_percent: v })} />
      <NumberField label={LABEL.pkKw} value={Number(props.pk_kw ?? 0)} step={0.1} onChange={(v) => onChange({ pk_kw: v })} />
      <NumberField label={LABEL.p0Kw} value={Number(props.p0_kw ?? 0)} step={0.1} onChange={(v) => onChange({ p0_kw: v })} />
      <NumberField label={LABEL.i0Percent} value={Number(props.i0_percent ?? 0)} step={0.1} onChange={(v) => onChange({ i0_percent: v })} />
    </>
  )
}

function OptionalNumberField({
  label,
  value,
  onChange,
  step = 1,
  min,
  max,
}: {
  label: string
  value: unknown
  onChange: (v: number | undefined) => void
  step?: number
  min?: number
  max?: number
}) {
  const numeric = typeof value === 'number' && Number.isFinite(value) ? value : ''
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type="number"
        step={step}
        min={min}
        max={max}
        value={numeric}
        onChange={(e) => onChange(e.target.value === '' ? undefined : e.target.valueAsNumber)}
      />
    </label>
  )
}

function CustomPvInverterFields({
  props,
  onChange,
}: {
  props: Record<string, unknown>
  onChange: (patch: Record<string, unknown>) => void
}) {
  return (
    <>
      <label className="field">
        <span>Custom inverter name</span>
        <input
          type="text"
          value={String(props.custom_inverter_name ?? '')}
          onChange={(e) => onChange({ custom_inverter_name: e.target.value })}
        />
      </label>
      <NumberField
        label="Inverter power at 40 °C (kW/kVA)"
        value={Number(props.custom_inverter_power_kw_at_40c ?? 0)}
        min={0}
        onChange={(value) => onChange({ custom_inverter_power_kw_at_40c: value })}
      />
      <OptionalNumberField
        label="Inverter power at 30 °C (kW/kVA, optional)"
        value={props.custom_inverter_power_kw_at_30c}
        min={0}
        onChange={(value) => onChange({ custom_inverter_power_kw_at_30c: value })}
      />
      <NumberField
        label="Inverter nominal AC voltage (kV)"
        value={Number(props.custom_inverter_nominal_ac_voltage_kv ?? 0)}
        step={0.01}
        min={0}
        onChange={(value) => onChange({ custom_inverter_nominal_ac_voltage_kv: value })}
      />
      <NumberField
        label="Inverters"
        value={Number(props.inverter_count ?? 1)}
        min={1}
        onChange={(value) => onChange({
          inverter_count: Number.isFinite(value) ? Math.max(1, Math.round(value)) : 1,
        })}
      />
      <OptionalNumberField
        label="Minimum power factor (optional)"
        value={props.custom_inverter_minimum_power_factor}
        step={0.01}
        min={0}
        max={1}
        onChange={(value) => onChange({ custom_inverter_minimum_power_factor: value })}
      />
      <p className="panel-hint">
        Nominal AC voltage is recorded for review; compatibility is assumed and is not validated.
      </p>
    </>
  )
}

/** Read-only preview of a catalogue transformer, shown in the Inspector when
 * a palette item is clicked (not dragged) — see Palette.tsx. Shared by the PV
 * and BESS station transformer catalogues (ticket 06): both are
 * `TransformerInfo`, and this card already renders exactly the rows either
 * one needs.
 *
 * Heads with `display_name`, not the raw catalogue key — the key is what a
 * saved design payload stores and an engineer debugging one needs to see,
 * so it stays visible as a row rather than disappearing (ticket 06 decision
 * 3: raw keys must stop leaking into the headline). */
function TransformerPreview({ tx }: { tx: TransformerInfo }) {
  return (
    <div>
      <h3>{tx.display_name}</h3>
      <Row label={LABEL.catalogueKey} value={tx.key} />
      <Row label={LABEL.brand} value={tx.brand ?? '—'} />
      <Row label={LABEL.sRatedKva} value={ratingAtAmbients(tx)} />
      <Row label={LABEL.ukPercent} value={fmt(tx.uk_percent, 2)} />
      <Row label={LABEL.pkKw} value={fmt(tx.pk_kw, 2)} />
      <Row label={LABEL.p0Kw} value={fmt(tx.p0_kw, 2)} />
      <Row label={LABEL.i0Percent} value={fmt(tx.i0_percent, 2)} />
      <Row label={LABEL.hvKv} value={tx.hv_kv != null ? fmt(tx.hv_kv, 2) : '—'} />
      <Row label={LABEL.lvKv} value={tx.lv_kv != null ? fmt(tx.lv_kv, 2) : '—'} />
      <p className="panel-hint">Drag this item onto the canvas to place a station of this model.</p>
    </div>
  )
}

function NodeProperties({ node }: { node: DiagramNode }) {
  const updateNodeProps = useStore((s) => s.updateNodeProps)
  const removeNode = useStore((s) => s.removeNode)
  const catalogue = useCatalogue()
  const diagram = useStore((s) => s.diagram)
  const technology = useStore((s) => s.designMeta?.technology)
  const patch = (p: Record<string, unknown>) => updateNodeProps(node.id, p)
  const props = node.props
  // Ticket 06: the expand control opening a placed station's specification
  // full-screen. Local to this component so closing it (Escape) never
  // touches selection/diagram state — the canvas underneath is untouched.
  const [specTarget, setSpecTarget] = useState<SpecViewTarget | null>(null)
  const { confirm, dialog: confirmDialog } = useConfirmDialog()

  // Station transformer -> duration -> solution, each narrowing the next
  // (ticket 02): a custom transformer corresponds to no catalogue entry, so
  // it carries no pairing to narrow the solution choice with.
  const bessTransformer = props.mode === 'custom'
    ? undefined
    : catalogue?.bess_transformers.find((tx) => tx.key === props.model)
  const bessPaired = bessTransformer?.paired_solutions ?? {}
  const dischargeHours = diagram.settings.rules.discharge_hours
  const bessSolutionOptions = props.mode === 'custom'
    ? catalogue?.bess_solutions ?? []
    : (catalogue?.bess_solutions ?? []).filter(
        (sol) => sol.key in bessPaired
          && (dischargeHours === undefined || sol.duration_h === dischargeHours),
      )
  const pairedContainers = bessPaired[String(props.bess_solution)]
  // The PV counterpart to `bessTransformer` above — same "custom means no
  // catalogue entry" guard. Only meaningful for a PV station; harmless
  // (undefined) for every other node kind.
  const pvTransformer = props.mode === 'custom'
    ? undefined
    : catalogue?.transformers.find((tx) => tx.key === props.model)
  const stationTransformer = props.fleet_kind === 'bess' ? bessTransformer : pvTransformer
  const selectedBessSolution = catalogue?.bess_solutions.find((sol) => sol.key === props.bess_solution)
  const pvPairings = pvTransformer?.paired_inverters ?? {}
  const pvInverterOptions = (catalogue?.pv_inverters ?? []).filter((inverter) => inverter.key in pvPairings)
  const selectedPvInverter = (catalogue?.pv_inverters ?? []).find((inverter) => inverter.key === props.pv_inverter)
  const selectedPvPairing = pvPairings[String(props.pv_inverter)]

  // One catalogue model, applied to every catalogue PV station on the canvas.
  // A station's inverter follows from its model, so this is also how a plant
  // changes inverter: re-model the stations and let the pairing decide.
  // Custom stations are left alone — they are custom on purpose.
  const otherPvStations = diagram.nodes.filter(
    (n) => n.kind === 'station' && n.props.fleet_kind !== 'bess'
      && n.props.mode !== 'custom' && n.id !== node.id,
  )
  const applyModelToAllPvStations = async () => {
    if (!pvTransformer) return
    const ok = await confirm({
      title: 'Apply to every PV station?',
      message: `Set ${otherPvStations.length} other PV station(s) to `
        + `${pvTransformer.display_name}, each filled with its paired inverter. `
        + `This replaces the model they have now and cannot be undone.`,
      confirmLabel: 'Apply to all',
    })
    if (!ok) return
    for (const target of otherPvStations) {
      updateNodeProps(target.id, {
        model: pvTransformer.key,
        ...defaultInverterSelection(pvTransformer),
      })
    }
  }

  return (
    <div>
      {node.kind === 'poc' && (
        <>
          {permitsFleetKind(technology, 'pv') && (
            <NumberField label={`PV target ${LABEL.activePowerMw}`} value={Number(props.p_target_mw ?? 0)} step={0.1} onChange={(v) => patch({ p_target_mw: v })} />
          )}
          {permitsFleetKind(technology, 'bess') && (
            <NumberField label={`BESS target ${LABEL.activePowerMw}`} value={Number(props.p_target_bess_mw ?? 0)} step={0.1} onChange={(v) => patch({ p_target_bess_mw: v })} />
          )}
          <NumberField label={LABEL.powerFactor} value={Number(props.pf ?? 0)} step={0.01} onChange={(v) => patch({ pf: v })} />
          <p className="panel-hint">
            The reactive duty at the point of connection is split pro-rata by each fleet&apos;s
            active target.
          </p>
        </>
      )}
      {node.kind === 'hv_tx' && (
        <>
          <label className="field">
            <span>Mode</span>
            <select value={String(props.mode ?? 'auto')} onChange={(e) => patch({ mode: e.target.value })}>
              <option value="auto">Auto-sized</option>
              <option value="model">Catalogue model</option>
              <option value="custom">Custom</option>
            </select>
          </label>
          {props.mode === 'model' && (
            <label className="field">
              <span>Model</span>
              <select value={String(props.model ?? '')} onChange={(e) => patch({ model: e.target.value })}>
                <option value="">— select —</option>
                {catalogue?.transformers.map((tx) => (
                  <option key={tx.key} value={tx.key}>
                    {tx.display_name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {props.mode === 'custom' && <CustomTransformerFields props={props} onChange={patch} />}
          <NumberField label="Parallel units" value={Number(props.n_parallel ?? 1)} onChange={(v) => patch({ n_parallel: v })} />
        </>
      )}
      {node.kind === 'station' && (
        <>
          <label className="field">
            <span>Fleet kind</span>
            <select value={String(props.fleet_kind ?? 'pv')} onChange={(e) => patch({ fleet_kind: e.target.value })}>
              <option value="pv">PV</option>
              <option value="bess">BESS</option>
            </select>
          </label>
          <label className="field">
            <span>Mode</span>
            <select value={String(props.mode ?? 'catalogue')} onChange={(e) => patch({ mode: e.target.value })}>
              <option value="catalogue">Catalogue model</option>
              <option value="custom">Custom</option>
            </select>
          </label>
          {props.mode !== 'custom' && (
            <label className="field">
              <span>Model</span>
              <select value={String(props.model ?? '')} onChange={(e) => patch({
                model: e.target.value,
                ...(props.fleet_kind !== 'bess'
                  ? defaultInverterSelection(
                      catalogue?.transformers.find((tx) => tx.key === e.target.value))
                  : {}),
              })}>
                <option value="">— select —</option>
                {(props.fleet_kind === 'bess' ? catalogue?.bess_transformers : catalogue?.transformers)?.map((tx) => (
                  <option key={tx.key} value={tx.key}>
                    {tx.display_name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {/* Ticket 06: hidden — not disabled — for a custom station. A
              custom transformer has no catalogue entry and therefore no
              specification to open. */}
          {stationTransformer && (
            <button
              type="button"
              onClick={() => setSpecTarget({
                kind: 'transformer_station',
                fleet_kind: props.fleet_kind === 'bess' ? 'bess' : 'pv',
                item: stationTransformer,
              })}
            >
              Station transformer specification
            </button>
          )}
          {props.mode === 'custom' && <CustomTransformerFields props={props} onChange={patch} />}
          {props.fleet_kind !== 'bess' && props.mode === 'custom' && (
            <CustomPvInverterFields props={props} onChange={patch} />
          )}
          {props.fleet_kind === 'bess' && (
            <>
              <label className="field">
                <span>BESS solution</span>
                <select value={String(props.bess_solution ?? '')} onChange={(e) => patch({ bess_solution: e.target.value })}>
                  <option value="">— select —</option>
                  {bessSolutionOptions.map((sol) => (
                    <option key={sol.key} value={sol.key}>
                      {sol.display_name}
                    </option>
                  ))}
                </select>
              </label>
              <NumberField
                label="Containers"
                value={Number(props.containers_override ?? pairedContainers ?? 0)}
                onChange={(v) => patch({ containers_override: v })}
              />
              {props.containers_override === undefined && (
                <p className="panel-hint">
                  {pairedContainers !== undefined
                    ? `Defaulted from the pairing (${pairedContainers}). Enter a value to override.`
                    : 'No pairing default for this transformer/solution — enter a container count.'}
                </p>
              )}
              {/* Ticket 06: same "hidden, not disabled" rule — no control for
                  the half that isn't chosen yet. */}
              {selectedBessSolution && (
                <button type="button" onClick={() => setSpecTarget({ kind: 'bess_solution', item: selectedBessSolution })}>
                  BESS solution specification
                </button>
              )}
            </>
          )}
          {props.fleet_kind !== 'bess' && props.mode !== 'custom' && pvTransformer && (
            <>
              {otherPvStations.length > 0 && (
                <button type="button" onClick={applyModelToAllPvStations}>
                  Apply this model to all PV stations ({otherPvStations.length})
                </button>
              )}
              {/* A station's inverter is a fact about the station until the
                  catalogue gives it a second pairing to choose between: every
                  station ships with exactly one today, and a select with one
                  option is a decision nobody gets to make. */}
              {pvInverterOptions.length > 1 ? (
                <label className="field">
                  <span>PV inverter</span>
                  <select
                    value={String(props.pv_inverter ?? '')}
                    onChange={(e) => {
                      const pairing = pvPairings[e.target.value]
                      patch({ pv_inverter: e.target.value, inverter_count: pairing?.maximum_count })
                    }}
                  >
                    <option value="">— select —</option>
                    {pvInverterOptions.map((inverter) => (
                      <option key={inverter.key} value={inverter.key}>{inverter.display_name}</option>
                    ))}
                  </select>
                </label>
              ) : (
                <Row label="PV inverter" value={selectedPvInverter?.display_name ?? '—'} />
              )}
              {selectedPvPairing && (
                <NumberField
                  label="Inverters"
                  value={Number(props.inverter_count ?? selectedPvPairing.maximum_count)}
                  min={1}
                  max={selectedPvPairing.maximum_count}
                  onChange={(value) => patch({
                    inverter_count: Number.isFinite(value)
                      ? Math.min(selectedPvPairing.maximum_count, Math.max(1, Math.round(value)))
                      : selectedPvPairing.maximum_count,
                  })}
                />
              )}
              {selectedPvInverter && (
                <button type="button" onClick={() => setSpecTarget({ kind: 'pv_inverter', item: selectedPvInverter })}>
                  PV inverter specification
                </button>
              )}
            </>
          )}
        </>
      )}
      {node.kind === 'aux' && (
        <>
          <NumberField label={LABEL.activePowerKw} value={Number(props.p_kw ?? 0)} onChange={(v) => patch({ p_kw: v })} />
          <NumberField label={LABEL.reactivePowerKvar} value={Number(props.q_kvar ?? 0)} onChange={(v) => patch({ q_kvar: v })} />
        </>
      )}
      {node.kind === 'busbar' && (
        <>
          <label className="field">
            <span>Fleet kind</span>
            {/* A fleet's branch may hold more than one busbar in parallel
                (ticket 05): a kind another busbar already uses is not
                disabled here, on the palette, or on the canvas drop. */}
            <select value={String(props.fleet_kind ?? 'pv')} onChange={(e) => patch({ fleet_kind: e.target.value })}>
              {(['pv', 'bess'] as const).map((kind) => (
                <option key={kind} value={kind}>
                  {kind === 'pv' ? 'PV' : 'BESS'}
                </option>
              ))}
            </select>
          </label>
          <SectionTitle>Switchgear pins</SectionTitle>
          {/* An engineer's own rating, checked instead of sized (ADR-0007,
              ticket 04). "Sized" clears the pin. */}
          <SwitchgearPinSelect
            label="Busbar pin"
            pinnedA={typeof props.busbar_switchgear_pin_a === 'number' ? props.busbar_switchgear_pin_a : null}
            onChange={(v) => patch({ busbar_switchgear_pin_a: v })}
          />
          <SwitchgearPinSelect
            label="Export switchgear pin"
            pinnedA={typeof props.export_switchgear_pin_a === 'number' ? props.export_switchgear_pin_a : null}
            onChange={(v) => patch({ export_switchgear_pin_a: v })}
          />
          {trunkEdgesOf(diagram, node.id).map((edge) => {
            const station = edge.source === node.id ? edge.target : edge.source
            const pins = (props.feeder_switchgear_pins_a ?? {}) as Record<string, number>
            return (
              <SwitchgearPinSelect
                key={edge.id}
                label={`Feeder pin → ${station}`}
                pinnedA={typeof pins[edge.id] === 'number' ? pins[edge.id] : null}
                onChange={(v) => {
                  const next = { ...pins }
                  if (v == null) delete next[edge.id]
                  else next[edge.id] = v
                  patch({ feeder_switchgear_pins_a: next })
                }}
              />
            )
          })}
        </>
      )}
      <button type="button" className="danger" onClick={() => removeNode(node.id)}>
        Delete block
      </button>
      {specTarget && (
        <ModalShell size="full" onEscape={() => setSpecTarget(null)}>
          <SpecView
            target={specTarget}
            solutions={catalogue?.bess_solutions ?? []}
            transformers={catalogue?.bess_transformers ?? []}
            pvInverters={catalogue?.pv_inverters ?? []}
            pvTransformers={catalogue?.transformers ?? []}
          />
        </ModalShell>
      )}
      {confirmDialog}
    </div>
  )
}

/** One line of busbar switchgear (ADR-0007): the rating beside its current,
 * marked as sized or pinned (ticket 04) — or, for a SIZED part whose current
 * clears the 4000 A top of the standard ladder, that no standard rating
 * admits it. A pinned rating is never "not sized": it is checked against
 * the pin however high the current. */
function switchgearValue(ratedA: number | null, currentA: number, pinned: boolean): string {
  if (pinned) return `${fmt(ratedA ?? 0, 0)} A (pinned) — ${fmt(currentA, 0)} A`
  return ratedA != null
    ? `${fmt(ratedA, 0)} A (sized) — ${fmt(currentA, 0)} A`
    : `not sized — ${fmt(currentA, 0)} A exceeds the 4,000 A ladder top`
}

/** Read-only computed results for one node, keyed by its id in the last solve
 * — exactly the figures map_results already provides for that kind. */
function NodeResults({ result }: { result?: NodeResult }) {
  // The design's ambient (ADR-0004) — the resolved rating shown below (hv_tx
  // case) is meaningless without it.
  const ambientC = useStore((s) => s.diagram.settings.rules.ambient_temp_c ?? 40)
  if (!result) return <p className="panel-hint">Not yet solved.</p>

  switch (result.kind) {
    case 'station':
      return (
        <>
          <Row label="Loading (%)" value={pct(result.loading)} />
          <Row label={`LV-side ${LABEL.activePowerKw}`} value={fmt(result.p_lv_kw, 1)} />
          <Row label={`LV-side ${LABEL.reactivePowerKvar}`} value={fmt(result.q_lv_kvar, 1)} />
          <Row label={`LV-side ${LABEL.apparentPowerKva}`} value={fmt(result.s_lv_kva, 1)} />
          <Row label="Transformer load loss ΔP (kW)" value={fmt(result.dp_tx_kw, 2)} />
          <Row label="Transformer reactive loss ΔQ (kvar)" value={fmt(result.dq_tx_kvar, 2)} />
        </>
      )
    case 'busbar':
      return (
        <>
          <Row label={`Total ${LABEL.activePowerMw}`} value={fmt(result.p_kw / 1000, 3)} />
          <Row label={`Total ${LABEL.reactivePowerMvar}`} value={fmt(result.q_kvar / 1000, 3)} />
          <Row label="Number of circuits" value={String(result.n_circuits)} />
          <SectionTitle>Busbar switchgear</SectionTitle>
          <Row
            label="Busbar"
            value={switchgearValue(result.switchgear_rated_a, result.i_a, result.switchgear_pinned)}
          />
          <Row
            label="Export switchgear"
            value={switchgearValue(
              result.export_switchgear_rated_a, result.export_i_a, result.export_switchgear_pinned,
            )}
          />
          {result.feeder_i_a.map((current, idx) => (
            <Row
              key={idx}
              label={`Circuit ${idx + 1} feeder`}
              value={switchgearValue(
                result.feeder_switchgear_rated_a[idx], current, result.feeder_switchgear_pinned[idx],
              )}
            />
          ))}
        </>
      )
    case 'aux':
      return (
        <>
          <Row label={LABEL.activePowerKw} value={fmt(result.p_kw ?? 0, 1)} />
          <Row label={LABEL.reactivePowerKvar} value={fmt(result.q_kvar ?? 0, 1)} />
        </>
      )
    case 'hv_tx':
      return (
        <>
          <Row label="Model" value={result.name ?? '—'} />
          <Row
            label={LABEL.sRatedKva}
            value={result.s_rated_kva != null ? `${fmt(result.s_rated_kva)} @ ${ambientC} °C` : '—'}
          />
          <Row label="Parallel units" value={String(result.n_parallel)} />
          <Row label="Load loss ΔP (kW)" value={fmt(result.dp_kw, 2)} />
          <Row label="Reactive loss ΔQ (kvar)" value={fmt(result.dq_kvar, 2)} />
        </>
      )
    case 'poc': {
      const deliveredP = result.p_refined_delivered_kw ?? result.p_delivered_kw
      const deliveredPf = powerFactor(deliveredP, result.q_delivered_kvar)
      return (
        <>
          <Row label={`Target ${LABEL.activePowerMw}`} value={fmt(result.p_target_kw / 1000, 3)} />
          <Row label={`Target ${LABEL.powerFactor}`} value={fmt(result.pf_target, 3)} />
          <Row label={`Delivered ${LABEL.activePowerMw}`} value={fmt(deliveredP / 1000, 3)} />
          <Row label={`Delivered ${LABEL.reactivePowerMvar}`} value={fmt(result.q_delivered_kvar / 1000, 3)} />
          <Row label={`Delivered ${LABEL.powerFactor}`} value={fmt(deliveredPf, 3)} />
        </>
      )
    }
    default:
      return null
  }
}

function EdgeProperties({
  edge,
  sourceKind,
  targetKind,
}: {
  edge: DiagramEdge
  sourceKind?: string
  targetKind?: string
}) {
  const updateEdge = useStore((s) => s.updateEdge)
  const removeEdge = useStore((s) => s.removeEdge)
  const settings = useStore((s) => s.diagram.settings)
  const catalogue = useCatalogue()
  const isAttachment = (sourceKind === 'hv_tx' && targetKind === 'busbar') || sourceKind === 'aux' || targetKind === 'aux'
  const sectionKv = edge.tier === 'hv' ? settings.tiers.hv_kv : settings.tiers.mv_kv
  const cableOptions = sectionKv != null ? (catalogue?.cables[kvGroupKey(sectionKv)] ?? []) : []

  return (
    <div>
      {!isAttachment && (
        <NumberField label={LABEL.lengthM} value={Number(edge.length_m ?? 0)} onChange={(v) => updateEdge(edge.id, { length_m: v })} />
      )}
      <label className="field">
        <span>Sizing</span>
        <select
          value={edge.sizing.mode}
          onChange={(e) =>
            updateEdge(edge.id, {
              sizing: e.target.value === 'forced' ? { mode: 'forced', cable: cableOptions[0]?.name ?? '' } : { mode: 'auto' },
            })
          }
        >
          <option value="auto">Auto</option>
          <option value="forced">Forced section</option>
        </select>
      </label>
      {edge.sizing.mode === 'forced' && (
        <label className="field">
          <span>Cable</span>
          <select value={edge.sizing.cable} onChange={(e) => updateEdge(edge.id, { sizing: { mode: 'forced', cable: e.target.value } })}>
            {cableOptions.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <button type="button" className="danger" onClick={() => removeEdge(edge.id)}>
        Delete cable
      </button>
    </div>
  )
}

/** Read-only computed results for one cable edge, keyed by its id in the last
 * solve — exactly the figures map_results already provides. Attachment edges
 * (aux / hv_tx-busbar) are direct connections, not cable runs, so the engine
 * never sizes or reports a cable for them. */
function EdgeResults({ result, isAttachment }: { result?: EdgeResult; isAttachment: boolean }) {
  if (!result) {
    return <p className="panel-hint">{isAttachment ? 'Direct attachment — no cable to size.' : 'Not yet solved.'}</p>
  }
  if (!result.sized) return <p className="panel-hint">Not sized.</p>

  return (
    <>
      <Row label="Cable" value={result.cable_label} />
      <Row label="Parallel circuits (n)" value={String(result.n_parallel)} />
      <Row label={LABEL.currentA} value={fmt(result.current_a, 1)} />
      <Row label={LABEL.utilizationPct} value={pct(result.utilization)} />
      <Row label="Active loss ΔP (kW)" value={fmt(result.dp_kw, 2)} />
      <Row label="Loss (% of local P)" value={result.loss_percent != null ? `${fmt(result.loss_percent, 2)}%` : '—'} />
      {result.vdrop_percent != null && <Row label="Voltage drop (%)" value={`${fmt(result.vdrop_percent, 2)}%`} />}
    </>
  )
}

export function Inspector() {
  const selection = useStore((s) => s.selection)
  const diagram = useStore((s) => s.diagram)
  const results = useStore((s) => s.results)
  const catalogue = useCatalogue()
  const [specViewOpen, setSpecViewOpen] = useState(false)

  if (!selection) {
    return (
      <CollapsiblePanel title="Inspector" side="right" className="inspector">
        <p className="panel-hint">Select a block or cable to edit its properties, or click a catalogue item to preview it.</p>
      </CollapsiblePanel>
    )
  }

  if (selection.type === 'palette') {
    const tx = catalogue?.transformers.find((t) => t.key === selection.key)
    // A BESS solution or BESS station transformer selected in the palette
    // gets a control to open its full specification full-screen (ticket 04).
    // Ticket 06: a BESS station transformer now gets the same compact
    // TransformerPreview card the PV branch already had — it was previously
    // falling through to "Loading…" because this lookup only checked the PV
    // catalogue.
    const bessTx = catalogue?.bess_transformers.find((t) => t.key === selection.key)
    const bessSolution = catalogue?.bess_solutions.find((s) => s.key === selection.key)
    const previewTx = tx ?? bessTx
    const specTarget = bessTx
      ? ({ kind: 'transformer_station', fleet_kind: 'bess', item: bessTx } as const)
      : bessSolution
        ? ({ kind: 'bess_solution', item: bessSolution } as const)
        : tx
          ? ({ kind: 'transformer_station', fleet_kind: 'pv', item: tx } as const)
          : null

    return (
      <CollapsiblePanel title="Inspector" side="right" className="inspector">
        <SectionTitle>Catalogue preview</SectionTitle>
        {previewTx && <TransformerPreview tx={previewTx} />}
        {bessSolution && <h3>{bessSolution.display_name}</h3>}
        {specTarget && (
          <button type="button" onClick={() => setSpecViewOpen(true)}>
            View full specification
          </button>
        )}
        {!previewTx && !bessSolution && <p className="panel-hint">Loading…</p>}
        {specViewOpen && specTarget && (
          <ModalShell size="full" onEscape={() => setSpecViewOpen(false)}>
            <SpecView
              target={specTarget}
              solutions={catalogue?.bess_solutions ?? []}
              transformers={catalogue?.bess_transformers ?? []}
            />
          </ModalShell>
        )}
      </CollapsiblePanel>
    )
  }

  if (selection.type === 'node') {
    const node = diagram.nodes.find((n) => n.id === selection.id)
    return (
      <CollapsiblePanel title="Inspector" side="right" className="inspector">
        {node ? (
          <>
            <p className="panel-hint">{node.kind}</p>
            <SectionTitle>Properties</SectionTitle>
            <NodeProperties key={node.id} node={node} />
            <SectionTitle>Results</SectionTitle>
            <NodeResults result={results?.nodes[node.id]} />
          </>
        ) : (
          <p className="panel-hint">Block not found.</p>
        )}
      </CollapsiblePanel>
    )
  }

  const edge = diagram.edges.find((e) => e.id === selection.id)
  const sourceKind = diagram.nodes.find((n) => n.id === edge?.source)?.kind
  const targetKind = diagram.nodes.find((n) => n.id === edge?.target)?.kind
  const isAttachment = (sourceKind === 'hv_tx' && targetKind === 'busbar') || sourceKind === 'aux' || targetKind === 'aux'
  return (
    <CollapsiblePanel title="Inspector" side="right" className="inspector">
      {edge ? (
        <>
          <p className="panel-hint">Cable</p>
          <SectionTitle>Properties</SectionTitle>
          <EdgeProperties edge={edge} sourceKind={sourceKind} targetKind={targetKind} />
          <SectionTitle>Results</SectionTitle>
          <EdgeResults result={results?.edges[edge.id]} isAttachment={isAttachment} />
        </>
      ) : (
        <p className="panel-hint">Cable not found.</p>
      )}
    </CollapsiblePanel>
  )
}
