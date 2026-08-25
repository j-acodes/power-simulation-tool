import type { Issue, SolveResults } from './types'

export interface ComplianceVerdict {
  compliant: boolean
  reasons: string[]
}

/** Delivered active power must land within this fraction of the POC target. */
const POWER_TOLERANCE = 0.005

/**
 * POC grid-compliance verdict, derived entirely from the last solve's summary
 * flags (already computed by the engine) plus any outstanding validation
 * issues. All criteria must hold for a COMPLIANT verdict:
 *   - delivered active power within 0.5% of the target
 *   - power_balance_ok
 *   - the station fleet not overloaded (loading_ok)
 *   - every circuit within its current cap (all_current_ok)
 *   - zero validation issues
 */
export function evaluateCompliance(results: SolveResults, issues: Issue[]): ComplianceVerdict {
  const reasons: string[] = []
  const { summary } = results

  if (issues.length > 0) {
    reasons.push(
      `${issues.length} validation issue${issues.length === 1 ? '' : 's'} on the diagram.`,
    )
  }

  const target = summary.p_poc_target_kw
  const delivered = summary.p_poc_refined_delivered_kw ?? summary.p_poc_delivered_kw
  if (target > 0) {
    const deviation = Math.abs(delivered - target) / target
    if (deviation > POWER_TOLERANCE) {
      reasons.push(
        `Delivered active power (${(delivered / 1000).toFixed(2)} MW) is ` +
          `${(deviation * 100).toFixed(2)}% off the ${(target / 1000).toFixed(2)} MW target ` +
          `(limit 0.5%).`,
      )
    }
  }

  if (!summary.power_balance_ok) {
    reasons.push('The internal power-balance check failed.')
  }

  if (!summary.loading_ok) {
    reasons.push(
      `The station fleet is overloaded — ${(summary.fleet_loading * 100).toFixed(0)}% of its ` +
        `combined rating.`,
    )
  }

  if (!summary.all_current_ok) {
    reasons.push(
      `A circuit exceeds its current cap — worst trunk current ` +
        `${summary.worst_trunk_current_a.toFixed(0)} A vs. a ` +
        `${summary.max_circuit_current_a.toFixed(0)} A limit.`,
    )
  }

  return { compliant: reasons.length === 0, reasons }
}
