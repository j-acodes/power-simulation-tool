import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import '../App.css'
import { solveStage1 } from '../api'
import { DisplayNameControl } from '../components/DisplayName'
import { useCatalogue } from '../hooks/useCatalogue'
import { fmt } from '../format'
import { LABEL } from '../labels'
import type { CatalogueResponse, Stage1Element, Stage1Request, Stage1Response } from '../types'

// TEMPORARY PAGE (plan section "Stage 1 conceptual mode"): a plain form
// replicating the frozen Streamlit Stage-1 tab against POST /api/stage1, with
// no canvas features. Deleted once the diagram editor's own results fully
// cover this conceptual-sizing use case.

type ElementDraft = Stage1Element & { id: string }

let idCounter = 0
function nextId(): string {
  idCounter += 1
  return `el-${idCounter}`
}

function detailFor(e: Stage1Element, catalogue: CatalogueResponse | null): string {
  if (e.type === 'Transformer') {
    const tx = catalogue?.transformers.find((t) => t.key === e.component)
    return `${tx?.display_name ?? e.component} (x${e.n_parallel})`
  }
  if (e.type === 'Cable section') return 'auto-sized (worst-case budget)'
  return `P=${e.p_kw} kW, Q=${e.q_kvar} kvar`
}

/** `/stage1` — temporary conceptual-sizing form page: POC inputs, an ordered
 * element list builder, and a Stage-1 results card. See backend/schemas.py
 * (Stage1Request/Stage1Response) for the exact shapes this mirrors. */
export function Stage1Page() {
  const catalogue = useCatalogue()

  const [pPocMw, setPPocMw] = useState(45.0)
  const [pfTarget, setPfTarget] = useState(0.95)
  const [interconnection, setInterconnection] = useState<'HV' | 'MV'>('HV')
  const [vExportKv, setVExportKv] = useState(132.0)
  const [exportM, setExportM] = useState(0)

  const [elements, setElements] = useState<ElementDraft[]>([])

  const [draftType, setDraftType] = useState<Stage1Element['type']>('Transformer')
  const [draftComponent, setDraftComponent] = useState('')
  const [draftVKv, setDraftVKv] = useState(20.0)
  const [draftNParallel, setDraftNParallel] = useState(1)
  const [draftLabel, setDraftLabel] = useState('')
  const [draftPKw, setDraftPKw] = useState(100.0)
  const [draftQKvar, setDraftQKvar] = useState(0.0)

  const [solving, setSolving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Stage1Response | null>(null)

  useEffect(() => {
    if (!catalogue) return
    setDraftComponent((c) => c || catalogue.transformers[0]?.key || '')
    setDraftVKv((v) => v || catalogue.defaults.tiers.mv_kv)
    setVExportKv((v) => v || catalogue.defaults.tiers.hv_kv)
  }, [catalogue])

  const addElement = () => {
    // Always send a string (possibly empty), never null/undefined: the
    // backend's loss cascade names each element from this field verbatim and
    // chokes on a missing label (see backend/schemas.py LossItem.label) — the
    // frozen Streamlit form sidesteps this the same way (text_input defaults
    // to "").
    const label = draftLabel.trim()
    let element: Stage1Element
    if (draftType === 'Transformer') {
      if (!draftComponent) return
      element = { type: 'Transformer', component: draftComponent, v_kv: draftVKv, n_parallel: draftNParallel, label }
    } else if (draftType === 'Cable section') {
      element = { type: 'Cable section', v_kv: draftVKv, label }
    } else {
      element = { type: 'Aux load', v_kv: draftVKv, p_kw: draftPKw, q_kvar: draftQKvar, label }
    }
    setElements((els) => [...els, { ...element, id: nextId() }])
    setDraftLabel('')
  }

  const removeElement = (id: string) => setElements((els) => els.filter((e) => e.id !== id))

  const moveElement = (id: string, delta: -1 | 1) => {
    setElements((els) => {
      const i = els.findIndex((e) => e.id === id)
      const j = i + delta
      if (i < 0 || j < 0 || j >= els.length) return els
      const next = [...els]
      ;[next[i], next[j]] = [next[j], next[i]]
      return next
    })
  }

  const clearElements = () => setElements([])

  const solve = async () => {
    setSolving(true)
    setError(null)
    try {
      const payload: Stage1Request = {
        p_poc_kw: pPocMw * 1000,
        pf_target: pfTarget,
        interconnection,
        v_export_kv: vExportKv,
        export_m: exportM,
        elements: elements.map(({ id: _id, ...e }) => e),
      }
      const res = await solveStage1(payload)
      setResult(res)
    } catch (err) {
      setError(String(err))
      setResult(null)
    } finally {
      setSolving(false)
    }
  }

  return (
    <div className="app stage1-page">
      <header className="app-header">
        <div className="app-header-title">
          <Link to="/" className="header-link">
            ← Projects
          </Link>
          <h1>Stage 1 — Conceptual sizing</h1>
        </div>
        <div className="app-header-actions">
          <DisplayNameControl />
        </div>
      </header>
      <p className="panel-hint stage1-note">
        Quick no-layout estimate: the required inverter capacity for a POC target over a lumped chain, with no
        drawing involved. Temporary page — the diagram editor will fully replace it.
      </p>

      <div className="app-body stage1-body">
        <div className="panel-wide stage1-form">
          <h2>1 · Interconnection</h2>
          <div className="stage1-grid">
            <label className="field">
              <span>{`Target ${LABEL.activePowerMw}`}</span>
              <input type="number" step={0.1} min={0} value={pPocMw} onChange={(e) => setPPocMw(e.target.valueAsNumber)} />
            </label>
            <label className="field">
              <span>{LABEL.powerFactor}</span>
              <input type="number" step={0.01} min={0} max={1} value={pfTarget} onChange={(e) => setPfTarget(e.target.valueAsNumber)} />
            </label>
            <label className="field">
              <span>Interconnection</span>
              <select value={interconnection} onChange={(e) => setInterconnection(e.target.value as 'HV' | 'MV')}>
                <option value="HV">HV</option>
                <option value="MV">MV</option>
              </select>
            </label>
            <label className="field">
              <span>Interconnection voltage (kV)</span>
              <input type="number" step={1} min={0} value={vExportKv} onChange={(e) => setVExportKv(e.target.valueAsNumber)} />
            </label>
            <label className="field">
              <span>Export cable {LABEL.lengthM} (0 = none)</span>
              <input type="number" step={10} min={0} value={exportM} onChange={(e) => setExportM(e.target.valueAsNumber)} />
            </label>
          </div>
          {interconnection === 'HV' && (
            <p className="panel-hint">
              The MV/HV transformer is sized automatically for the plant power — don&rsquo;t add it to the chain
              below.
            </p>
          )}

          <h2>2 · Build the electrical chain (MV busbar → inverter)</h2>
          <div className="stage1-add-element">
            <label className="field">
              <span>Element type</span>
              <select value={draftType} onChange={(e) => setDraftType(e.target.value as Stage1Element['type'])}>
                <option value="Transformer">Transformer</option>
                <option value="Cable section">Cable section</option>
                <option value="Aux load">Aux load</option>
              </select>
            </label>
            {draftType === 'Transformer' && (
              <>
                <label className="field">
                  <span>Transformer</span>
                  <select value={draftComponent} onChange={(e) => setDraftComponent(e.target.value)}>
                    <option value="">— select —</option>
                    {catalogue?.transformers.map((tx) => (
                      <option key={tx.key} value={tx.key}>
                        {tx.display_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Section voltage (kV)</span>
                  <input type="number" step={0.1} min={0} value={draftVKv} onChange={(e) => setDraftVKv(e.target.valueAsNumber)} />
                </label>
                <label className="field">
                  <span>Parallel units</span>
                  <input
                    type="number"
                    step={1}
                    min={1}
                    value={draftNParallel}
                    onChange={(e) => setDraftNParallel(e.target.valueAsNumber)}
                  />
                </label>
              </>
            )}
            {draftType === 'Cable section' && (
              <label className="field">
                <span>Section voltage (kV)</span>
                <input type="number" step={0.1} min={0} value={draftVKv} onChange={(e) => setDraftVKv(e.target.valueAsNumber)} />
              </label>
            )}
            {draftType === 'Aux load' && (
              <>
                <label className="field">
                  <span>{LABEL.activePowerKw}</span>
                  <input type="number" step={1} value={draftPKw} onChange={(e) => setDraftPKw(e.target.valueAsNumber)} />
                </label>
                <label className="field">
                  <span>{LABEL.reactivePowerKvar}</span>
                  <input type="number" step={1} value={draftQKvar} onChange={(e) => setDraftQKvar(e.target.valueAsNumber)} />
                </label>
                <label className="field">
                  <span>Section voltage (kV)</span>
                  <input type="number" step={0.1} min={0} value={draftVKv} onChange={(e) => setDraftVKv(e.target.valueAsNumber)} />
                </label>
              </>
            )}
            <label className="field">
              <span>Label (optional)</span>
              <input type="text" value={draftLabel} onChange={(e) => setDraftLabel(e.target.value)} />
            </label>
            <button type="button" onClick={addElement} disabled={draftType === 'Transformer' && !draftComponent}>
              Add to chain
            </button>
          </div>

          {elements.length === 0 ? (
            <p className="panel-hint">No elements yet — add elements above.</p>
          ) : (
            <>
              <ul className="entity-list stage1-element-list">
                {elements.map((e, i) => (
                  <li key={e.id} className="entity-row">
                    <span className="entity-meta stage1-element-order">{i + 1}</span>
                    <span className="entity-name stage1-element-name">{e.label || e.type}</span>
                    <span className="entity-meta">{detailFor(e, catalogue)}</span>
                    <span className="entity-meta">{e.v_kv} kV</span>
                    <button type="button" onClick={() => moveElement(e.id, -1)} disabled={i === 0} title="Move up">
                      ↑
                    </button>
                    <button type="button" onClick={() => moveElement(e.id, 1)} disabled={i === elements.length - 1} title="Move down">
                      ↓
                    </button>
                    <button type="button" className="danger" onClick={() => removeElement(e.id)}>
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
              <button type="button" onClick={clearElements}>
                Clear chain
              </button>
            </>
          )}

          <h2>3 · Results</h2>
          <button type="button" onClick={solve} disabled={solving || elements.length === 0}>
            {solving ? 'Calculating…' : 'Calculate inverter sizing'}
          </button>
          {error && <p className="error">{error}</p>}

          {result && (
            <div className="stage1-results">
              <div className={`compliance-banner ${result.power_balance_ok ? 'ok' : 'bad'}`}>
                <div className="compliance-verdict">{result.power_balance_ok ? 'Power balance OK' : 'Power balance NOT OK'}</div>
              </div>
              <div className="results-grid stage1-results-grid">
                <div>
                  <span className="label">{`P ${LABEL.activePowerMw}`}</span>
                  <span className="value">{fmt(result.p_inv_kw / 1000, 2)}</span>
                </div>
                <div>
                  <span className="label">{`Q ${LABEL.reactivePowerMvar}`}</span>
                  <span className="value">{fmt(result.q_inv_kvar / 1000, 2)}</span>
                </div>
                <div>
                  <span className="label">{`S ${LABEL.apparentPowerMva}`}</span>
                  <span className="value">{fmt(result.s_inv_kva / 1000, 2)}</span>
                </div>
                <div>
                  <span className="label">{LABEL.powerFactor}</span>
                  <span className="value">{fmt(result.pf_inv, 3)}</span>
                </div>
              </div>

              <h3>Loss breakdown (POC → inverter)</h3>
              <table className="stage1-loss-table">
                <thead>
                  <tr>
                    <th>Element</th>
                    <th>Active loss ΔP (kW)</th>
                    <th>Reactive loss ΔQ (kvar)</th>
                  </tr>
                </thead>
                <tbody>
                  {result.losses.map((l, i) => (
                    <tr key={i}>
                      <td>{l.label}</td>
                      <td>{fmt(l.dp_kw, 2)}</td>
                      <td>{fmt(l.dq_kvar, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
