import { create } from 'zustand'
import type {
  Diagram,
  DiagramEdge,
  DiagramNode,
  DiagramSettings,
  Issue,
  SolveResults,
} from './types'

export type Selection =
  | { type: 'node' | 'edge'; id: string }
  | { type: 'palette'; key: string }
  | null

export interface DesignMeta {
  id: number
  name: string
  version: number
}

const DISPLAY_NAME_KEY = 'powertool.displayName'

function readDisplayName(): string | null {
  try {
    return localStorage.getItem(DISPLAY_NAME_KEY)
  } catch {
    return null
  }
}

export const EMPTY_DIAGRAM: Diagram = {
  schema_version: 1,
  settings: {
    tiers: { lv_kv: 0.8, mv_kv: 20.0, hv_kv: null },
    rules: {
      max_utilization: 0.8,
      collection_loss_pct: 1.3,
      export_loss_pct_per_km: 0.1,
      max_circuit_current_a: 400.0,
    },
  },
  nodes: [],
  edges: [],
}

interface State {
  diagram: Diagram
  results: SolveResults | null
  issues: Issue[]
  solvePaused: boolean
  solving: boolean
  selection: Selection

  /** Set only while editing a persisted design (null on the scratch page). */
  designMeta: DesignMeta | null
  /** The exact diagram object last loaded from / saved to the server — dirty
   * is `diagram !== savedDiagramRef` (every mutation replaces the object). */
  savedDiagramRef: Diagram | null

  displayName: string | null

  loadDiagram: (diagram: Diagram) => void
  /** Load a persisted design: sets the diagram AND marks it clean/attributed
   * to `meta`, in one shot (mount, and the conflict dialog's "reload theirs"). */
  loadDesign: (diagram: Diagram, meta: DesignMeta) => void
  /** Record a successful save: current diagram becomes the clean baseline. */
  markSaved: (version: number) => void
  addNode: (node: DiagramNode) => void
  updateNodeProps: (id: string, props: Record<string, unknown>) => void
  moveNode: (id: string, x: number, y: number) => void
  /** Reposition many nodes at once (auto-arrange) — one diagram object, one
   * re-render, one solve. */
  moveNodes: (positions: Record<string, { x: number; y: number }>) => void
  removeNode: (id: string) => void
  addEdge: (edge: DiagramEdge) => void
  updateEdge: (id: string, patch: Partial<DiagramEdge>) => void
  removeEdge: (id: string) => void
  updateSettings: (patch: Partial<DiagramSettings>) => void
  setSolvePaused: (paused: boolean) => void
  setSelection: (selection: Selection) => void
  setSolveResult: (issues: Issue[], results: SolveResults | null) => void
  setSolving: (solving: boolean) => void
  setDisplayName: (name: string) => void
}

export const useStore = create<State>((set) => ({
  diagram: EMPTY_DIAGRAM,
  results: null,
  issues: [],
  solvePaused: false,
  solving: false,
  selection: null,
  designMeta: null,
  savedDiagramRef: null,
  displayName: readDisplayName(),

  loadDiagram: (diagram) =>
    set({ diagram, results: null, issues: [], selection: null }),

  loadDesign: (diagram, meta) =>
    set({
      diagram,
      savedDiagramRef: diagram,
      designMeta: meta,
      results: null,
      issues: [],
      selection: null,
    }),

  markSaved: (version) =>
    set((s) => ({
      savedDiagramRef: s.diagram,
      designMeta: s.designMeta ? { ...s.designMeta, version } : s.designMeta,
    })),

  addNode: (node) =>
    set((s) => ({ diagram: { ...s.diagram, nodes: [...s.diagram.nodes, node] } })),

  updateNodeProps: (id, props) =>
    set((s) => ({
      diagram: {
        ...s.diagram,
        nodes: s.diagram.nodes.map((n) =>
          n.id === id ? { ...n, props: { ...n.props, ...props } } : n,
        ),
      },
    })),

  moveNode: (id, x, y) =>
    set((s) => ({
      diagram: {
        ...s.diagram,
        nodes: s.diagram.nodes.map((n) => (n.id === id ? { ...n, x, y } : n)),
      },
    })),

  moveNodes: (positions) =>
    set((s) => ({
      diagram: {
        ...s.diagram,
        nodes: s.diagram.nodes.map((n) => (positions[n.id] ? { ...n, ...positions[n.id] } : n)),
      },
    })),

  removeNode: (id) =>
    set((s) => ({
      diagram: {
        ...s.diagram,
        nodes: s.diagram.nodes.filter((n) => n.id !== id),
        edges: s.diagram.edges.filter((e) => e.source !== id && e.target !== id),
      },
      selection: s.selection?.type === 'node' && s.selection.id === id ? null : s.selection,
    })),

  addEdge: (edge) =>
    set((s) => ({ diagram: { ...s.diagram, edges: [...s.diagram.edges, edge] } })),

  updateEdge: (id, patch) =>
    set((s) => ({
      diagram: {
        ...s.diagram,
        edges: s.diagram.edges.map((e) => (e.id === id ? { ...e, ...patch } : e)),
      },
    })),

  removeEdge: (id) =>
    set((s) => ({
      diagram: { ...s.diagram, edges: s.diagram.edges.filter((e) => e.id !== id) },
      selection: s.selection?.type === 'edge' && s.selection.id === id ? null : s.selection,
    })),

  updateSettings: (patch) =>
    set((s) => ({
      diagram: {
        ...s.diagram,
        settings: {
          tiers: { ...s.diagram.settings.tiers, ...patch.tiers },
          rules: { ...s.diagram.settings.rules, ...patch.rules },
        },
      },
    })),

  setSolvePaused: (paused) => set({ solvePaused: paused }),
  setSelection: (selection) => set({ selection }),
  setSolveResult: (issues, results) => set({ issues, results }),
  setSolving: (solving) => set({ solving }),
  setDisplayName: (name) => {
    try {
      localStorage.setItem(DISPLAY_NAME_KEY, name)
    } catch {
      // localStorage unavailable (private mode, etc.) — keep in-memory only.
    }
    set({ displayName: name })
  },
}))
