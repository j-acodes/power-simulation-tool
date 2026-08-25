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

  loadDiagram: (diagram: Diagram) => void
  addNode: (node: DiagramNode) => void
  updateNodeProps: (id: string, props: Record<string, unknown>) => void
  moveNode: (id: string, x: number, y: number) => void
  removeNode: (id: string) => void
  addEdge: (edge: DiagramEdge) => void
  updateEdge: (id: string, patch: Partial<DiagramEdge>) => void
  removeEdge: (id: string) => void
  updateSettings: (patch: Partial<DiagramSettings>) => void
  setSolvePaused: (paused: boolean) => void
  setSelection: (selection: Selection) => void
  setSolveResult: (issues: Issue[], results: SolveResults | null) => void
  setSolving: (solving: boolean) => void
}

export const useStore = create<State>((set) => ({
  diagram: EMPTY_DIAGRAM,
  results: null,
  issues: [],
  solvePaused: false,
  solving: false,
  selection: null,

  loadDiagram: (diagram) =>
    set({ diagram, results: null, issues: [], selection: null }),

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
}))
