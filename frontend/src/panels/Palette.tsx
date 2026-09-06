import { useMemo } from 'react'
import { CollapsiblePanel } from './CollapsiblePanel'
import { useCatalogue } from '../hooks/useCatalogue'
import { useStore } from '../store'
import type { DiagramNode, NodeKind } from '../types'
import { takenBusbarSlots } from '../canvas/connect'
import type { PaletteDropPayload } from '../canvas/Editor'
import { permitsFleetKind } from '../technology'
import { groupByBrand } from '../catalogueGrouping'

const BESS_CUSTOM_PROPS = {
  mode: 'custom',
  fleet_kind: 'bess',
  name: 'Custom BESS station',
  s_rated_kva: 2750,
  uk_percent: 8,
  pk_kw: 27.5,
  p0_kw: 2.75,
  i0_percent: 0,
}

function onDragStart(event: React.DragEvent, payload: PaletteDropPayload) {
  event.dataTransfer.setData('application/reactflow', JSON.stringify(payload))
  event.dataTransfer.effectAllowed = 'move'
}

function Item({
  label,
  kind,
  props,
  onClick,
  selected,
  draggable = true,
}: {
  label: string
  kind?: NodeKind
  props?: DiagramNode['props']
  onClick?: () => void
  selected?: boolean
  /** A BESS solution is selectable but never draggable (ticket 06): dragging
   *  one onto the canvas would have to invent a station, and a solution is
   *  chosen for a station that already exists. */
  draggable?: boolean
}) {
  return (
    <div
      className={`palette-item${selected ? ' selected' : ''}`}
      draggable={draggable}
      onDragStart={draggable && kind && props ? (e) => onDragStart(e, { kind, props }) : undefined}
      onClick={onClick}
    >
      {label}
    </div>
  )
}

export function Palette() {
  const catalogue = useCatalogue()
  const diagram = useStore((s) => s.diagram)
  const selection = useStore((s) => s.selection)
  const setSelection = useStore((s) => s.setSelection)
  const technology = useStore((s) => s.designMeta?.technology)
  const nodes = diagram.nodes
  const hasPoc = nodes.some((n) => n.kind === 'poc')
  // One busbar per fleet kind, read the way the server reads it: an existing
  // busbar counts against the fleet its stations put it in, and an undecided
  // one counts as PV — see busbarSlot. Offering a kind the server would reject
  // is the bug this ticket exists to close.
  const taken = takenBusbarSlots(diagram)
  const showsPv = permitsFleetKind(technology, 'pv')
  const showsBess = permitsFleetKind(technology, 'bess')

  const brandGroups = useMemo(() => (catalogue ? groupByBrand(catalogue.transformers) : []), [catalogue])
  const bessBrandGroups = useMemo(
    () => (catalogue ? groupByBrand(catalogue.bess_transformers) : []),
    [catalogue],
  )

  return (
    <CollapsiblePanel title="Palette" side="left" className="palette">
      <div className="palette-section">
        <h3>Topology</h3>
        {!hasPoc && <Item label="Point of Connection" kind="poc" props={{ p_target_mw: 10, pf: 0.95 }} />}
        {showsPv && !taken.has('pv') && <Item label="MV busbar — PV" kind="busbar" props={{ fleet_kind: 'pv' }} />}
        {showsBess && !taken.has('bess') && <Item label="MV busbar — BESS" kind="busbar" props={{ fleet_kind: 'bess' }} />}
        <Item label="MV/HV transformer" kind="hv_tx" props={{ mode: 'auto', n_parallel: 1 }} />
        <Item label="Aux load" kind="aux" props={{ p_kw: 50, q_kvar: 10 }} />
      </div>
      {showsPv && (
        <div className="palette-section">
          <details className="palette-group" open>
            <summary>Stations — catalogue</summary>
            {!catalogue && <p className="palette-hint">Loading catalogue…</p>}
            {brandGroups.map(([brand, transformers]) => (
              <details key={brand} className="palette-group" open>
                <summary>{brand}</summary>
                {transformers.map((tx) => (
                  <Item
                    key={tx.key}
                    label={tx.display_name}
                    kind="station"
                    props={{ mode: 'catalogue', model: tx.key }}
                    selected={selection?.type === 'palette' && selection.key === tx.key}
                    onClick={() => setSelection({ type: 'palette', key: tx.key })}
                  />
                ))}
              </details>
            ))}
          </details>
        </div>
      )}
      {showsPv && (
        <div className="palette-section">
          <h3>Stations — custom</h3>
          <Item
            label="Custom station"
            kind="station"
            props={{ mode: 'custom', name: 'Custom station', s_rated_kva: 1000, uk_percent: 6, pk_kw: 8, p0_kw: 1, i0_percent: 0.5 }}
          />
        </div>
      )}
      {showsBess && (
        <div className="palette-section">
          <details className="palette-group" open>
            <summary>BESS stations — catalogue</summary>
            {!catalogue && <p className="palette-hint">Loading catalogue…</p>}
            {bessBrandGroups.map(([brand, transformers]) => (
              <details key={brand} className="palette-group" open>
                <summary>{brand}</summary>
                {transformers.map((tx) => (
                  <Item
                    key={tx.key}
                    label={tx.display_name}
                    kind="station"
                    props={{ mode: 'catalogue', model: tx.key, fleet_kind: 'bess' }}
                    selected={selection?.type === 'palette' && selection.key === tx.key}
                    onClick={() => setSelection({ type: 'palette', key: tx.key })}
                  />
                ))}
              </details>
            ))}
          </details>
        </div>
      )}
      {showsBess && (
        <div className="palette-section">
          <h3>BESS stations — custom</h3>
          <Item label="Custom BESS station" kind="station" props={BESS_CUSTOM_PROPS} />
        </div>
      )}
      {showsBess && (
        <div className="palette-section">
          <details className="palette-group" open>
            <summary>BESS solutions — catalogue</summary>
            {!catalogue && <p className="palette-hint">Loading catalogue…</p>}
            {catalogue?.bess_solutions.map((sol) => (
              <Item
                key={sol.key}
                label={sol.display_name}
                draggable={false}
                selected={selection?.type === 'palette' && selection.key === sol.key}
                onClick={() => setSelection({ type: 'palette', key: sol.key })}
              />
            ))}
          </details>
        </div>
      )}
    </CollapsiblePanel>
  )
}
