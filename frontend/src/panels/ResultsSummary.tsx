import { useMemo, useState } from 'react'
import { evaluateCompliance } from '../compliance'
import { fmt, pct } from '../format'
import { useStore } from '../store'

export function ResultsSummary() {
  const [open, setOpen] = useState(true)
  const results = useStore((s) => s.results)
  const issues = useStore((s) => s.issues)
  const solving = useStore((s) => s.solving)

  const verdict = useMemo(() => (results ? evaluateCompliance(results, issues) : null), [results, issues])

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
                <span className="label">Inverters</span>
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
        </>
      )}
    </div>
  )
}
