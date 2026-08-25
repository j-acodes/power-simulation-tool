import { useCallback, useMemo } from 'react'
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Connection,
  type EdgeChange,
  type NodeChange,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useStore } from '../store'
import type { DiagramNode, NodeKind } from '../types'
import { defaultLengthM, inferTier } from './connect'
import { AuxNode } from './nodes/AuxNode'
import { BusbarNode } from './nodes/BusbarNode'
import { HvTxNode } from './nodes/HvTxNode'
import { PocNode } from './nodes/PocNode'
import { StationNode } from './nodes/StationNode'
import type { CanvasNode } from './nodeData'
import { CableEdge } from './edges/CableEdge'
import type { CanvasEdge } from './edgeData'

const nodeTypes = { poc: PocNode, hv_tx: HvTxNode, busbar: BusbarNode, station: StationNode, aux: AuxNode }
const edgeTypes = { cable: CableEdge }

export interface PaletteDropPayload {
  kind: NodeKind
  props: DiagramNode['props']
}

function FlowCanvas() {
  const diagram = useStore((s) => s.diagram)
  const results = useStore((s) => s.results)
  const issues = useStore((s) => s.issues)
  const selection = useStore((s) => s.selection)
  const addNode = useStore((s) => s.addNode)
  const moveNode = useStore((s) => s.moveNode)
  const removeNode = useStore((s) => s.removeNode)
  const addEdge = useStore((s) => s.addEdge)
  const removeEdge = useStore((s) => s.removeEdge)
  const setSelection = useStore((s) => s.setSelection)
  const { screenToFlowPosition } = useReactFlow()

  const issueNodeIds = useMemo(() => {
    const all = [...issues, ...(results?.warnings ?? [])]
    return new Set(all.map((i) => i.node_id).filter((id): id is string => id != null))
  }, [issues, results])
  const issueEdgeIds = useMemo(() => {
    const all = [...issues, ...(results?.warnings ?? [])]
    return new Set(all.map((i) => i.edge_id).filter((id): id is string => id != null))
  }, [issues, results])

  const rfNodes: CanvasNode[] = useMemo(
    () =>
      diagram.nodes.map((n) => ({
        id: n.id,
        type: n.kind,
        position: { x: n.x, y: n.y },
        data: { diagramNode: n, result: results?.nodes[n.id], hasIssue: issueNodeIds.has(n.id) },
        selected: selection?.type === 'node' && selection.id === n.id,
      })),
    [diagram.nodes, results, issueNodeIds, selection],
  )

  const rfEdges: CanvasEdge[] = useMemo(
    () =>
      diagram.edges.map((e) => ({
        id: e.id,
        type: 'cable',
        source: e.source,
        target: e.target,
        data: { diagramEdge: e, result: results?.edges[e.id], hasIssue: issueEdgeIds.has(e.id) },
        selected: selection?.type === 'edge' && selection.id === e.id,
      })),
    [diagram.edges, results, issueEdgeIds, selection],
  )

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      for (const change of changes) {
        if (change.type === 'position' && change.position) {
          moveNode(change.id, change.position.x, change.position.y)
        } else if (change.type === 'remove') {
          removeNode(change.id)
        }
      }
    },
    [moveNode, removeNode],
  )

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      for (const change of changes) {
        if (change.type === 'remove') removeEdge(change.id)
      }
    },
    [removeEdge],
  )

  const onConnect = useCallback(
    (connection: Connection) => {
      const source = diagram.nodes.find((n) => n.id === connection.source)
      const target = diagram.nodes.find((n) => n.id === connection.target)
      if (!source || !target || !connection.source || !connection.target) return
      const tier = inferTier(source.kind, target.kind)
      const length_m = defaultLengthM(source.kind, target.kind)
      addEdge({
        id: crypto.randomUUID(),
        source: connection.source,
        target: connection.target,
        tier,
        ...(length_m !== undefined ? { length_m } : {}),
        sizing: { mode: 'auto' },
      })
    },
    [diagram.nodes, addEdge],
  )

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const raw = event.dataTransfer.getData('application/reactflow')
      if (!raw) return
      const payload = JSON.parse(raw) as PaletteDropPayload
      if ((payload.kind === 'poc' || payload.kind === 'busbar') && diagram.nodes.some((n) => n.kind === payload.kind)) {
        return
      }
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY })
      addNode({ id: crypto.randomUUID(), kind: payload.kind, x: position.x, y: position.y, props: payload.props })
    },
    [diagram.nodes, addNode, screenToFlowPosition],
  )

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  return (
    <div className="rf-wrapper" onDrop={onDrop} onDragOver={onDragOver}>
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_, node) => setSelection({ type: 'node', id: node.id })}
        onEdgeClick={(_, edge) => setSelection({ type: 'edge', id: edge.id })}
        onPaneClick={() => setSelection(null)}
        fitView
      >
        <Background />
        <Controls position="bottom-right" />
      </ReactFlow>
    </div>
  )
}

export function Editor() {
  return (
    <ReactFlowProvider>
      <FlowCanvas />
    </ReactFlowProvider>
  )
}
