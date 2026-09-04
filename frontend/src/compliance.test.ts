import { describe, expect, it } from 'vitest'
import { evaluateCompliance } from './compliance'
import type { BranchSummary, Issue, ResultsSummary, SolveResults } from './types'

/** A PV fleet that passes both hard gates. */
function fleet(overrides: Partial<BranchSummary> = {}): BranchSummary {
  return {
    kind: 'pv',
    p_inv_refined_kw: 45000,
    q_inv_refined_kvar: 14800,
    s_inv_refined_kva: 47370,
    p_poc_target_kw: 45000,
    p_poc_delivered_kw: 45000,
    p_poc_refined_delivered_kw: 45000,
    fleet_loading: 0.83,
    loading_ok: true,
    max_loading: 1.0,
    bess_aux_p_kw: 0,
    bess_aux_q_kvar: 0,
    containers: null,
    e_delivered_kwh: null,
    e_required_kwh: null,
    energy_ok: null,
    ...overrides,
  } as BranchSummary
}

/** A summary that passes every criterion; each test breaks exactly one. */
function summary(overrides: Partial<ResultsSummary> = {}): ResultsSummary {
  return {
    p_poc_target_kw: 45000,
    p_poc_delivered_kw: 45000,
    p_poc_refined_delivered_kw: null,
    power_balance_ok: true,
    loading_ok: true,
    all_current_ok: true,
    fleet_loading: 0.83,
    worst_trunk_current_a: 417,
    max_circuit_current_a: 600,
    branches: [fleet()],
    ...overrides,
  } as ResultsSummary
}

function results(overrides: Partial<ResultsSummary> = {}): SolveResults {
  return { edges: {}, nodes: {}, warnings: [], summary: summary(overrides) }
}

const issue: Issue = { code: 'x', message: 'bad', node_id: null, edge_id: null }

describe('evaluateCompliance', () => {
  it('is compliant when every criterion holds', () => {
    expect(evaluateCompliance(results(), [])).toEqual({ compliant: true, reasons: [] })
  })

  it('fails on outstanding validation issues', () => {
    const verdict = evaluateCompliance(results(), [issue])
    expect(verdict.compliant).toBe(false)
    expect(verdict.reasons[0]).toContain('1 validation issue')
  })

  it('accepts delivered power inside the 0.5% tolerance', () => {
    // 0.4% under target
    expect(evaluateCompliance(results({ p_poc_delivered_kw: 44820 }), []).compliant).toBe(true)
  })

  it('rejects delivered power outside the 0.5% tolerance', () => {
    // 1% under target
    const verdict = evaluateCompliance(results({ p_poc_delivered_kw: 44550 }), [])
    expect(verdict.compliant).toBe(false)
    expect(verdict.reasons[0]).toContain('off the 45.00 MW target')
  })

  it('judges the refined delivered power when there is one', () => {
    const verdict = evaluateCompliance(
      results({ p_poc_delivered_kw: 44550, p_poc_refined_delivered_kw: 45000 }),
      [],
    )
    expect(verdict.compliant).toBe(true)
  })

  it('skips the power check when there is no target', () => {
    expect(
      evaluateCompliance(results({ p_poc_target_kw: 0, p_poc_delivered_kw: 0 }), []).compliant,
    ).toBe(true)
  })

  it('fails on a broken power balance', () => {
    const verdict = evaluateCompliance(results({ power_balance_ok: false }), [])
    expect(verdict.compliant).toBe(false)
    expect(verdict.reasons[0]).toContain('power-balance')
  })

  it('fails on an overloaded fleet', () => {
    // Loading is a per-fleet fact now: the gate is judged against that fleet's
    // own maximum, so the figure lives on the branch, not on the plant summary.
    const verdict = evaluateCompliance(
      results({ branches: [fleet({ loading_ok: false, fleet_loading: 1.14 })] }),
      [],
    )
    expect(verdict.compliant).toBe(false)
    expect(verdict.reasons[0]).toContain('114%')
  })

  it('fails on a circuit over its current cap', () => {
    const verdict = evaluateCompliance(results({ all_current_ok: false, worst_trunk_current_a: 812 }), [])
    expect(verdict.compliant).toBe(false)
    expect(verdict.reasons[0]).toContain('812 A')
  })

  it('reports every failing criterion at once', () => {
    const verdict = evaluateCompliance(
      results({
        power_balance_ok: false,
        branches: [fleet({ loading_ok: false })],
        all_current_ok: false,
      }),
      [issue],
    )
    expect(verdict.reasons).toHaveLength(4)
  })
})


describe('evaluateCompliance — per-fleet gates', () => {
  it('names the fleet whose loading failed, against its own maximum', () => {
    // Loading is a per-fleet gate: a hybrid can have a compliant PV fleet and an
    // overloaded BESS one, and "the station fleet is overloaded" would not tell
    // the engineer which, nor against what limit.
    const verdict = evaluateCompliance(
      results({
        loading_ok: false,
        branches: [fleet(), fleet({ kind: 'bess', loading_ok: false, fleet_loading: 1.4, max_loading: 0.9 })],
      }),
      [],
    )
    expect(verdict.compliant).toBe(false)
    const reason = verdict.reasons.find((r) => r.includes('BESS'))
    expect(reason).toBeDefined()
    expect(reason).toContain('140')
    expect(reason).toContain('90')
    // The compliant PV fleet must not be blamed alongside it.
    expect(verdict.reasons.some((r) => r.includes('PV'))).toBe(false)
  })

  it('fails on delivered energy even when every loading gate passes', () => {
    // The second hard gate. Both are hard and independent, so an engineer can
    // see which one failed and by how much.
    const verdict = evaluateCompliance(
      results({
        branches: [
          fleet({ kind: 'bess', containers: 8, e_delivered_kwh: 40000, e_required_kwh: 48000, energy_ok: false }),
        ],
      }),
      [],
    )
    expect(verdict.compliant).toBe(false)
    expect(verdict.reasons).toHaveLength(1)
    const [reason] = verdict.reasons
    expect(reason).toContain('40.0')
    expect(reason).toContain('48.0')
  })

  it('passes when the energy gate is met', () => {
    expect(
      evaluateCompliance(
        results({
          branches: [
            fleet({ kind: 'bess', containers: 8, e_delivered_kwh: 40000, e_required_kwh: 12000, energy_ok: true }),
          ],
        }),
        [],
      ).compliant,
    ).toBe(true)
  })

  it('does not judge energy when no discharge duration was chosen', () => {
    // Every design saved before this ticket. The gate has nothing to judge
    // against, and inventing a duration to judge it by would be worse.
    expect(
      evaluateCompliance(results({ branches: [fleet({ kind: 'bess' })] }), []).compliant,
    ).toBe(true)
  })
})
