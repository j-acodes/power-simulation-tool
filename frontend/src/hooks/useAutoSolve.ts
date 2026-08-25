import { useEffect, useRef } from 'react'
import { solveDiagram } from '../api'
import { useStore } from '../store'
import type { Diagram } from '../types'

const DEBOUNCE_MS = 600

/** A diagram hash that ignores node x/y: dragging a block must never trigger a
 * re-solve, only a real change to structure, props or settings should. */
function hashDiagram(diagram: Diagram): string {
  const nodes = diagram.nodes.map(({ id, kind, props }) => ({ id, kind, props }))
  return JSON.stringify({ settings: diagram.settings, nodes, edges: diagram.edges })
}

/** Debounced auto-solve: POSTs /api/solve 600 ms after the last structural
 * change to the diagram, skipping while solvePaused, and stores the result. */
export function useAutoSolve(): void {
  const diagram = useStore((s) => s.diagram)
  const solvePaused = useStore((s) => s.solvePaused)
  const setSolveResult = useStore((s) => s.setSolveResult)
  const setSolving = useStore((s) => s.setSolving)
  const lastHash = useRef<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const generation = useRef(0)

  useEffect(() => {
    if (solvePaused) return
    const hash = hashDiagram(diagram)
    if (hash === lastHash.current) return
    if (timer.current) clearTimeout(timer.current)

    timer.current = setTimeout(() => {
      lastHash.current = hash
      const gen = ++generation.current
      setSolving(true)
      solveDiagram(diagram)
        .then((res) => {
          if (gen === generation.current) setSolveResult(res.issues, res.results)
        })
        .catch((err: unknown) => {
          if (gen === generation.current) {
            setSolveResult(
              [{ code: 'network_error', message: String(err), node_id: null, edge_id: null }],
              null,
            )
          }
        })
        .finally(() => {
          if (gen === generation.current) setSolving(false)
        })
    }, DEBOUNCE_MS)

    return () => {
      if (timer.current) clearTimeout(timer.current)
    }
  }, [diagram, solvePaused, setSolveResult, setSolving])
}
