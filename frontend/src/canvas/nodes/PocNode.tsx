import { Handle, Position, type NodeProps } from '@xyflow/react'
import { fmt } from '../../format'
import type { CanvasNode } from '../nodeData'
import type { PocNodeResult } from '../../types'

export function PocNode({ data }: NodeProps<CanvasNode>) {
  const props = data.diagramNode.props
  const pTarget = Number(props.p_target_mw ?? 0)
  const pf = Number(props.pf ?? 0)
  const result = data.result?.kind === 'poc' ? (data.result as PocNodeResult) : undefined

  return (
    <div className={`rf-node poc${data.hasIssue ? ' issue' : ''}`}>
      <div className="rf-node-title">Point of Connection</div>
      <div className="rf-node-line">{fmt(pTarget, 1)} MW @ pf {fmt(pf, 2)}</div>
      {result && (
        <div className={`rf-node-line badge ${result.meets_target ? 'badge-ok' : 'badge-bad'}`}>
          delivered {fmt((result.p_refined_delivered_kw ?? result.p_delivered_kw) / 1000, 2)} MW
        </div>
      )}
      <Handle type="source" position={Position.Bottom} id="out" />
    </div>
  )
}
