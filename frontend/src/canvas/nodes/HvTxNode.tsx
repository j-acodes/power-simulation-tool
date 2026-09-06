import { Handle, Position, type NodeProps } from '@xyflow/react'
import { fmt } from '../../format'
import { useStore } from '../../store'
import type { CanvasNode } from '../nodeData'
import type { HvTxNodeResult } from '../../types'

export function HvTxNode({ data }: NodeProps<CanvasNode>) {
  const props = data.diagramNode.props
  const mode = String(props.mode ?? 'auto')
  const result = data.result?.kind === 'hv_tx' ? (data.result as HvTxNodeResult) : undefined
  // The design's ambient (ADR-0004) — the resolved rating shown below is
  // meaningless without it.
  const ambientC = useStore((s) => s.diagram.settings.rules.ambient_temp_c ?? 40)

  return (
    <div className={`rf-node hv_tx${data.hasIssue ? ' issue' : ''}`}>
      <div className="rf-node-title">MV/HV Transformer</div>
      <div className="rf-node-line">
        {mode === 'auto' ? 'auto-sized' : String(props.model ?? props.name ?? mode)}
      </div>
      {result && (
        <div className="rf-node-line">
          {result.name ?? 'sized'} — {fmt(result.s_rated_kva)} kVA @ {ambientC} °C
          {result.n_parallel > 1 ? ` x${result.n_parallel}` : ''}
        </div>
      )}
      <Handle type="target" position={Position.Top} id="in" />
      <Handle type="source" position={Position.Bottom} id="out" />
    </div>
  )
}
