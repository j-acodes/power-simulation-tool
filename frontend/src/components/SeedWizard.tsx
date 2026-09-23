import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { seedDiagram } from '../api'
import { useCatalogue } from '../hooks/useCatalogue'
import { LABEL } from '../labels'
import { useStore } from '../store'
import type { Diagram, SeedParams } from '../types'
import { ModalShell, useConfirmDialog } from './Modal'
import { defaultInverterSelection } from '../inverterDefaults'

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
  const technology = useStore((s) => s.designMeta?.technology)
  const isBess = technology === 'bess'
  const isHybrid = technology === 'hybrid'
  // Which section(s) to render: PV shows for pv, hybrid, or a design that
  // hasn't loaded yet (permitsFleetKind's fail-open default); BESS shows for
  // bess or hybrid. A hybrid design shows both, each with its own fields,
  // the shared fields (interconnection, voltages, pf target, export length,
  // aux, feeders-per-busbar) rendered once outside either section.
  const showPv = !isBess
  const showBess = isBess || isHybrid
  const { confirm, dialog: confirmDialog } = useConfirmDialog()

  const [pPocMw, setPPocMw] = useState(REFERENCE.p_poc_mw)
  const [pfTarget, setPfTarget] = useState(REFERENCE.pf_target)
  const [interconnection, setInterconnection] = useState<'HV' | 'MV'>('HV')
  const [vHvKv, setVHvKv] = useState(REFERENCE.v_hv_kv)
  const [exportM, setExportM] = useState(0)
  const [vMvKv, setVMvKv] = useState(0)
  const [stationModel, setStationModel] = useState('')
  const [pvInverter, setPvInverter] = useState('')
  const [inverterCount, setInverterCount] = useState<number | null>(null)
  const [maxLoading, setMaxLoading] = useState(0)
  const [trunkM, setTrunkM] = useState(REFERENCE.trunk_m)
  const [spacingM, setSpacingM] = useState(REFERENCE.spacing_m)
  const [auxPKw, setAuxPKw] = useState(REFERENCE.aux_p_kw)
  const [auxQKvar, setAuxQKvar] = useState(REFERENCE.aux_q_kvar)

  // --- BESS section (ticket 02): duration -> solution -> station cascade ---
  const [pPocBessMw, setPPocBessMw] = useState(REFERENCE.p_poc_mw)
  const [dischargeHours, setDischargeHours] = useState<number | null>(null)
  const [bessSolution, setBessSolution] = useState('')
  const [bessStationModel, setBessStationModel] = useState('')
  const [maxLoadingBess, setMaxLoadingBess] = useState(0)
  const [trunkBessM, setTrunkBessM] = useState(REFERENCE.trunk_m)
  const [spacingBessM, setSpacingBessM] = useState(REFERENCE.spacing_m)

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const eligibleStations = useMemo(
    () => (catalogue?.transformers ?? []).filter(
      (station) => Object.keys(station.paired_inverters).length > 0,
    ),
    [catalogue],
  )
  const effectiveStationModel = stationModel || eligibleStations[0]?.key || ''
  const selectedStation = eligibleStations.find((station) => station.key === effectiveStationModel)
  const pairings = selectedStation?.paired_inverters ?? {}
  const effectivePvInverter = pvInverter in pairings
    ? pvInverter
    : Object.keys(pairings)[0] ?? ''
  const inverterOptions = (catalogue?.pv_inverters ?? []).filter(
    (inverter) => inverter.key in pairings,
  )
  const selectedPairing = pairings[effectivePvInverter]
  const effectiveInverterCount = inverterCount ?? selectedPairing?.maximum_count ?? 0

  // Change PRODUCT, not duration (see powertool.graph.supported_durations):
  // the duration select offers every duration on offer across the BESS
  // catalogue; picking one narrows the solution select to solutions that
  // sell it, and picking a solution narrows the station select to stations
  // paired with it.
  const durations = useMemo(
    () => [...new Set((catalogue?.bess_solutions ?? []).map((s) => s.duration_h))].sort((a, b) => a - b),
    [catalogue],
  )
  const effectiveDischargeHours = dischargeHours ?? durations[0] ?? null
  const solutionsForDuration = (catalogue?.bess_solutions ?? []).filter(
    (s) => s.duration_h === effectiveDischargeHours,
  )
  const effectiveBessSolution = solutionsForDuration.some((s) => s.key === bessSolution)
    ? bessSolution
    : solutionsForDuration[0]?.key ?? ''
  const eligibleBessStations = (catalogue?.bess_transformers ?? []).filter(
    (station) => effectiveBessSolution in station.paired_solutions,
  )
  const effectiveBessStationModel = eligibleBessStations.some((s) => s.key === bessStationModel)
    ? bessStationModel
    : eligibleBessStations[0]?.key ?? ''

  // Fill catalogue-derived defaults once they arrive, without clobbering
  // anything the user has already changed.
  useEffect(() => {
    if (!catalogue) return
    // Catalogue data arrives asynchronously; these are one-time form defaults,
    // not state derived from state. User-entered non-zero values remain intact.
    // oxlint-disable-next-line react/set-state-in-effect
    setVMvKv((v) => v || catalogue.defaults.tiers.mv_kv)
    setMaxLoading((v) => v || catalogue.defaults.rules.max_utilization)
    // oxlint-disable-next-line react/set-state-in-effect
    setMaxLoadingBess((v) => v || catalogue.defaults.rules.max_utilization)
  }, [catalogue])

  const pvReady = Boolean(effectiveStationModel) && Boolean(effectivePvInverter) && Boolean(selectedPairing)
  const bessReady = Boolean(effectiveBessStationModel) && Boolean(effectiveBessSolution) && effectiveDischargeHours != null
  const canSubmit = isHybrid ? pvReady && bessReady : isBess ? bessReady : pvReady

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const shared = {
        pf_target: pfTarget,
        interconnection,
        v_hv_kv: interconnection === 'HV' ? vHvKv : null,
        export_m: exportM,
        v_mv_kv: vMvKv,
        aux_p_kw: auxPKw,
        aux_q_kvar: auxQKvar,
      }
      const pvBlock = {
        p_poc_mw: pPocMw,
        station_model: effectiveStationModel,
        pv_inverter: effectivePvInverter,
        inverter_count: effectiveInverterCount,
        max_loading: maxLoading,
        trunk_m: trunkM,
        spacing_m: spacingM,
      }
      const bessBlock = {
        p_poc_bess_mw: pPocBessMw,
        discharge_hours: effectiveDischargeHours ?? 0,
        bess_solution: effectiveBessSolution,
        bess_station_model: effectiveBessStationModel,
        max_loading_bess: maxLoadingBess,
        trunk_bess_m: trunkBessM,
        spacing_bess_m: spacingBessM,
      }
      const params: SeedParams = isHybrid
        ? { technology: 'hybrid', ...shared, ...pvBlock, ...bessBlock }
        : isBess
          ? { technology: 'bess', ...shared, ...bessBlock }
          : { technology: 'pv', ...shared, ...pvBlock }
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
      <ModalShell onEscape={onClose} size="wide">
        <form className="seed-wizard" onSubmit={submit}>
          <h2>Seed from POC target</h2>
          <p className="panel-hint">
            Propose a starting plant for a POC target — you rearrange it on the canvas afterwards.
          </p>

          <div className="seed-wizard-grid">
            {showPv && (
              <label className="field">
                <span>{`Target ${isHybrid ? 'PV ' : ''}${LABEL.activePowerMw}`}</span>
                <input type="number" step={0.1} min={0} value={pPocMw} onChange={(e) => setPPocMw(e.target.valueAsNumber)} required />
              </label>
            )}
            {showBess && (
              <label className="field">
                <span>{`Target BESS ${LABEL.activePowerMw}`}</span>
                <input type="number" step={0.1} min={0} value={pPocBessMw} onChange={(e) => setPPocBessMw(e.target.valueAsNumber)} required />
              </label>
            )}
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
            {showPv && (
              <>
                <label className="field">
                  <span>PV Transformer Station</span>
                  <select
                    value={effectiveStationModel}
                    onChange={(e) => {
                      const key = e.target.value
                      const station = eligibleStations.find((candidate) => candidate.key === key)
                      const deployed = defaultInverterSelection(station)
                      setStationModel(key)
                      setPvInverter(deployed.pv_inverter)
                      setInverterCount(deployed.inverter_count ?? null)
                    }}
                    required
                  >
                    <option value="">— select —</option>
                    {eligibleStations.map((tx) => (
                      <option key={tx.key} value={tx.key}>
                        {tx.display_name}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>PV inverter</span>
                  <select
                    value={effectivePvInverter}
                    onChange={(e) => {
                      const key = e.target.value
                      setPvInverter(key)
                      setInverterCount(pairings[key]?.maximum_count ?? null)
                    }}
                    required
                  >
                    <option value="">— select —</option>
                    {inverterOptions.map((inverter) => (
                      <option key={inverter.key} value={inverter.key}>{inverter.display_name}</option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>Inverters per station</span>
                  <input
                    type="number"
                    step={1}
                    min={1}
                    max={selectedPairing?.maximum_count}
                    value={effectiveInverterCount || ''}
                    onChange={(e) => {
                      const value = e.target.valueAsNumber
                      setInverterCount(selectedPairing && Number.isFinite(value)
                        ? Math.min(selectedPairing.maximum_count, Math.max(1, Math.round(value)))
                        : selectedPairing?.maximum_count ?? null)
                    }}
                    required
                  />
                </label>

                <label className="field">
                  <span>{isHybrid ? 'PV max loading' : 'Max loading'}</span>
                  <input type="number" step={0.01} min={0} max={1} value={maxLoading} onChange={(e) => setMaxLoading(e.target.valueAsNumber)} required />
                </label>
                <label className="field">
                  <span>{isHybrid ? 'PV trunk' : 'Trunk'} {LABEL.lengthM}</span>
                  <input type="number" step={10} min={0} value={trunkM} onChange={(e) => setTrunkM(e.target.valueAsNumber)} required />
                </label>
                <label className="field">
                  <span>{isHybrid ? 'PV spacing' : 'Spacing'} {LABEL.lengthM}</span>
                  <input type="number" step={10} min={0} value={spacingM} onChange={(e) => setSpacingM(e.target.valueAsNumber)} required />
                </label>
              </>
            )}

            {showBess && (
              <>
                <label className="field">
                  <span>Discharge duration</span>
                  <select
                    value={effectiveDischargeHours ?? ''}
                    onChange={(e) => {
                      setDischargeHours(Number(e.target.value))
                      setBessSolution('')
                      setBessStationModel('')
                    }}
                    required
                  >
                    <option value="">— select —</option>
                    {durations.map((hours) => (
                      <option key={hours} value={hours}>{`${hours} h`}</option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>BESS solution</span>
                  <select
                    value={effectiveBessSolution}
                    onChange={(e) => {
                      setBessSolution(e.target.value)
                      setBessStationModel('')
                    }}
                    required
                  >
                    <option value="">— select —</option>
                    {solutionsForDuration.map((solution) => (
                      <option key={solution.key} value={solution.key}>{solution.display_name}</option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>BESS station</span>
                  <select
                    value={effectiveBessStationModel}
                    onChange={(e) => setBessStationModel(e.target.value)}
                    required
                  >
                    <option value="">— select —</option>
                    {eligibleBessStations.map((station) => (
                      <option key={station.key} value={station.key}>{station.display_name}</option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>{isHybrid ? 'BESS max loading' : 'Max loading'}</span>
                  <input type="number" step={0.01} min={0} max={1} value={maxLoadingBess} onChange={(e) => setMaxLoadingBess(e.target.valueAsNumber)} required />
                </label>
                <label className="field">
                  <span>{isHybrid ? 'BESS trunk' : 'Trunk'} {LABEL.lengthM}</span>
                  <input type="number" step={10} min={0} value={trunkBessM} onChange={(e) => setTrunkBessM(e.target.valueAsNumber)} required />
                </label>
                <label className="field">
                  <span>{isHybrid ? 'BESS spacing' : 'Spacing'} {LABEL.lengthM}</span>
                  <input type="number" step={10} min={0} value={spacingBessM} onChange={(e) => setSpacingBessM(e.target.valueAsNumber)} required />
                </label>
              </>
            )}

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
            <button type="submit" disabled={submitting || !canSubmit}>
              {submitting ? 'Seeding…' : 'Seed diagram'}
            </button>
          </div>
        </form>
      </ModalShell>
      {confirmDialog}
    </>
  )
}
