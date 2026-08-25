import type { Edge } from '@xyflow/react'
import type { DiagramEdge, EdgeResult } from '../types'

export interface CanvasEdgeData extends Record<string, unknown> {
  diagramEdge: DiagramEdge
  result?: EdgeResult
  hasIssue: boolean
}

export type CanvasEdge = Edge<CanvasEdgeData, 'cable'>
