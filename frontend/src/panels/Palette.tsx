import { useMemo } from 'react'
import { useCatalogue } from '../hooks/useCatalogue'
import { useStore } from '../store'
import type { DiagramNode, NodeKind, TransformerInfo } from '../types'
import type { PaletteDropPayload } from '../canvas/Editor'

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
}: {
  label: string
  kind: NodeKind
  props: DiagramNode['props']
  onClick?: () => void
  selected?: boolean
}) {
  return (
    <div
      className={`palette-item${selected ? ' selected' : ''}`}
      draggable
      onDragStart={(e) => onDragStart(e, { kind, props })}
      onClick={onClick}
    >
      {label}
    </div>
  )
}

/** Groups the transformer catalogue by brand, preserving first-seen order —
 * with 11 models across 3 brands, one collapsible dropdown per brand reads
 * better than one long flat list or one single "catalogue" dropdown. */
function groupByBrand(transformers: TransformerInfo[]): Array<[string, TransformerInfo[]]> {
  const groups = new Map<string, TransformerInfo[]>()
  for (const tx of transformers) {
    const brand = tx.brand ?? 'Other'
    if (!groups.has(brand)) groups.set(brand, [])
    groups.get(brand)!.push(tx)
  }
  return [...groups.entries()]
}

export function Palette() {
  const catalogue = useCatalogue()
  const nodes = useStore((s) => s.diagram.nodes)
  const selection = useStore((s) => s.selection)
  const setSelection = useStore((s) => s.setSelection)
  const hasPoc = nodes.some((n) => n.kind === 'poc')
  const hasBusbar = nodes.some((n) => n.kind === 'busbar')

  const brandGroups = useMemo(() => (catalogue ? groupByBrand(catalogue.transformers) : []), [catalogue])

  return (
    <aside className="panel palette">
      <h2>Palette</h2>
      <div className="palette-section">
        <h3>Topology</h3>
        {!hasPoc && <Item label="Point of Connection" kind="poc" props={{ p_target_mw: 10, pf: 0.95 }} />}
        {!hasBusbar && <Item label="MV busbar" kind="busbar" props={{}} />}
        <Item label="MV/HV transformer" kind="hv_tx" props={{ mode: 'auto', n_parallel: 1 }} />
        <Item label="Aux load" kind="aux" props={{ p_kw: 50, q_kvar: 10 }} />
      </div>
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
                  label={tx.key}
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
      <div className="palette-section">
        <h3>Stations — custom</h3>
        <Item
          label="Custom station"
          kind="station"
          props={{ mode: 'custom', name: 'Custom station', s_rated_kva: 1000, uk_percent: 6, pk_kw: 8, p0_kw: 1, i0_percent: 0.5 }}
        />
      </div>
    </aside>
  )
}
