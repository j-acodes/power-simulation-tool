import type { Node } from '@xyflow/react'
import type { DiagramNode, NodeResult } from '../types'

/** The name a block goes by — the title drawn on the canvas, reused wherever a
 * node has to be named in prose or a table. */
export function nodeLabel(node: DiagramNode): string {
  switch (node.kind) {
    case 'poc':
      return 'Point of Connection'
    case 'hv_tx':
      return 'MV/HV Transformer'
    case 'busbar':
      return 'MV busbar'
    case 'aux':
      return 'Aux load'
    case 'station':
      return node.props.mode === 'custom'
        ? String(node.props.name ?? 'Custom station')
        : String(node.props.model ?? 'no model')
  }
}

export interface CanvasNodeData extends Record<string, unknown> {
  diagramNode: DiagramNode
  result?: NodeResult
  hasIssue: boolean
}

export type CanvasNode = Node<CanvasNodeData, DiagramNode['kind']>
