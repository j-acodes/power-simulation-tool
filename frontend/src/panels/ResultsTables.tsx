import { useState } from 'react'
import { conversionLabel, conversionLabelPlural, fleetLabel } from '../fleet'
import { reportPdf, sldPdf } from '../api'
import { nodeLabel } from '../canvas/nodeData'
import { ModalShell } from '../components/Modal'
import { fmt, pct, powerFactor } from '../format'
import { useStore } from '../store'
import type {
  BindingLimit,
  BusbarNodeResult,
  Diagram,
  HvTxNodeResult,
  SolveResults,
  StationNodeResult,
} from '../types'

// The top of the busbar switchgear standard rating ladder (ADR-0007) — a
// busbar or export switchgear above this has no admissible standard size.
// Mirrors powertool.components.BUSBAR_SWITCHGEAR_LADDER_A[-1].
const BUSBAR_LADDER_TOP_A = 4000

// Plain-word labels for a circuit's binding limit (ticket 07's owner
// decision) — see powertool.architecture.circuit_binding_limit.
const BINDING_LIMIT_LABEL: Record<BindingLimit, string> = {
  station_switchgear: 'Station switchgear',
  cable_entry: 'Cable entry',
  feeder: 'Feeder',
}

/** The full solve, element by element — the same tables the Markdown/PDF report
 * carries (powertool/report.py `_transformer_table` / `_cable_table`), but per
 * unit rather than aggregated by model, so every row maps to a block on the
 * canvas. */
export function ResultsTables({ onClose }: { onClose: () => void }) {
  const diagram = useStore((s) => s.diagram)
  const results = useStore((s) => s.results)
  const designMeta = useStore((s) => s.designMeta)
  const [reporting, setReporting] = useState(false)
  const [reportError, setReportError] = useState<string | null>(null)
  const [buildingSld, setBuildingSld] = useState(false)
  const [sldError, setSldError] = useState<string | null>(null)

  /** Download the PDF sizing report. The diagram has to be POSTed, so the
   * browser can't just be handed a URL — the response Blob is saved through an
   * object URL instead. */
  const downloadReport = async () => {
    setReporting(true)
    setReportError(null)
    try {
      const name = designMeta?.name ?? 'Plant'
      const blob = await reportPdf(diagram, name)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${name}-sizing-report.pdf`
      link.click()
      // Revoking synchronously after click can cancel the download.
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setReportError(err instanceof Error ? err.message : String(err))
    } finally {
      setReporting(false)
    }
  }

  /** Download the standalone SLD PDF, same pattern as the report download. */
  const downloadSld = async () => {
    setBuildingSld(true)
    setSldError(null)
    try {
      const name = designMeta?.name ?? 'Plant'
      const blob = await sldPdf(diagram, name, designMeta?.projectId)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${name}-sld.pdf`
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setSldError(err instanceof Error ? err.message : String(err))
    } finally {
      setBuildingSld(false)
    }
  }

  if (!results) return null

  return (
    <ModalShell onEscape={onClose} size="xl">
      <div className="results-tables-header">
        <h2>Full results</h2>
        <button type="button" className="btn-primary" onClick={downloadReport} disabled={reporting}>
          {reporting ? 'Building…' : 'Report (PDF)'}
        </button>
        <button type="button" className="btn-primary" onClick={downloadSld} disabled={buildingSld}>
          {buildingSld ? 'Building…' : 'SLD (PDF)'}
        </button>
      </div>
      {reportError && <p className="error">Report: {reportError}</p>}
      {sldError && <p className="error">SLD: {sldError}</p>}
      <div className="results-tables">
        <PlantSummary results={results} />
        <FleetSummaries results={results} />
        <Stations diagram={diagram} results={results} />
        <Busbars diagram={diagram} results={results} />
        <Cables diagram={diagram} results={results} />
      </div>
      <div className="modal-actions">
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
    </ModalShell>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="label">{label}</span>
      <span className="value">{value}</span>
    </div>
  )
}

/** One block per fleet, shown only when there is more than one.
 *
 * A hybrid's two fleets are two independent cascades that happen to share an
 * export step, so merging their figures into the plant table would produce
 * numbers belonging to no fleet in particular — which is exactly what a design
 * reviewer cannot act on. */
function FleetSummaries({ results }: { results: SolveResults }) {
  const branches = results.summary.branches
  if (branches.length < 2) return null
  return (
    <>
      {branches.map((branch) => (
        <section key={branch.kind}>
          <h3>{`${fleetLabel(branch.kind)} fleet`}</h3>
          <div className="results-figures">
            <Row
              label={`Required ${conversionLabelPlural(branch.kind)}`}
              value={`${fmt(branch.p_inv_refined_kw / 1000, 2)} MW / ${fmt(branch.q_inv_refined_kvar / 1000, 2)} Mvar / ${fmt(branch.s_inv_refined_kva / 1000, 2)} MVA`}
            />
            <Row
              label="Fleet loading"
              value={`${pct(branch.fleet_loading)} of ${pct(branch.max_loading)} max${branch.loading_ok ? '' : ' — OVERLOADED'}`}
            />
            <Row
              label="POC delivered"
              value={`${fmt((branch.p_poc_refined_delivered_kw ?? branch.p_poc_delivered_kw) / 1000, 2)} MW / target ${fmt((branch.p_poc_target_kw ?? 0) / 1000, 2)} MW`}
            />
            {branch.containers != null && <Row label="Containers" value={String(branch.containers)} />}
            {branch.e_delivered_kwh != null && branch.e_required_kwh != null && (
              <Row
                label="Delivered energy"
                value={`${fmt(branch.e_delivered_kwh / 1000, 1)} MWh / needs ${fmt(branch.e_required_kwh / 1000, 1)} MWh${branch.energy_ok ? '' : ' — SHORT'}`}
              />
            )}
            {branch.bess_aux_p_kw > 0 && (
              <Row
                label="Container auxiliaries"
                value={`${fmt(branch.bess_aux_p_kw, 0)} kW / ${fmt(branch.bess_aux_q_kvar, 0)} kvar — separately supplied`}
              />
            )}
          </div>
        </section>
      ))}
    </>
  )
}

function PlantSummary({ results }: { results: SolveResults }) {
  const s = results.summary
  const delivered = s.p_poc_refined_delivered_kw ?? s.p_poc_delivered_kw
  // A single-fleet plant's conversion device is named after that fleet; a
  // hybrid's plant-level row covers both, so it stays neutral rather than
  // picking one fleet's word for the other's equipment. Per-fleet figures are
  // named individually in FleetSummaries below.
  const single = s.branches.length === 1 ? s.branches[0].kind : undefined
  const device = s.branches.length === 1 ? conversionLabel(single) : 'conversion'
  const devices = s.branches.length === 1 ? conversionLabelPlural(single) : 'conversion devices'
  return (
    <section>
      <h3>Plant summary</h3>
      <div className="results-figures">
        <Row
          label={`Required ${devices}`}
          value={`${fmt(s.p_inv_refined_kw / 1000, 2)} MW / ${fmt(s.q_inv_refined_kvar / 1000, 2)} Mvar / ${fmt(s.s_inv_refined_kva / 1000, 2)} MVA`}
        />
        <Row label={`Power factor at ${device}`} value={fmt(s.pf_inv, 3)} />
        <Row label="Loss-cascade correction" value={fmt(s.correction_factor, 4)} />
        <Row
          label="POC delivered"
          value={`${fmt(delivered / 1000, 2)} MW / target ${fmt(s.p_poc_target_kw / 1000, 2)} MW`}
        />
        <Row
          label="Power factor at POC"
          value={fmt(powerFactor(delivered, s.q_poc_delivered_kvar), 3)}
        />
        <Row
          label="Station fleet"
          value={`${s.n_stations} stations — ${fmt(s.s_fleet_kva / 1000, 2)} MVA installed`}
        />
        <Row label="Fleet loading" value={`${pct(s.fleet_loading)}${s.loading_ok ? '' : ' — OVERLOADED'}`} />
        <Row label="MV circuits" value={`${s.n_circuits} (${s.circuit_sizes.join(', ')})`} />
        <Row
          label="Worst trunk current"
          value={`${fmt(s.worst_trunk_current_a, 0)} A`}
        />
        <Row
          label="Station switchgear"
          value={s.all_current_ok ? 'Every station within its rating' : 'A STATION IS OVER ITS RATING — see warnings'}
        />
        <Row label="Cable losses" value={`${fmt(s.total_cable_loss_kw, 1)} kW`} />
        <Row label="Transformer losses" value={`${fmt(s.total_transformer_loss_kw, 1)} kW`} />
        <Row
          label="Total active losses"
          value={`${fmt(s.total_active_loss_kw, 1)} kW (${fmt(s.loss_percent_of_p_inv, 2)}% of P ${device})`}
        />
        <Row
          label="Voltages"
          value={`MV ${fmt(s.v_mv_kv, 1)} kV${s.v_hv_kv != null ? ` / HV ${fmt(s.v_hv_kv, 1)} kV` : ' — MV interconnection'}`}
        />
        <Row label="Power balance" value={s.power_balance_ok ? 'OK' : 'FAILED'} />
      </div>
    </section>
  )
}

function Stations({ diagram, results }: { diagram: Diagram; results: SolveResults }) {
  // The design's ambient (ADR-0004) — a resolved rating is meaningless
  // without it, so every rating cell below carries it as a plain suffix.
  const ambientC = diagram.settings.rules.ambient_temp_c ?? 40

  const rows = diagram.nodes
    .map((node) => ({ node, result: results.nodes[node.id] }))
    .filter((r) => r.result?.kind === 'station')
    .map((r) => ({ node: r.node, result: r.result as StationNodeResult }))
    .sort((a, b) => a.result.circuit - b.result.circuit || a.result.position - b.result.position)

  const hvRows = diagram.nodes
    .map((node) => ({ node, result: results.nodes[node.id] }))
    .filter((r) => r.result?.kind === 'hv_tx')
    .map((r) => ({ node: r.node, result: r.result as HvTxNodeResult }))

  if (rows.length === 0 && hvRows.length === 0) return null

  return (
    <section>
      <h3>Transformers</h3>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Block</th>
              <th>Circuit</th>
              <th className="num">Rating [kVA]</th>
              <th className="num">Loading</th>
              <th className="num">S LV [kVA]</th>
              <th className="num">ΔP [kW]</th>
              <th className="num">ΔQ [kvar]</th>
              <th className="num">S MV [kVA]</th>
              <th className="num">Current [A]</th>
              <th className="num">Through / rated [A]</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ node, result }) => (
              <tr key={node.id}>
                <td className="row-name">{nodeLabel(node)}</td>
                <td>
                  C{result.circuit}·{result.position}
                </td>
                <td className="num">{fmt(result.s_rated_kva, 0)} @ {ambientC} °C</td>
                <td className="num">{pct(result.loading)}</td>
                <td className="num">{fmt(result.s_lv_kva, 1)}</td>
                <td className="num">{fmt(result.dp_tx_kw, 2)}</td>
                <td className="num">{fmt(result.dq_tx_kvar, 2)}</td>
                <td className="num">{fmt(result.s_mv_kva, 1)}</td>
                <td className="num">{fmt(result.i_a, 1)}</td>
                <td className="num">
                  {fmt(result.through_current_a, 0)} / {fmt(result.switchgear_rated_current_a, 0)}
                </td>
              </tr>
            ))}
            {hvRows.map(({ node, result }) => (
              <tr key={node.id}>
                <td className="row-name">
                  {nodeLabel(node)}
                  {result.name ? ` — ${result.name}` : ''}
                </td>
                <td>MV/HV</td>
                <td className="num">
                  {fmt(result.s_rated_kva, 0)} @ {ambientC} °C
                  {result.n_parallel > 1 ? ` ×${result.n_parallel}` : ''}
                </td>
                <td className="num">
                  {result.s_rated_kva
                    ? pct(result.s_through_kva / (result.s_rated_kva * result.n_parallel))
                    : '—'}
                </td>
                <td className="num">—</td>
                <td className="num">{fmt(result.dp_kw, 2)}</td>
                <td className="num">{fmt(result.dq_kvar, 2)}</td>
                <td className="num">{fmt(result.s_through_kva, 1)}</td>
                <td className="num">—</td>
                <td className="num">—</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function Busbars({ diagram, results }: { diagram: Diagram; results: SolveResults }) {
  const feedersPerBusbar = diagram.settings.rules.feeders_per_busbar ?? 12

  const rows = diagram.nodes
    .map((node) => ({ node, result: results.nodes[node.id] }))
    .filter((r) => r.result?.kind === 'busbar')
    .map((r) => ({ node: r.node, result: r.result as BusbarNodeResult }))

  if (rows.length === 0) return null

  return (
    <section>
      <h3>Busbars</h3>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Busbar</th>
              <th className="num">Feeders</th>
              <th className="num">Current [A]</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ node, result }) => (
              <tr key={node.id}>
                <td className="row-name">{nodeLabel(node)}</td>
                <td className="num">
                  {result.n_circuits} / {feedersPerBusbar}
                </td>
                <td className="num">
                  {fmt(result.i_a, 0)} / {BUSBAR_LADDER_TOP_A} A
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>Circuits</h3>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Busbar</th>
              <th>Circuit</th>
              <th>Binding limit</th>
              <th className="num">Feeder current [A]</th>
            </tr>
          </thead>
          <tbody>
            {rows.flatMap(({ node, result }) =>
              result.feeder_binding_limit.map((limit, i) => (
                <tr key={`${node.id}-${i}`}>
                  <td className="row-name">{nodeLabel(node)}</td>
                  <td>Circuit {i + 1}</td>
                  <td>{BINDING_LIMIT_LABEL[limit]}</td>
                  <td className="num">{fmt(result.feeder_i_a[i], 1)}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function Cables({ diagram, results }: { diagram: Diagram; results: SolveResults }) {
  const byId = new Map(diagram.nodes.map((n) => [n.id, n]))

  /** "HUAWEI_JUPITER9000 (C1·2)" — the circuit position is what tells two
   * identical station models apart in a run. */
  const endpoint = (id: string): string => {
    const node = byId.get(id)
    if (!node) return id
    const result = results.nodes[id]
    const where = result?.kind === 'station' ? ` (C${result.circuit}·${result.position})` : ''
    return nodeLabel(node) + where
  }
  const rows = diagram.edges
    .map((edge) => ({ edge, result: results.edges[edge.id] }))
    .filter((r) => r.result !== undefined)

  if (rows.length === 0) return null

  return (
    <section>
      <h3>Cables</h3>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Run</th>
              <th>Tier</th>
              <th>Cable</th>
              <th className="num">Circuits</th>
              <th className="num">Length [m]</th>
              <th className="num">S [kVA]</th>
              <th className="num">Current [A]</th>
              <th className="num">Util.</th>
              <th className="num">Loss %</th>
              <th className="num">V-drop %</th>
              <th className="num">ΔP [kW]</th>
              <th className="num">ΔQ series [kvar]</th>
              <th className="num">Q charging [kvar]</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ edge, result }) => {
              return (
                <tr key={edge.id}>
                  <td className="row-name">
                    {endpoint(edge.source)} → {endpoint(edge.target)}
                  </td>
                  <td>{edge.tier.toUpperCase()}</td>
                  <td>
                    {result.cable_label}
                    {result.forced ? ' (forced)' : ''}
                  </td>
                  <td className="num">{result.n_parallel}</td>
                  <td className="num">{fmt(result.length_m, 0)}</td>
                  <td className="num">{fmt(result.s_kva, 1)}</td>
                  <td className="num">{fmt(result.current_a, 1)}</td>
                  <td className="num">{pct(result.utilization)}</td>
                  <td className="num">{fmt(result.loss_percent, 2)}</td>
                  <td className="num">{fmt(result.vdrop_percent, 2)}</td>
                  <td className="num">{fmt(result.dp_kw, 2)}</td>
                  <td className="num">{fmt(result.dq_series_kvar, 2)}</td>
                  <td className="num">{fmt(result.q_charging_kvar, 2)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
