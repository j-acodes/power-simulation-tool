import type { Node } from '@xyflow/react'
import type { DiagramNode, NodeResult } from '../types'

export interface CanvasNodeData extends Record<string, unknown> {
  diagramNode: DiagramNode
  result?: NodeResult
  hasIssue: boolean
}

export type CanvasNode = Node<CanvasNodeData, DiagramNode['kind']>
