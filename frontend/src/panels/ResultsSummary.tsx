import { useMemo, useState } from 'react'
import { evaluateCompliance } from '../compliance'
import { fmt, pct } from '../format'
import { conversionLabelPlural } from '../fleet'
import { useStore } from '../store'
import { ResultsTables } from './ResultsTables'

export function ResultsSummary() {
  const [open, setOpen] = useState(true)
  const [showTables, setShowTables] = useState(false)
  const results = useStore((s) => s.results)
  const issues = useStore((s) => s.issues)
  const solving = useStore((s) => s.solving)

  const verdict = useMemo(() => (results ? evaluateCompliance(results, issues) : null), [results, issues])
  // Named after the fleet when there is only one, so a battery project reads
  // "PCS units" here and in the tables modal alike. A hybrid's row covers both
  // fleets, so it stays neutral rather than borrowing one fleet's word for the
  // other's equipment — the per-fleet blocks in the modal name them properly.
  const branches = results?.summary.branches ?? []
  const devices = branches.length === 1 ? conversionLabelPlural(branches[0].kind) : 'conversion devices'

  return (
    <div className="results-summary">
      <button type="button" className="results-toggle" onClick={() => setOpen((v) => !v)}>
        {open ? '▾' : '▸'} Results
        {verdict && <span className={`compliance-dot ${verdict.compliant ? 'ok' : 'bad'}`} aria-hidden="true" />}
        {solving && <span className="solving-badge">solving…</span>}
      </button>
      {open && (
        <>
          {!results && <p className="panel-hint">Draw a valid plant to see results.</p>}
          {results && verdict && (
            <div className={`compliance-banner ${verdict.compliant ? 'ok' : 'bad'}`}>
              <div className="compliance-verdict">{verdict.compliant ? 'COMPLIANT' : 'NOT COMPLIANT'}</div>
              {!verdict.compliant && (
                <ul className="compliance-reasons">
                  {verdict.reasons.map((reason, i) => (
                    <li key={i}>{reason}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {results && (
            <div className="results-grid">
              <div>
                <span className="label">{devices[0].toUpperCase() + devices.slice(1)}</span>
                <span className="value">
                  {fmt(results.summary.p_inv_refined_kw / 1000, 2)} MW / {fmt(results.summary.q_inv_refined_kvar / 1000, 2)} Mvar /{' '}
                  {fmt(results.summary.s_inv_refined_kva / 1000, 2)} MVA
                </span>
              </div>
              <div>
                <span className="label">POC delivered</span>
                <span className="value">
                  {fmt((results.summary.p_poc_refined_delivered_kw ?? results.summary.p_poc_delivered_kw) / 1000, 2)} MW /{' '}
                  target {fmt(results.summary.p_poc_target_kw / 1000, 2)} MW
                </span>
              </div>
              <div>
                <span className="label">Fleet loading</span>
                <span className="value">{pct(results.summary.fleet_loading)}</span>
              </div>
              <div>
                <span className="label">Total losses</span>
                <span className="value">{fmt(results.summary.total_active_loss_kw, 1)} kW</span>
              </div>
              <div>
                <span className="label">Circuits</span>
                <span className="value">{results.summary.n_circuits} ({results.summary.circuit_sizes.join(', ')})</span>
              </div>
            </div>
          )}
          {/* A BESS design has to answer two more questions than a PV one: how
              many containers it needs, and how much energy it delivers against
              what it owes. Both are read off the supplier's own table, so they
              belong in front of the engineer rather than only inside a
              compliance failure message. */}
          {results?.summary.branches
            .filter((branch) => branch.kind === 'bess' && branch.containers != null)
            .map((branch) => (
              <div className="results-grid" key={branch.kind}>
                <div>
                  <span className="label">BESS containers</span>
                  <span className="value">{branch.containers}</span>
                </div>
                <div>
                  <span className="label">Energy delivered</span>
                  <span className={`value${branch.energy_ok === false ? ' bad' : ''}`}>
                    {fmt((branch.e_delivered_kwh ?? 0) / 1000, 1)} MWh
                    {branch.e_required_kwh != null &&
                      ` / needs ${fmt(branch.e_required_kwh / 1000, 1)} MWh`}
                  </span>
                </div>
                <div>
                  <span className="label">Container auxiliaries</span>
                  <span className="value">
                    {fmt(branch.bess_aux_p_kw, 0)} kW / {fmt(branch.bess_aux_q_kvar, 0)} kvar
                  </span>
                </div>
              </div>
            ))}
          {results && (
            <button type="button" className="results-tables-link" onClick={() => setShowTables(true)}>
              Full results…
            </button>
          )}
        </>
      )}
      {showTables && <ResultsTables onClose={() => setShowTables(false)} />}
    </div>
  )
}
