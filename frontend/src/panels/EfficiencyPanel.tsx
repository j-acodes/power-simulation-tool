import { useMemo, useState } from 'react'
import type { ChangeEvent } from 'react'
import { runEfficiency } from '../api'
import { parseAmbientCsv, summarise, toCliCsv } from '../efficiency'
import type { ParsedAmbient } from '../efficiency'
import { useStore } from '../store'
import type { EfficiencyResponse } from '../types'
import { EfficiencyChart } from './EfficiencyChart'

const pct = (v: number, digits: number) => `${v.toFixed(digits)} %`

/** Efficiency run of the design on the canvas (ticket 17): upload a CSV of
 * `timestamp, ambient °C`, run it through the engine (POST /api/efficiency),
 * and see operating round-trip efficiency at the point of connection, idle
 * standby loss and PCS derating per timestamp. No physics here. */
export function EfficiencyPanel() {
  const diagram = useStore((s) => s.diagram)
  const designName = useStore((s) => s.designMeta?.name)
  const [parsed, setParsed] = useState<ParsedAmbient | null>(null)
  const [cyclesPerDay, setCyclesPerDay] = useState('1')
  const [cellRte, setCellRte] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<EfficiencyResponse | null>(null)
  const summary = useMemo(() => (result ? summarise(result.rows) : null), [result])

  const onFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    setResult(null)
    setError(null)
    setParsed(file ? parseAmbientCsv(await file.text()) : null)
  }

  const cycles = Number(cyclesPerDay)
  const cyclesValid = cyclesPerDay.trim() !== '' && Number.isFinite(cycles) && cycles > 0
  const cellRteValue = cellRte.trim() === '' ? null : Number(cellRte)
  const cellRteValid = cellRteValue === null || Number.isFinite(cellRteValue)
  const canRun =
    parsed !== null && parsed.errors.length === 0 && cyclesValid && cellRteValid && !running

  const onRun = async () => {
    if (!parsed || !canRun) return
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      setResult(
        await runEfficiency({
          diagram,
          rows: parsed.rows,
          cycles_per_day: cycles,
          cell_rte_pct: cellRteValue,
        }),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunning(false)
    }
  }

  const onDownload = () => {
    if (!result) return
    const blob = new Blob([toCliCsv(result.rows)], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${designName ?? 'design'}-efficiency-run.csv`
    link.click()
    // Revoking synchronously after click can cancel the download.
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return (
    <div className="efficiency-panel">
      <h3>Efficiency run</h3>
      <p className="panel-hint">
        Runs the BESS fleet of the design on the canvas against a CSV of timestamp and
        ambient °C (one header row).
      </p>
      <label className="field">
        <span>Ambient CSV</span>
        <input type="file" accept=".csv,text/csv" onChange={onFile} />
      </label>
      {parsed && parsed.errors.length === 0 && (
        <p className="panel-hint">
          {parsed.rows.length} {parsed.rows.length === 1 ? 'timestamp' : 'timestamps'} read.
        </p>
      )}
      {parsed && parsed.errors.length > 0 && (
        <ul className="efficiency-messages error">
          {parsed.errors.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      )}
      <label className="field inline">
        <span>Cycles per day</span>
        <input
          type="number"
          min={0}
          step={0.1}
          value={cyclesPerDay}
          onChange={(e) => setCyclesPerDay(e.target.value)}
        />
      </label>
      <label className="field inline">
        <span>Cell round-trip efficiency (%)</span>
        <input
          type="number"
          step={0.1}
          placeholder="catalogue"
          value={cellRte}
          onChange={(e) => setCellRte(e.target.value)}
        />
      </label>
      <button type="button" className="btn-primary" disabled={!canRun} onClick={onRun}>
        {running ? 'Running…' : 'Run efficiency run'}
      </button>

      {error && (
        <p className="error inline efficiency-error" role="alert">
          {error}
        </p>
      )}

      {result && summary && (
        <>
          <h3>Summary</h3>
          <table className="efficiency-summary" aria-label="Summary">
            <tbody>
              <tr>
                <th scope="row">Minimum operating RTE</th>
                <td>{pct(summary.minRtePct, 2)}</td>
              </tr>
              <tr>
                <th scope="row">Average operating RTE</th>
                <td>{pct(summary.avgRtePct, 2)}</td>
              </tr>
              <tr>
                <th scope="row">Maximum operating RTE</th>
                <td>{pct(summary.maxRtePct, 2)}</td>
              </tr>
              <tr>
                <th scope="row">Average idle standby loss</th>
                <td>{summary.avgIdleLossKwhPerH.toFixed(0)} kWh per idle hour</td>
              </tr>
              <tr>
                <th scope="row">Timestamps with PCS derating</th>
                <td>
                  {summary.deratedCount} of {summary.count}
                </td>
              </tr>
            </tbody>
          </table>
          {result.warnings.length > 0 && (
            <>
              <h3>Warnings</h3>
              <ul className="efficiency-messages">
                {result.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </>
          )}
          <EfficiencyChart rows={result.rows} />
          <button type="button" onClick={onDownload}>
            Download CSV
          </button>
        </>
      )}
    </div>
  )
}
