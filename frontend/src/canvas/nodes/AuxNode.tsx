import { Handle, Position, type NodeProps } from '@xyflow/react'
import { fmt } from '../../format'
import type { CanvasNode } from '../nodeData'

export function AuxNode({ data }: NodeProps<CanvasNode>) {
  const props = data.diagramNode.props
  const pKw = Number(props.p_kw ?? 0)
  const qKvar = Number(props.q_kvar ?? 0)

  return (
    <div className={`rf-node aux${data.hasIssue ? ' issue' : ''}`}>
      <div className="rf-node-title">Aux load</div>
      <div className="rf-node-line">
        {fmt(pKw)} kW / {fmt(qKvar)} kvar
      </div>
      <Handle type="target" position={Position.Top} id="in" />
    </div>
  )
}
