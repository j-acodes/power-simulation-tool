import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { ResultsTables } from './ResultsTables'
import { EMPTY_DIAGRAM, useStore } from '../store'
import type { BusbarNodeResult, SolveResults, StationNodeResult } from '../types'

const station: StationNodeResult = {
  kind: 'station',
  circuit: 1,
  position: 1,
  model: 'HUAWEI_JUPITER3000',
  s_rated_kva: 3300,
  loading: 0.5,
  p_lv_kw: 1650,
  q_lv_kvar: 400,
  s_lv_kva: 1698,
  dp_tx_kw: 20,
  dq_tx_kvar: 60,
  p_mv_kw: 1630,
  q_mv_kvar: 340,
  s_mv_kva: 1665,
  i_a: 48.1,
  through_current_a: 412,
  switchgear_rated_current_a: 630,
}

const busbar: BusbarNodeResult = {
  kind: 'busbar',
  p_kw: 1650,
  q_kvar: 400,
  s_kva: 1698,
  n_circuits: 1,
  circuit_sizes: [1],
  v_kv: 20,
  i_a: 412,
  switchgear_rated_a: 630,
  switchgear_pinned: false,
  export_i_a: 412,
  export_switchgear_rated_a: 630,
  export_switchgear_pinned: false,
  feeder_i_a: [412],
  feeder_switchgear_rated_a: [630],
  feeder_switchgear_pinned: [false],
  feeder_edge_ids: ['e_t1'],
  feeder_binding_limit: ['station_switchgear'],
}

/** A minimal but complete summary — ResultsTables renders PlantSummary
 * unconditionally, so every field it reads has to exist even though this
 * suite only asserts on the Stations/Busbars tables (ticket 07). */
const summary = {
  branches: [],
  p_inv_kw: 1650, q_inv_kvar: 400, s_inv_kva: 1698, pf_inv: 0.97,
  p_inv_refined_kw: 1650, q_inv_refined_kvar: 400, s_inv_refined_kva: 1698,
  correction_factor: 1.0,
  p_poc_target_kw: 1600, p_poc_delivered_kw: 1600, q_poc_delivered_kvar: 390,
  p_poc_refined_delivered_kw: 1600,
  n_stations: 1, n_circuits: 1, circuit_sizes: [1],
  s_fleet_kva: 3300, fleet_loading: 0.5, loading_ok: true,
  total_cable_loss_kw: 5, total_transformer_loss_kw: 20, total_active_loss_kw: 25,
  loss_percent_of_p_inv: 1.5, worst_trunk_current_a: 412, all_current_ok: true,
  power_balance_ok: true, v_mv_kv: 20, v_hv_kv: null,
}

function withResults() {
  useStore.setState({
    diagram: {
      ...EMPTY_DIAGRAM,
      nodes: [
        { id: 's1', kind: 'station', x: 0, y: 0, props: { model: 'HUAWEI_JUPITER3000' } },
        { id: 'bus', kind: 'busbar', x: 0, y: 0, props: {} },
      ],
    },
    designMeta: null,
    results: {
      edges: {}, nodes: { s1: station, bus: busbar }, warnings: [], summary,
    } as unknown as SolveResults,
  })
}

describe('ResultsTables — what limited each circuit (ticket 07)', () => {
  beforeEach(() => {
    useStore.setState({ selection: null, diagram: EMPTY_DIAGRAM, designMeta: null, results: null })
  })

  it('shows through current beside switchgear rated current, per station', () => {
    withResults()
    render(<ResultsTables onClose={() => {}} />)

    expect(screen.getByText('Through / rated [A]')).toBeTruthy()
    expect(screen.getByText('412 / 630')).toBeTruthy()
  })

  it('names the circuit binding limit in plain words', () => {
    withResults()
    render(<ResultsTables onClose={() => {}} />)

    expect(screen.getByText('Binding limit')).toBeTruthy()
    // "Station switchgear" also labels the plant-summary row below, so this
    // is scoped to the row it appears in beside the circuit it decided.
    const circuitRow = screen.getByText('Circuit 1').closest('tr')
    expect(circuitRow).toBeTruthy()
    expect(circuitRow!.textContent).toContain('Station switchgear')
  })

  it('shows feeders used against the feeders-per-busbar setting and busbar current against 4000 A', () => {
    withResults()
    render(<ResultsTables onClose={() => {}} />)

    expect(screen.getByText('1 / 12')).toBeTruthy() // default feeders-per-busbar
    expect(screen.getByText('412 / 4000 A')).toBeTruthy()
  })
})
