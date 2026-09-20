import { useEffect } from 'react'
import { missingInverterSelections } from '../inverterDefaults'
import { useStore } from '../store'
import { useCatalogue } from './useCatalogue'

/** Keeps every catalogue PV station on the canvas carrying its paired
 * inverter, whatever route the diagram arrived by — dropped from the palette,
 * seeded, loaded from the example plant, or read back from a saved design.
 * One place rather than one per loader; see `missingInverterSelections`. */
export function useFillInverters() {
  const catalogue = useCatalogue()
  const diagram = useStore((s) => s.diagram)
  const updateNodeProps = useStore((s) => s.updateNodeProps)
  useEffect(() => {
    if (!catalogue) return
    for (const { id, selection } of missingInverterSelections(diagram, catalogue.transformers)) {
      updateNodeProps(id, selection)
    }
  }, [catalogue, diagram, updateNodeProps])
}
