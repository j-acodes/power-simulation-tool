import { useStore } from '../store'

export function SettingsPanel() {
  const settings = useStore((s) => s.diagram.settings)
  const solvePaused = useStore((s) => s.solvePaused)
  const updateSettings = useStore((s) => s.updateSettings)
  const setSolvePaused = useStore((s) => s.setSolvePaused)
  const { tiers, rules } = settings

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
