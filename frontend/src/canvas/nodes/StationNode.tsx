import { Handle, Position, type NodeProps } from '@xyflow/react'
import { pct } from '../../format'
import { nodeLabel, type CanvasNode } from '../nodeData'
import type { StationNodeResult } from '../../types'

export function StationNode({ data }: NodeProps<CanvasNode>) {
  const label = nodeLabel(data.diagramNode)
  const result = data.result?.kind === 'station' ? (data.result as StationNodeResult) : undefined
  const overloaded = result !== undefined && result.loading > 1.0
  const high = result !== undefined && result.loading > 0.9 && !overloaded

  return (
    <div className={`rf-node station${data.hasIssue ? ' issue' : ''}`}>
      <div className="rf-node-title">{label}</div>
      {result && (
        <div className={`rf-node-line badge ${overloaded ? 'badge-bad' : high ? 'badge-warn' : 'badge-ok'}`}>
          {pct(result.loading)} loaded
        </div>
      )}
      <Handle type="target" position={Position.Top} id="in" />
      <Handle type="source" position={Position.Bottom} id="out" />
    </div>
  )
}
