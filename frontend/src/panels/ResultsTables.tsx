import { nodeLabel } from '../canvas/nodeData'
import { ModalShell } from '../components/Modal'
import { fmt, pct, powerFactor } from '../format'
import { useStore } from '../store'
import type {
  Diagram,
  HvTxNodeResult,
  SolveResults,
  StationNodeResult,
} from '../types'

/** The full solve, element by element — the same tables the Markdown/PDF report
 * carries (powertool/report.py `_transformer_table` / `_cable_table`), but per
 * unit rather than aggregated by model, so every row maps to a block on the
 * canvas. */
export function ResultsTables({ onClose }: { onClose: () => void }) {
  const diagram = useStore((s) => s.diagram)
  const results = useStore((s) => s.results)
  if (!results) return null

  return (
    <ModalShell onEscape={onClose} size="xl">
      <h2>Full results</h2>
      <div className="results-tables">
        <PlantSummary results={results} />
        <Stations diagram={diagram} results={results} />
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

function PlantSummary({ results }: { results: SolveResults }) {
  const s = results.summary
  const delivered = s.p_poc_refined_delivered_kw ?? s.p_poc_delivered_kw
  return (
    <section>
      <h3>Plant summary</h3>
      <div className="results-figures">
        <Row
          label="Required inverters"
          value={`${fmt(s.p_inv_refined_kw / 1000, 2)} MW / ${fmt(s.q_inv_refined_kvar / 1000, 2)} Mvar / ${fmt(s.s_inv_refined_kva / 1000, 2)} MVA`}
        />
        <Row label="Power factor at inverter" value={fmt(s.pf_inv, 3)} />
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
          value={`${fmt(s.worst_trunk_current_a, 0)} A / cap ${fmt(s.max_circuit_current_a, 0)} A${s.all_current_ok ? '' : ' — OVER'}`}
        />
        <Row label="Cable losses" value={`${fmt(s.total_cable_loss_kw, 1)} kW`} />
        <Row label="Transformer losses" value={`${fmt(s.total_transformer_loss_kw, 1)} kW`} />
        <Row
          label="Total active losses"
          value={`${fmt(s.total_active_loss_kw, 1)} kW (${fmt(s.loss_percent_of_p_inv, 2)}% of P inverter)`}
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
            </tr>
          </thead>
          <tbody>
            {rows.map(({ node, result }) => (
              <tr key={node.id}>
                <td className="row-name">{nodeLabel(node)}</td>
                <td>
                  C{result.circuit}·{result.position}
                </td>
                <td className="num">{fmt(result.s_rated_kva, 0)}</td>
                <td className="num">{pct(result.loading)}</td>
                <td className="num">{fmt(result.s_lv_kva, 1)}</td>
                <td className="num">{fmt(result.dp_tx_kw, 2)}</td>
                <td className="num">{fmt(result.dq_tx_kvar, 2)}</td>
                <td className="num">{fmt(result.s_mv_kva, 1)}</td>
                <td className="num">{fmt(result.i_a, 1)}</td>
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
                  {fmt(result.s_rated_kva, 0)}
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
              </tr>
            ))}
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
