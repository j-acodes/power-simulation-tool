import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { seedDiagram } from '../api'
import { useCatalogue } from '../hooks/useCatalogue'
import { LABEL } from '../labels'
import { useStore } from '../store'
import type { Diagram, SeedParams } from '../types'
import { ModalShell, useConfirmDialog } from './Modal'

// 45 MW / 0.95 pf HV reference plant (same numbers as example.ts) — sensible
// starting point for fields the catalogue doesn't have an opinion on.
const REFERENCE = {
  p_poc_mw: 45.0,
  pf_target: 0.95,
  v_hv_kv: 132.0,
  trunk_m: 800.0,
  spacing_m: 350.0,
  aux_p_kw: 120.0,
  aux_q_kvar: 40.0,
}

interface SeedWizardProps {
  onClose: () => void
}

/** "Seed from POC target…" modal: collects SeedRequest params, POSTs
 * /api/seed, and replaces the canvas diagram with the proposed plant
 * (confirming first if the canvas isn't empty). The auto-solve hook picks up
 * the new diagram automatically once loaded. */
export function SeedWizard({ onClose }: SeedWizardProps) {
  const catalogue = useCatalogue()
  const diagram = useStore((s) => s.diagram)
  const loadDiagram = useStore((s) => s.loadDiagram)
  const { confirm, dialog: confirmDialog } = useConfirmDialog()

  const [pPocMw, setPPocMw] = useState(REFERENCE.p_poc_mw)
  const [pfTarget, setPfTarget] = useState(REFERENCE.pf_target)
  const [interconnection, setInterconnection] = useState<'HV' | 'MV'>('HV')
  const [vHvKv, setVHvKv] = useState(REFERENCE.v_hv_kv)
  const [exportM, setExportM] = useState(0)
  const [vMvKv, setVMvKv] = useState(0)
  const [stationModel, setStationModel] = useState('')
  const [maxLoading, setMaxLoading] = useState(0)
  const [trunkM, setTrunkM] = useState(REFERENCE.trunk_m)
  const [spacingM, setSpacingM] = useState(REFERENCE.spacing_m)
  const [maxCircuitCurrentA, setMaxCircuitCurrentA] = useState(0)
  const [auxPKw, setAuxPKw] = useState(REFERENCE.aux_p_kw)
  const [auxQKvar, setAuxQKvar] = useState(REFERENCE.aux_q_kvar)

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fill catalogue-derived defaults once they arrive, without clobbering
  // anything the user has already changed.
  useEffect(() => {
    if (!catalogue) return
    setVMvKv((v) => v || catalogue.defaults.tiers.mv_kv)
    setMaxLoading((v) => v || catalogue.defaults.rules.max_utilization)
    setMaxCircuitCurrentA((v) => v || catalogue.defaults.rules.max_circuit_current_a)
    setStationModel((k) => k || catalogue.transformers[0]?.key || '')
  }, [catalogue])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const params: SeedParams = {
        p_poc_mw: pPocMw,
        pf_target: pfTarget,
        interconnection,
        v_hv_kv: interconnection === 'HV' ? vHvKv : null,
        export_m: exportM,
        v_mv_kv: vMvKv,
        station_model: stationModel,
        max_loading: maxLoading,
        trunk_m: trunkM,
        spacing_m: spacingM,
        max_circuit_current_a: maxCircuitCurrentA,
        aux_p_kw: auxPKw,
        aux_q_kvar: auxQKvar,
      }
      const proposed = (await seedDiagram(params)) as Diagram
      const isEmpty = diagram.nodes.length === 0
      const proceed =
        isEmpty ||
        (await confirm({
          title: 'Replace diagram?',
          message: 'Replace the current drawing?',
          confirmLabel: 'Replace',
        }))
      if (proceed) {
        loadDiagram(proposed)
        onClose()
      }
    } catch (err) {
      setError(String(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <ModalShell onEscape={onClose} wide>
        <form className="seed-wizard" onSubmit={submit}>
          <h2>Seed from POC target</h2>
          <p className="panel-hint">
            Propose a starting plant for a POC target — you rearrange it on the canvas afterwards.
          </p>

          <div className="seed-wizard-grid">
            <label className="field">
              <span>{`Target ${LABEL.activePowerMw}`}</span>
              <input type="number" step={0.1} min={0} value={pPocMw} onChange={(e) => setPPocMw(e.target.valueAsNumber)} required />
            </label>
            <label className="field">
              <span>{LABEL.powerFactor}</span>
              <input type="number" step={0.01} min={0} max={1} value={pfTarget} onChange={(e) => setPfTarget(e.target.valueAsNumber)} required />
            </label>

            <label className="field">
              <span>Interconnection</span>
              <select value={interconnection} onChange={(e) => setInterconnection(e.target.value as 'HV' | 'MV')}>
                <option value="HV">HV</option>
                <option value="MV">MV</option>
              </select>
            </label>
            {interconnection === 'HV' && (
              <label className="field">
                <span>{LABEL.hvKv}</span>
                <input type="number" step={1} min={0} value={vHvKv} onChange={(e) => setVHvKv(e.target.valueAsNumber)} required />
              </label>
            )}
            <label className="field">
              <span>Export cable {LABEL.lengthM}</span>
              <input type="number" step={10} min={0} value={exportM} onChange={(e) => setExportM(e.target.valueAsNumber)} />
            </label>

            <label className="field">
              <span>{LABEL.mvKv}</span>
              <input type="number" step={0.1} min={0} value={vMvKv} onChange={(e) => setVMvKv(e.target.valueAsNumber)} required />
            </label>
            <label className="field">
              <span>Station model</span>
              <select value={stationModel} onChange={(e) => setStationModel(e.target.value)} required>
                <option value="">— select —</option>
                {catalogue?.transformers.map((tx) => (
                  <option key={tx.key} value={tx.key}>
                    {tx.display_name}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Max loading</span>
              <input type="number" step={0.01} min={0} max={1} value={maxLoading} onChange={(e) => setMaxLoading(e.target.valueAsNumber)} required />
            </label>
            <label className="field">
              <span>Max circuit {LABEL.currentA}</span>
              <input
                type="number"
                step={1}
                min={0}
                value={maxCircuitCurrentA}
                onChange={(e) => setMaxCircuitCurrentA(e.target.valueAsNumber)}
                required
              />
            </label>

            <label className="field">
              <span>Trunk {LABEL.lengthM}</span>
              <input type="number" step={10} min={0} value={trunkM} onChange={(e) => setTrunkM(e.target.valueAsNumber)} required />
            </label>
            <label className="field">
              <span>Spacing {LABEL.lengthM}</span>
              <input type="number" step={10} min={0} value={spacingM} onChange={(e) => setSpacingM(e.target.valueAsNumber)} required />
            </label>

            <label className="field">
              <span>Aux {LABEL.activePowerKw} (optional)</span>
              <input type="number" step={1} value={auxPKw} onChange={(e) => setAuxPKw(e.target.valueAsNumber)} />
            </label>
            <label className="field">
              <span>Aux {LABEL.reactivePowerKvar} (optional)</span>
              <input type="number" step={1} value={auxQKvar} onChange={(e) => setAuxQKvar(e.target.valueAsNumber)} />
            </label>
          </div>

          {error && <p className="error inline">{error}</p>}
          <div className="modal-actions">
            <button type="button" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" disabled={submitting || !stationModel}>
              {submitting ? 'Seeding…' : 'Seed diagram'}
            </button>
          </div>
        </form>
      </ModalShell>
      {confirmDialog}
    </>
  )
}
