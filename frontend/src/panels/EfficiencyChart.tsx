import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, PointerEvent } from 'react'
import { downsampleMinMax } from '../efficiency'
import type { EfficiencyRow } from '../types'

// Three measures in three units, so three small charts on one shared time
// axis rather than one chart with several y-scales. Each is a single series
// (the title names it); one crosshair and one readout span all three.

interface Measure {
  key: 'operating_rte_pct' | 'idle_loss_kwh_per_h' | 'pcs_power_pct'
  title: string
  unit: string
  digits: number
  /** Fixed domain, or null to fit the data. */
  domain: [number, number] | null
}

const MEASURES: Measure[] = [
  { key: 'operating_rte_pct', title: 'Operating RTE at the POC (%)', unit: '%', digits: 2, domain: null },
  { key: 'idle_loss_kwh_per_h', title: 'Idle standby loss (kWh per idle hour)', unit: 'kWh/h', digits: 0, domain: null },
  { key: 'pcs_power_pct', title: 'PCS power (% of rated)', unit: '%', digits: 0, domain: [0, 100] },
]

const PANEL_H = 92
const TITLE_H = 18
const GAP = 10
const AXIS_W = 44
const RIGHT = 8
const X_AXIS_H = 18
const FALLBACK_WIDTH = 520

function fitDomain(values: number[]): [number, number] {
  let lo = Infinity
  let hi = -Infinity
  for (const v of values) {
    if (v < lo) lo = v
    if (v > hi) hi = v
  }
  const pad = hi > lo ? (hi - lo) * 0.08 : Math.max(Math.abs(hi) * 0.01, 0.01)
  return [lo - pad, hi + pad]
}

/** Width of the element, tracked as it resizes (jsdom has no layout: fallback). */
function useWidth() {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(FALLBACK_WIDTH)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => {
      const w = Math.floor(entry.contentRect.width)
      if (w > 0) setWidth(w)
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return [ref, width] as const
}

export function EfficiencyChart({ rows }: { rows: EfficiencyRow[] }) {
  const [ref, width] = useWidth()
  const [hover, setHover] = useState<number | null>(null)
  const plotW = Math.max(width - AXIS_W - RIGHT, 50)
  const n = rows.length
  const xOf = (i: number) => AXIS_W + (n > 1 ? (i / (n - 1)) * plotW : plotW / 2)
  const height = MEASURES.length * (TITLE_H + PANEL_H + GAP) + X_AXIS_H

  // Paths are the expensive part at 8,760 rows; recomputed only when the data
  // or the width changes, never on hover.
  const panels = useMemo(() => {
    const columns = Math.max(Math.floor(plotW), 1)
    return MEASURES.map((m, k) => {
      const values = rows.map((r) => r[m.key])
      const [lo, hi] = m.domain ?? fitDomain(values)
      const top = k * (TITLE_H + PANEL_H + GAP) + TITLE_H
      const yOf = (v: number) => top + PANEL_H - ((v - lo) / (hi - lo)) * PANEL_H
      const xs = (i: number) => AXIS_W + (rows.length > 1 ? (i / (rows.length - 1)) * plotW : plotW / 2)
      const points = downsampleMinMax(values, columns)
      const d = points
        .map((p, j) => `${j === 0 ? 'M' : 'L'}${xs(p.i).toFixed(1)},${yOf(p.v).toFixed(1)}`)
        .join('')
      return { m, top, lo, hi, yOf, d }
    })
  }, [rows, plotW])

  if (n === 0) return null

  const indexAt = (clientX: number, rect: DOMRect) => {
    const x = ((clientX - rect.left) / rect.width) * width
    const t = n > 1 ? (x - AXIS_W) / plotW : 0
    return Math.min(n - 1, Math.max(0, Math.round(t * (n - 1))))
  }
  const onPointerMove = (e: PointerEvent<SVGSVGElement>) =>
    setHover(indexAt(e.clientX, e.currentTarget.getBoundingClientRect()))
  const onKeyDown = (e: KeyboardEvent<SVGSVGElement>) => {
    const step = e.shiftKey ? 24 : 1
    if (e.key === 'ArrowRight') setHover((h) => Math.min(n - 1, (h ?? -1) + step))
    else if (e.key === 'ArrowLeft') setHover((h) => Math.max(0, (h ?? n) - step))
    else if (e.key === 'Escape') setHover(null)
    else return
    e.preventDefault()
  }

  const hoverRow = hover === null ? null : rows[hover]
  const hoverX = hover === null ? 0 : xOf(hover)
  const plotBottom = height - X_AXIS_H

  return (
    <div className="efficiency-chart" ref={ref}>
      <svg
        role="img"
        aria-label={`Operating RTE, idle standby loss and PCS power over ${n} timestamps`}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        tabIndex={0}
        onPointerMove={onPointerMove}
        onPointerLeave={() => setHover(null)}
        onKeyDown={onKeyDown}
        onBlur={() => setHover(null)}
      >
        {panels.map(({ m, top, lo, hi, yOf, d }) => (
          <g key={m.key}>
            <text className="efficiency-chart-title" x={AXIS_W} y={top - 5}>
              {m.title}
            </text>
            {[lo, hi].map((v, j) => (
              <g key={j}>
                <line className="efficiency-chart-grid" x1={AXIS_W} x2={AXIS_W + plotW} y1={yOf(v)} y2={yOf(v)} />
                <text className="efficiency-chart-tick" x={AXIS_W - 4} y={yOf(v)} dy={j === 0 ? 0 : 9} textAnchor="end">
                  {v.toFixed(m.digits)}
                </text>
              </g>
            ))}
            <path className="efficiency-chart-line" d={d} />
          </g>
        ))}
        <text className="efficiency-chart-tick" x={AXIS_W} y={height - 4}>
          {rows[0].timestamp}
        </text>
        <text className="efficiency-chart-tick" x={AXIS_W + plotW} y={height - 4} textAnchor="end">
          {rows[n - 1].timestamp}
        </text>
        {hoverRow && (
          <g pointerEvents="none">
            <line className="efficiency-chart-crosshair" x1={hoverX} x2={hoverX} y1={TITLE_H} y2={plotBottom} />
            {panels.map(({ m, yOf }) => (
              <circle key={m.key} className="efficiency-chart-dot" cx={hoverX} cy={yOf(hoverRow[m.key])} r={4} />
            ))}
          </g>
        )}
      </svg>
      {hoverRow && (
        <div
          className="efficiency-chart-tooltip"
          style={hoverX > width / 2 ? { right: width - hoverX + 8 } : { left: hoverX + 8 }}
        >
          <div className="efficiency-chart-tooltip-time">{hoverRow.timestamp}</div>
          {MEASURES.map((m) => (
            <div key={m.key}>
              {m.title.replace(/ \(.*\)$/, '')}: <strong>{hoverRow[m.key].toFixed(m.digits === 0 ? 1 : m.digits)}</strong> {m.unit}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
