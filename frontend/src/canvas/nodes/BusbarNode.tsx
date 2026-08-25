import { Handle, Position, type NodeProps } from '@xyflow/react'
import { fmt } from '../../format'
import type { CanvasNode } from '../nodeData'
import type { BusbarNodeResult } from '../../types'

export function BusbarNode({ data }: NodeProps<CanvasNode>) {
  const result = data.result?.kind === 'busbar' ? (data.result as BusbarNodeResult) : undefined

  return (
    <div className={`rf-node busbar${data.hasIssue ? ' issue' : ''}`}>
      <div className="rf-node-title">MV busbar</div>
      {result && (
        <div className="rf-node-line">
          {result.n_circuits} circuit{result.n_circuits === 1 ? '' : 's'} — {fmt(result.p_kw)} kW
        </div>
      )}
      <Handle type="target" position={Position.Top} id="in" />
      <Handle type="source" position={Position.Bottom} id="out" />
    </div>
  )
}
