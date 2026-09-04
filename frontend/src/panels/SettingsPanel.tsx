import { useStore } from '../store'
import { useCatalogue } from '../hooks/useCatalogue'
import { supportedDurations } from '../bess'
import { permitsFleetKind } from '../technology'

export function SettingsPanel() {
  const diagram = useStore((s) => s.diagram)
  const catalogue = useCatalogue()
  const settings = useStore((s) => s.diagram.settings)
  const solvePaused = useStore((s) => s.solvePaused)
  const updateSettings = useStore((s) => s.updateSettings)
  const setSolvePaused = useStore((s) => s.setSolvePaused)
  const technology = useStore((s) => s.designMeta?.technology)
  const { tiers, rules } = settings
  // Only offered once a BESS station is drawn, and only over the durations the
  // selected solutions actually tabulate — the container count is read from the
  // supplier's table, never interpolated, so a duration nobody sells has no
  // answer. Rendering it as a select is what makes that invalid state
  // unreachable rather than merely rejected.
  const durations = supportedDurations(diagram, catalogue?.bess_solutions ?? [])

  return (
    <div className="settings-panel">
      <h3>Tier voltages</h3>
      <label className="field inline">
        <span>LV (kV)</span>
        <input
          type="number"
          step={0.01}
          value={tiers.lv_kv}
          onChange={(e) => updateSettings({ tiers: { ...tiers, lv_kv: e.target.valueAsNumber } })}
        />
      </label>
      <label className="field inline">
        <span>MV (kV)</span>
        <input
          type="number"
          step={0.1}
          value={tiers.mv_kv}
          onChange={(e) => updateSettings({ tiers: { ...tiers, mv_kv: e.target.valueAsNumber } })}
        />
      </label>
      <label className="field inline">
        <span>
          <input
            type="checkbox"
            checked={tiers.hv_kv !== null}
            onChange={(e) => updateSettings({ tiers: { ...tiers, hv_kv: e.target.checked ? 132.0 : null } })}
          />
          {' HV interconnection'}
        </span>
      </label>
      {tiers.hv_kv !== null && (
        <label className="field inline">
          <span>HV (kV)</span>
          <input
            type="number"
            step={1}
            value={tiers.hv_kv}
            onChange={(e) => updateSettings({ tiers: { ...tiers, hv_kv: e.target.valueAsNumber } })}
          />
        </label>
      )}

      <h3>Rules</h3>
      <label className="field inline">
        <span>Max utilization</span>
        <input
          type="number"
          step={0.01}
          value={rules.max_utilization}
          onChange={(e) => updateSettings({ rules: { ...rules, max_utilization: e.target.valueAsNumber } })}
        />
      </label>
      <label className="field inline">
        <span>Collection loss budget (%)</span>
        <input
          type="number"
          step={0.01}
          value={rules.collection_loss_pct}
          onChange={(e) => updateSettings({ rules: { ...rules, collection_loss_pct: e.target.valueAsNumber } })}
        />
      </label>
      <label className="field inline">
        <span>Export loss budget (%/km)</span>
        <input
          type="number"
          step={0.01}
          value={rules.export_loss_pct_per_km}
          onChange={(e) => updateSettings({ rules: { ...rules, export_loss_pct_per_km: e.target.valueAsNumber } })}
        />
      </label>
      <label className="field inline">
        <span>Max circuit current (A)</span>
        <input
          type="number"
          step={1}
          value={rules.max_circuit_current_a}
          onChange={(e) => updateSettings({ rules: { ...rules, max_circuit_current_a: e.target.valueAsNumber } })}
        />
      </label>
      <label className="field inline">
        <span>Max fleet loading</span>
        <input
          type="number"
          step={0.05}
          value={rules.max_loading ?? 1.0}
          onChange={(e) => updateSettings({ rules: { ...rules, max_loading: e.target.valueAsNumber } })}
        />
      </label>
      {/* Per-fleet overrides are opt-in: an empty box means "use the plant-wide
          figure above", which is what every design drawn before hybrid support
          means by leaving it alone. */}
      {(['pv', 'bess'] as const).filter((kind) => permitsFleetKind(technology, kind)).map((kind) => {
        const key = `max_loading_${kind}` as const
        return (
          <label className="field inline" key={kind}>
            <span>{`Max loading — ${kind === 'pv' ? 'PV' : 'BESS'}`}</span>
            <input
              type="number"
              step={0.05}
              placeholder="plant-wide"
              value={rules[key] ?? ''}
              onChange={(e) =>
                updateSettings({
                  rules: { ...rules, [key]: e.target.value === '' ? undefined : e.target.valueAsNumber },
                })
              }
            />
          </label>
        )
      })}

      {durations.length > 0 && (
        <>
          <h3>BESS</h3>
          <label className="field inline">
            <span>Discharge duration (h)</span>
            <select
              value={rules.discharge_hours ?? ''}
              onChange={(e) =>
                updateSettings({
                  rules: {
                    ...rules,
                    discharge_hours: e.target.value === '' ? undefined : Number(e.target.value),
                  },
                })
              }
            >
              <option value="">— not set —</option>
              {durations.map((hours) => (
                <option key={hours} value={hours}>{`${hours} h`}</option>
              ))}
            </select>
          </label>
          {rules.discharge_hours === undefined && (
            <p className="panel-hint">
              Without a duration the delivered-energy check has nothing to judge against.
            </p>
          )}
        </>
      )}

      <h3>Solve</h3>
      <label className="field inline">
        <span>
          <input type="checkbox" checked={solvePaused} onChange={(e) => setSolvePaused(e.target.checked)} />
          {' Pause auto-solve'}
        </span>
      </label>
    </div>
  )
}
