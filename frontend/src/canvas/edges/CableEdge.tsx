import { BaseEdge, EdgeLabelRenderer, getStraightPath, type EdgeProps } from '@xyflow/react'
import { fmt } from '../../format'
import type { CanvasEdge } from '../edgeData'

export function CableEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
}: EdgeProps<CanvasEdge>) {
  const [path, labelX, labelY] = getStraightPath({ sourceX, sourceY, targetX, targetY })
  const edge = data?.diagramEdge
  const result = data?.result
  const hasIssue = data?.hasIssue ?? false

  const lengthLabel = edge?.length_m ? `${fmt(edge.length_m)} m` : null
  const resultLabel = result && result.sized ? `${result.cable_label} — ${fmt(result.dp_kw, 1)} kW` : null

  return (
    <>
      <BaseEdge id={id} path={path} style={{ stroke: hasIssue ? '#dc2626' : undefined, strokeWidth: hasIssue ? 2.5 : undefined }} />
      {(lengthLabel || resultLabel) && (
        <EdgeLabelRenderer>
          <div
            className={`rf-edge-label${hasIssue ? ' issue' : ''}`}
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          >
            {lengthLabel}
            {resultLabel && <div>{resultLabel}</div>}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}
