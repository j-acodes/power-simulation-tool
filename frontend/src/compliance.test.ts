import { describe, expect, it } from 'vitest'
import { evaluateCompliance } from './compliance'
import type { Issue, ResultsSummary, SolveResults } from './types'

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
    const verdict = evaluateCompliance(results({ loading_ok: false, fleet_loading: 1.14 }), [])
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
      results({ power_balance_ok: false, loading_ok: false, all_current_ok: false }),
      [issue],
    )
    expect(verdict.reasons).toHaveLength(4)
  })
})
