import { fmt, kvGroupKey, pct, powerFactor } from '../format'
import { CollapsiblePanel } from './CollapsiblePanel'
import { LABEL } from '../labels'
import { useCatalogue } from '../hooks/useCatalogue'
import { useStore } from '../store'
import { takenBusbarSlots } from '../canvas/connect'
import type { DiagramEdge, DiagramNode, EdgeResult, NodeResult, TransformerInfo } from '../types'

function NumberField({
  label,
  value,
  onChange,
  step = 1,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  step?: number
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type="number" step={step} value={Number.isFinite(value) ? value : ''} onChange={(e) => onChange(e.target.valueAsNumber)} />
    </label>
  )
}

/** Read-only "label: value" row, used for the catalogue preview and every
 * Results section. */
function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="kv-row">
      <span className="k">{label}</span>
      <span className="v">{value}</span>
    </div>
  )
}

function SectionTitle({ children }: { children: string }) {
  return <h3 className="inspector-section-title">{children}</h3>
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

/** Read-only preview of a catalogue transformer, shown in the Inspector when
 * a palette item is clicked (not dragged) — see Palette.tsx. */
function TransformerPreview({ tx }: { tx: TransformerInfo }) {
  return (
    <div>
      <h3>{tx.key}</h3>
      <Row label={LABEL.brand} value={tx.brand ?? '—'} />
      <Row label={LABEL.sRatedKva} value={fmt(tx.s_rated_kva)} />
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
  const patch = (p: Record<string, unknown>) => updateNodeProps(node.id, p)
  const props = node.props

  return (
    <div>
      {node.kind === 'poc' && (
        <>
          <NumberField label={`PV target ${LABEL.activePowerMw}`} value={Number(props.p_target_mw ?? 0)} step={0.1} onChange={(v) => patch({ p_target_mw: v })} />
          <NumberField label={`BESS target ${LABEL.activePowerMw}`} value={Number(props.p_target_bess_mw ?? 0)} step={0.1} onChange={(v) => patch({ p_target_bess_mw: v })} />
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
                    {tx.key}
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
              <select value={String(props.model ?? '')} onChange={(e) => patch({ model: e.target.value })}>
                <option value="">— select —</option>
                {(props.fleet_kind === 'bess' ? catalogue?.bess_transformers : catalogue?.transformers)?.map((tx) => (
                  <option key={tx.key} value={tx.key}>
                    {tx.key}
                  </option>
                ))}
              </select>
            </label>
          )}
          {props.mode === 'custom' && <CustomTransformerFields props={props} onChange={patch} />}
          {props.fleet_kind === 'bess' && (
            <label className="field">
              <span>BESS solution</span>
              <select value={String(props.bess_solution ?? '')} onChange={(e) => patch({ bess_solution: e.target.value })}>
                <option value="">— select —</option>
                {catalogue?.bess_solutions.map((sol) => (
                  <option key={sol.key} value={sol.key}>
                    {sol.key}
                  </option>
                ))}
              </select>
            </label>
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
        <label className="field">
          <span>Fleet kind</span>
          {/* A kind another busbar already occupies is disabled rather than
              hidden: the engineer can see the option exists and why it is not
              available, and cannot use this control to create the duplicate the
              palette and the canvas both refuse. */}
          <select value={String(props.fleet_kind ?? 'pv')} onChange={(e) => patch({ fleet_kind: e.target.value })}>
            {(['pv', 'bess'] as const).map((kind) => (
              <option key={kind} value={kind} disabled={takenBusbarSlots(diagram, node.id).has(kind)}>
                {kind === 'pv' ? 'PV' : 'BESS'}
                {takenBusbarSlots(diagram, node.id).has(kind) ? ' — already used' : ''}
              </option>
            ))}
          </select>
        </label>
      )}
      <button type="button" className="danger" onClick={() => removeNode(node.id)}>
        Delete block
      </button>
    </div>
  )
}

/** Read-only computed results for one node, keyed by its id in the last solve
 * — exactly the figures map_results already provides for that kind. */
function NodeResults({ result }: { result?: NodeResult }) {
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
          <Row label={LABEL.sRatedKva} value={result.s_rated_kva != null ? fmt(result.s_rated_kva) : '—'} />
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

  if (!selection) {
    return (
      <CollapsiblePanel title="Inspector" side="right" className="inspector">
        <p className="panel-hint">Select a block or cable to edit its properties, or click a catalogue item to preview it.</p>
      </CollapsiblePanel>
    )
  }

  if (selection.type === 'palette') {
    const tx = catalogue?.transformers.find((t) => t.key === selection.key)
    return (
      <CollapsiblePanel title="Inspector" side="right" className="inspector">
        <SectionTitle>Catalogue preview</SectionTitle>
        {tx ? <TransformerPreview tx={tx} /> : <p className="panel-hint">Loading…</p>}
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
            <NodeProperties node={node} />
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
