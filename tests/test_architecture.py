"""Tests for the plant architecture (Stage 2) and the mixed transformer fleet.

Rules: the station fleet (models + counts) comes from Stage 1 and runs at
uniform per-unit loading (each station's share is proportional to its rating);
stations are grouped into MV circuits respecting a max current per circuit,
with the current computed from the actual MV-side power (LV share minus the
station transformer's own losses), never from the nameplate; within a circuit
the biggest stations sit nearest the substation.
"""

import math

import pytest

from powertool import (
    Cable,
    Chain,
    ChainElement,
    Transformer,
    TransformerGroup,
    current_a,
    size_pv_inverters,
)
from powertool import architecture
from powertool.architecture import (
    arrange_plant,
    arrange_plant_manual,
    assign_circuits,
    size_architecture,
    size_branch,
    size_circuits,
    size_plant,
    station_mv_output,
)
from powertool.sizing import SizingResult


def _tx_2500() -> Transformer:
    # Representative 2500 kVA 20/0.8 kV station transformer.
    return Transformer("TX_2500", s_rated_kva=2500, uk_percent=6.0, pk_kw=24.0,
                       p0_kw=2.5, i0_percent=0.8, hv_kv=20, lv_kv=0.8)


def _tx_9000() -> Transformer:
    # A big PV station, parameters per the project's design assumptions.
    return Transformer("TX_9000", s_rated_kva=9000, uk_percent=8.0, pk_kw=90.0,
                       p0_kw=9.0, i0_percent=0.0, lv_kv=0.8, brand="BrandA")


def _tx_3300() -> Transformer:
    return Transformer("TX_3300", s_rated_kva=3300, uk_percent=8.0, pk_kw=33.0,
                       p0_kw=3.3, i0_percent=0.0, lv_kv=0.8, brand="BrandB")


def _stage1(p_inv_kw: float, q_inv_kvar: float) -> SizingResult:
    # Minimal Stage-1 result: only the inverter-level figures matter here.
    s = math.hypot(p_inv_kw, q_inv_kvar)
    return SizingResult(
        p_poc_kw=0.0, q_poc_kvar=0.0, pf_target=1.0,
        p_inv_kw=p_inv_kw, q_inv_kvar=q_inv_kvar, s_inv_kva=s,
        pf_inv=p_inv_kw / s, losses=[], power_balance_ok=True,
    )


# --- station_mv_output ----------------------------------------------------------

def test_station_mv_output_subtracts_transformer_losses():
    tx = _tx_2500()
    p_lv, q_lv = 2400.0, 500.0
    dp, dq = tx.losses(math.hypot(p_lv, q_lv))
    p_mv, q_mv = station_mv_output(p_lv, q_lv, tx)
    assert p_mv == pytest.approx(p_lv - dp)
    assert q_mv == pytest.approx(q_lv - dq)


def test_station_mv_output_degenerate_losses_raise():
    bad = Transformer("BAD", s_rated_kva=100, uk_percent=50.0, pk_kw=40.0, p0_kw=80.0)
    with pytest.raises(ValueError):
        station_mv_output(100.0, 0.0, bad)


# --- TransformerGroup (parallel mixed fleet) -------------------------------------

def test_group_of_one_type_equals_n_parallel_transformer():
    # A group of n identical units must reproduce the existing n_parallel math.
    tx = _tx_2500()
    n, s = 4, 8_000.0
    group = TransformerGroup("4x2500", units=[(tx, n)])
    dp_unit, dq_unit = tx.losses(s / n)
    dp_g, dq_g = group.losses(s)
    assert dp_g == pytest.approx(dp_unit * n)
    assert dq_g == pytest.approx(dq_unit * n)


def test_mixed_group_losses_at_equal_per_unit_loading():
    # 1x9000 + 2x3300 carrying 14,000 kVA: r = 14000/15600 for every unit.
    group = TransformerGroup("mixed", units=[(_tx_9000(), 1), (_tx_3300(), 2)])
    assert group.s_rated_total_kva == 15_600
    assert group.n_units == 3
    r_sq = (14_000 / 15_600) ** 2
    dp, dq = group.losses(14_000)
    assert dp == pytest.approx((90.0 + 2 * 33.0) * r_sq + (9.0 + 2 * 3.3))
    ux9 = _tx_9000().ux_percent / 100.0
    ux3 = _tx_3300().ux_percent / 100.0
    assert dq == pytest.approx(r_sq * (ux9 * 9000 + 2 * ux3 * 3300))


def test_group_validations():
    with pytest.raises(ValueError):
        TransformerGroup("empty", units=[])
    with pytest.raises(ValueError):
        TransformerGroup("bad count", units=[(_tx_3300(), 0)])
    group = TransformerGroup("ok", units=[(_tx_3300(), 2)])
    with pytest.raises(ValueError):
        ChainElement(group, v_kv=20.0, n_parallel=2)  # counts live in the group


def test_series_bug_regression_group_vs_cascaded_blocks():
    # The reported bug: two station blocks added to the Stage-1 chain were
    # cascaded in SERIES, each carrying the full plant power. As a parallel
    # group they share it, so losses must be far smaller.
    p_poc = 15_000.0
    series = Chain([
        ChainElement(_tx_3300(), v_kv=20.0, n_parallel=1),
        ChainElement(_tx_9000(), v_kv=20.0, n_parallel=1),
    ])
    group = Chain([
        ChainElement(TransformerGroup("fleet", units=[(_tx_3300(), 1), (_tx_9000(), 1)]),
                     v_kv=20.0),
    ])
    res_series = size_pv_inverters(series, p_poc_kw=p_poc, pf_target=0.98)
    res_group = size_pv_inverters(group, p_poc_kw=p_poc, pf_target=0.98)
    assert res_group.total_active_loss_kw < 0.25 * res_series.total_active_loss_kw
    # Sanity: the fleet runs near full load (15 MVA on 12.3 MVA... overloaded
    # slightly), so its loss is on the order of pk at r ~ 1.2.
    assert res_group.total_active_loss_kw < 250.0


# --- assign_circuits --------------------------------------------------------------

def test_assign_worked_example_18_capped_at_5():
    # 18 identical stations, cap 380 A at 70 A each -> balanced 5+5+4+4.
    bins = assign_circuits([70.0] * 18, 380.0)
    assert sorted((len(b) for b in bins), reverse=True) == [5, 5, 4, 4]
    assert sorted(i for b in bins for i in b) == list(range(18))


def test_assign_even_split():
    assert [len(b) for b in assign_circuits([70.0] * 15, 380.0)] == [5, 5, 5]


def test_assign_single_circuit_when_cap_allows():
    assert [len(b) for b in assign_circuits([10.0] * 6, 1000.0)] == [6]


def test_assign_one_station():
    assert assign_circuits([70.0], 380.0) == [[0]]


def test_assign_station_exceeds_cap_raises():
    with pytest.raises(ValueError):
        assign_circuits([100.0] * 4, 50.0)


def test_assign_exact_cap_boundary():
    # Cap exactly 5x the station current must allow 5 per circuit.
    assert [len(b) for b in assign_circuits([76.0] * 10, 380.0)] == [5, 5]


def test_assign_mixed_currents_respect_cap():
    currents = [300.0, 300.0, 100.0, 100.0, 100.0, 100.0]
    bins = assign_circuits(currents, 400.0)
    assert len(bins) == 3  # lower bound: 1000/400 -> 3 circuits
    for b in bins:
        assert sum(currents[i] for i in b) <= 400.0 + 1e-9
    assert sorted(i for b in bins for i in b) == list(range(6))


def test_assign_invariants():
    for n in (1, 2, 7, 18, 23, 40):
        bins = assign_circuits([70.0] * n, 380.0)
        sizes = [len(b) for b in bins]
        assert sum(sizes) == n
        assert max(sizes) - min(sizes) <= 1  # identical stations stay balanced
        assert max(sizes) <= math.floor(380.0 / 70.0)


# --- arrange_plant ----------------------------------------------------------------

def test_arrange_plant_45mw_example():
    # 18 x 2500 kVA from Stage 1; per-station MV current ~69 A, so a 380 A
    # circuit cap gives at most 5 per circuit -> 4 circuits, 5+5+4+4.
    stage1 = _stage1(p_inv_kw=43_000, q_inv_kvar=9_000)
    layout = arrange_plant(
        stage1, [(_tx_2500(), 18)],
        max_circuit_current_a=380.0,
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    assert layout.n_transformers == 18
    assert layout.circuit_sizes == [5, 5, 4, 4]
    assert layout.circuit_sizes_label == "4 (5+5+4+4)"
    assert layout.s_fleet_kva == 45_000
    assert layout.fleet_loading == pytest.approx(stage1.s_inv_kva / 45_000)
    assert layout.loading_ok

    plan = layout.circuit_plans[0][0]
    # Equal ratings -> equal shares of the Stage-1 inverter output.
    assert plan.p_lv_kw == pytest.approx(43_000 / 18)
    assert plan.q_lv_kvar == pytest.approx(9_000 / 18)
    assert plan.i_a == pytest.approx(current_a(plan.s_mv_kva, 20.0))
    assert plan.p_mv_kw < plan.p_lv_kw  # transformer losses subtracted
    # Every circuit respects the current cap.
    for circuit in layout.circuit_plans:
        assert sum(p.i_a for p in circuit) <= 380.0 + 1e-9


def test_arrange_mixed_fleet_shares_and_ordering():
    # 1x9000 + 2x3300: shares proportional to rating, biggest nearest the
    # substation (position 0) in its circuit.
    stage1 = _stage1(p_inv_kw=14_500, q_inv_kvar=2_000)
    layout = arrange_plant(
        stage1, [(_tx_3300(), 2), (_tx_9000(), 1)],  # order given must not matter
        max_circuit_current_a=10_000.0,
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    assert layout.n_transformers == 3
    assert layout.n_circuits == 1
    plans = layout.circuit_plans[0]
    assert [p.transformer.s_rated_kva for p in plans] == [9000, 3300, 3300]
    big, small = plans[0], plans[1]
    assert big.p_lv_kw / small.p_lv_kw == pytest.approx(9000 / 3300)
    assert big.loading == pytest.approx(small.loading)  # uniform per-unit loading
    assert big.loading == pytest.approx(stage1.s_inv_kva / 15_600)


def test_arrange_loading_flag():
    stage1 = _stage1(p_inv_kw=20_000, q_inv_kvar=0.0)  # 20 MVA on 15.6 MVA fleet
    layout = arrange_plant(
        stage1, [(_tx_9000(), 1), (_tx_3300(), 2)],
        max_circuit_current_a=10_000.0,
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    assert layout.fleet_loading > 1.0
    assert not layout.loading_ok


def test_arrange_plant_invalid_inputs():
    stage1 = _stage1(43_000, 9_000)
    with pytest.raises(ValueError):
        arrange_plant(stage1, [(_tx_2500(), 18)], max_circuit_current_a=380.0,
                      trunk_length_km=-1.0, spacing_km=0.35, v_mv_kv=20.0)
    with pytest.raises(ValueError):
        arrange_plant(stage1, [], max_circuit_current_a=380.0,
                      trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0)


# --- arrange_plant_manual (drawn arrangement) -------------------------------------

def _as_drawn(layout) -> list[list[Transformer]]:
    """The circuits of a layout as a drawing would hand them over."""
    return [[plan.transformer for plan in circuit] for circuit in layout.circuit_plans]


def _lengths_of(layout) -> dict[tuple[int, int], float]:
    """A COMPLETE segment_lengths map reproducing a layout's trunk/spacing."""
    return {
        (c_idx, s_idx): (layout.trunk_length_km if s_idx == 1 else layout.spacing_km)
        for c_idx, n_stations in enumerate(layout.circuit_sizes, start=1)
        for s_idx in range(1, n_stations + 1)
    }


def test_manual_arrangement_equals_the_auto_one_when_fed_its_own_output():
    # The de-risking test for the diagram editor: hand arrange_plant_manual the
    # exact arrangement arrange_plant produced and every number downstream must
    # be identical — the manual path changes WHO decides the layout, never the
    # physics.
    stage1, auto = _full_plant_inputs()
    manual = arrange_plant_manual(
        stage1, _as_drawn(auto),
        max_circuit_current_a=auto.max_circuit_current_a, v_mv_kv=auto.v_mv_kv,
    )

    assert manual.fleet == auto.fleet  # 18 identical stations aggregate back
    assert manual.circuit_sizes == auto.circuit_sizes
    assert manual.fleet_loading == auto.fleet_loading
    assert manual.loading_ok == auto.loading_ok
    assert manual.circuit_plans == auto.circuit_plans

    auto_arch = size_architecture(
        auto, stage1, _catalogue(), hv_transformer=_hv_tx(),
        aux_p_kw=120.0, aux_q_kvar=40.0, p_poc_target_kw=43_000.0)
    manual_arch = size_architecture(
        manual, stage1, _catalogue(), segment_lengths=_lengths_of(auto),
        hv_transformer=_hv_tx(),
        aux_p_kw=120.0, aux_q_kvar=40.0, p_poc_target_kw=43_000.0)

    assert manual_arch.p_poc_delivered_kw == auto_arch.p_poc_delivered_kw
    assert manual_arch.q_poc_delivered_kvar == auto_arch.q_poc_delivered_kvar
    assert manual_arch.correction_factor == auto_arch.correction_factor
    assert manual_arch.s_inv_refined_kva == auto_arch.s_inv_refined_kva
    assert manual_arch.total_active_loss_kw == auto_arch.total_active_loss_kw
    for got, expected in zip(manual_arch.circuits, auto_arch.circuits):
        assert got.i_trunk_a == expected.i_trunk_a
        assert [s.cable_label for s in got.segments] == \
               [s.cable_label for s in expected.segments]
        assert [s.dp_kw for s in got.segments] == [s.dp_kw for s in expected.segments]
        assert [s.length_km for s in got.segments] == \
               [s.length_km for s in expected.segments]


def test_manual_arrangement_never_reorders_what_was_drawn():
    # The positional bijection with the canvas: a deliberately "wrong" drawing —
    # the small station first, the light circuit first — must survive untouched.
    # arrange_plant would sort both the other way round.
    stage1 = _stage1(p_inv_kw=14_500, q_inv_kvar=2_000)
    drawn = [[_tx_3300()], [_tx_3300(), _tx_9000()]]
    layout = arrange_plant_manual(stage1, drawn, max_circuit_current_a=10_000.0,
                                  v_mv_kv=20.0)

    assert layout.circuit_sizes == [1, 2]
    assert [[p.transformer.s_rated_kva for p in c] for c in layout.circuit_plans] == \
           [[3300], [3300, 9000]]
    # Same fleet, auto-arranged: one circuit, biggest station nearest the busbar.
    auto = arrange_plant(stage1, [(_tx_3300(), 2), (_tx_9000(), 1)],
                         max_circuit_current_a=10_000.0, trunk_length_km=0.8,
                         spacing_km=0.35, v_mv_kv=20.0)
    assert auto.circuit_sizes == [3]
    assert layout.fleet_loading == auto.fleet_loading  # same fleet, same loading

    # Segment 1 of circuit 2 (the trunk) feeds the drawn order, not a sorted one.
    (small, big) = size_circuits(layout, _catalogue(),
                                 segment_lengths=_lengths_of(layout))
    assert [st.s_rated_kva for st in big.stations] == [3300, 9000]
    assert big.segments[-1].p_kw == pytest.approx(layout.circuit_plans[1][1].p_mv_kw)


def test_manual_arrangement_mixed_models_share_by_own_rating():
    # Mixed models on ONE drawn circuit: uniform per-unit loading, so each
    # station's LV share is proportional to its own rating and each gets its own
    # StationPlan (its own losses, its own current).
    stage1 = _stage1(p_inv_kw=14_500, q_inv_kvar=2_000)
    layout = arrange_plant_manual(
        stage1, [[_tx_9000(), _tx_3300(), _tx_3300()]],
        max_circuit_current_a=10_000.0, v_mv_kv=20.0,
    )

    assert layout.fleet == [(_tx_9000(), 1), (_tx_3300(), 2)]  # counts aggregated
    assert layout.s_fleet_kva == 15_600
    big, small, small2 = layout.circuit_plans[0]
    assert big.p_lv_kw / small.p_lv_kw == pytest.approx(9000 / 3300)
    assert big.loading == pytest.approx(small.loading)
    assert big.loading == pytest.approx(stage1.s_inv_kva / 15_600)
    assert small.i_a == pytest.approx(small2.i_a)
    assert big.i_a > small.i_a
    assert big.p_mv_kw < big.p_lv_kw  # own transformer losses, own share


def test_manual_arrangement_accepts_an_over_cap_drawing():
    # The user drew it: an over-current circuit is reported, never refused.
    stage1 = _stage1(p_inv_kw=14_500, q_inv_kvar=2_000)
    layout = arrange_plant_manual(stage1, [[_tx_9000(), _tx_3300()]],
                                  max_circuit_current_a=50.0, v_mv_kv=20.0)
    (circuit,) = size_circuits(layout, _catalogue(),
                               segment_lengths=_lengths_of(layout))
    assert not circuit.current_ok
    assert circuit.i_trunk_a > 50.0


def test_manual_arrangement_needs_stations():
    stage1 = _stage1(43_000, 9_000)
    with pytest.raises(ValueError):
        arrange_plant_manual(stage1, [], max_circuit_current_a=380.0, v_mv_kv=20.0)
    with pytest.raises(ValueError):
        arrange_plant_manual(stage1, [[_tx_2500()], []],
                             max_circuit_current_a=380.0, v_mv_kv=20.0)


# --- size_circuits ----------------------------------------------------------------

def _catalogue(b_us: float = 60.0) -> list[Cable]:
    # A small and a large MV cable, enough to force different picks per segment.
    return [
        Cable("AL_95", r_ohm_per_km=0.32, x_ohm_per_km=0.125, b_us_per_km=b_us * 0.7,
              cross_section_mm2=95, material="aluminium", rated_current_a=235,
              rated_voltage_kv=20),
        Cable("AL_400", r_ohm_per_km=0.0778, x_ohm_per_km=0.105, b_us_per_km=b_us,
              cross_section_mm2=400, material="aluminium", rated_current_a=565,
              rated_voltage_kv=20),
    ]


def _layout_one_circuit(n_stations: int = 3, q_inv_kvar: float = 2_000.0):
    # n identical 2500 kVA stations in a single circuit (generous current cap).
    stage1 = _stage1(p_inv_kw=2_400.0 * n_stations, q_inv_kvar=q_inv_kvar)
    return arrange_plant(
        stage1, [(_tx_2500(), n_stations)],
        max_circuit_current_a=10_000.0,
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )


def test_segment_loading_cumulative_and_decreasing():
    layout = _layout_one_circuit(n_stations=3)
    assert layout.circuit_sizes == [3]
    (circuit,) = size_circuits(layout, _catalogue())
    plan = layout.circuit_plans[0][0]

    assert len(circuit.segments) == 3
    assert [seg.index for seg in circuit.segments] == [1, 2, 3]
    assert circuit.segments[0].length_km == pytest.approx(0.8)
    assert circuit.segments[1].length_km == pytest.approx(0.35)

    # The far segment carries exactly one station's MV output.
    far = circuit.segments[-1]
    assert far.p_kw == pytest.approx(plan.p_mv_kw)
    assert far.q_kvar == pytest.approx(plan.q_mv_kvar)

    # S strictly decreases toward the far end (each span sheds one station).
    s_values = [seg.s_kva for seg in circuit.segments]
    assert s_values[0] > s_values[1] > s_values[2]

    # Trunk power: 3 stations minus the cable losses already consumed behind it.
    assert circuit.segments[0].p_kw < 3 * plan.p_mv_kw
    assert circuit.segments[0].p_kw > 3 * plan.p_mv_kw * 0.97


def test_per_segment_independent_cable_selection():
    layout = _layout_one_circuit(n_stations=5, q_inv_kvar=3_000.0)
    (circuit,) = size_circuits(layout, _catalogue())

    far = circuit.segments[-1]
    trunk = circuit.segments[0]
    assert far.selection.cable.name == "AL_95"
    trunk_area = trunk.selection.cable.cross_section_mm2 * trunk.selection.n_parallel
    far_area = far.selection.cable.cross_section_mm2 * far.selection.n_parallel
    assert trunk_area > far_area
    assert far.cable_label.startswith("Al_3x1x95")


def test_mixed_fleet_circuit_sizing():
    # Mixed circuit [9000, 3300, 3300]: the far segment carries the SMALL
    # station only; the trunk carries everything.
    stage1 = _stage1(p_inv_kw=14_500, q_inv_kvar=2_000)
    layout = arrange_plant(
        stage1, [(_tx_9000(), 1), (_tx_3300(), 2)],
        max_circuit_current_a=10_000.0,
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    (circuit,) = size_circuits(layout, _catalogue())

    assert [st.s_rated_kva for st in circuit.stations] == [9000, 3300, 3300]
    assert circuit.stations[0].model == "9000 kVA - BrandA"
    small_plan = layout.circuit_plans[0][-1]
    far = circuit.segments[-1]
    assert far.p_kw == pytest.approx(small_plan.p_mv_kw)
    # Per-circuit power balance with heterogeneous stations.
    p_in = sum(p.p_mv_kw for p in layout.circuit_plans[0])
    p_out = circuit.p_busbar_kw + sum(seg.dp_kw for seg in circuit.segments)
    assert p_out == pytest.approx(p_in, rel=1e-9)


def test_trunk_current_within_cap():
    layout = _layout_one_circuit(n_stations=3)
    (circuit,) = size_circuits(layout, _catalogue())
    assert circuit.i_trunk_a <= layout.max_circuit_current_a
    assert circuit.current_ok


def test_trunk_current_cap_violation_flagged():
    # Force an inconsistent cap after arrangement — flag it, don't crash.
    layout = _layout_one_circuit(n_stations=3)
    layout.max_circuit_current_a = 2.0 * layout.circuit_plans[0][0].i_a
    (circuit,) = size_circuits(layout, _catalogue())
    assert not circuit.current_ok


def test_charging_recorded_but_never_netted():
    layout = _layout_one_circuit(n_stations=3)
    (with_b,) = size_circuits(layout, _catalogue(b_us=120.0))
    (no_b,) = size_circuits(layout, _catalogue(b_us=0.0))

    assert all(seg.q_charging_kvar > 0 for seg in with_b.segments)
    assert all(seg.q_charging_kvar == 0 for seg in no_b.segments)
    assert with_b.q_busbar_kvar == pytest.approx(no_b.q_busbar_kvar)
    assert all(seg.dq_series_kvar >= 0 for seg in with_b.segments)


def test_circuit_power_balance():
    layout = _layout_one_circuit(n_stations=4)
    (circuit,) = size_circuits(layout, _catalogue())
    p_in = sum(p.p_mv_kw for p in layout.circuit_plans[0])
    p_out = circuit.p_busbar_kw + sum(seg.dp_kw for seg in circuit.segments)
    assert p_out == pytest.approx(p_in, rel=1e-9)


def test_all_circuits_sized_and_balanced():
    stage1 = _stage1(p_inv_kw=43_000, q_inv_kvar=9_000)
    layout = arrange_plant(
        stage1, [(_tx_2500(), 18)],
        max_circuit_current_a=380.0,
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    circuits = size_circuits(layout, _catalogue())
    assert [len(c.stations) for c in circuits] == [5, 5, 4, 4]
    assert all(c.current_ok for c in circuits)
    assert circuits[0].i_trunk_a == pytest.approx(circuits[1].i_trunk_a)
    assert circuits[2].i_trunk_a == pytest.approx(circuits[3].i_trunk_a)
    p_injected = sum(p.p_mv_kw for c in layout.circuit_plans for p in c)
    assert sum(c.p_busbar_kw for c in circuits) < p_injected


# --- per-run segment length overrides ---------------------------------------------

def test_segment_length_overrides():
    layout = _layout_one_circuit(n_stations=3)
    (base,) = size_circuits(layout, _catalogue())
    (edited,) = size_circuits(layout, _catalogue(),
                              segment_lengths={(1, 2): 1.2})

    assert edited.segments[0].length_km == pytest.approx(base.segments[0].length_km)
    assert edited.segments[1].length_km == pytest.approx(1.2)
    assert edited.segments[2].length_km == pytest.approx(base.segments[2].length_km)
    assert edited.segments[1].dp_kw > base.segments[1].dp_kw
    assert edited.p_busbar_kw < base.p_busbar_kw


def test_segment_length_override_must_be_positive():
    layout = _layout_one_circuit(n_stations=3)
    with pytest.raises(ValueError):
        size_circuits(layout, _catalogue(), segment_lengths={(1, 1): 0.0})


# --- per-run forced sections ------------------------------------------------------

def test_segment_candidates_force_one_run_and_leave_the_others_auto():
    # The drawing can pin a section on a single run (the engineer knows what is
    # already trenched there); every other run still auto-sizes.
    layout = _layout_one_circuit(n_stations=5, q_inv_kvar=3_000.0)
    (base,) = size_circuits(layout, _catalogue())
    assert base.segments[-1].selection.cable.name == "AL_95"  # auto pick

    big = [c for c in _catalogue() if c.name == "AL_400"]
    (forced,) = size_circuits(layout, _catalogue(), segment_candidates={(1, 5): big})

    assert forced.segments[-1].selection.cable.name == "AL_400"
    assert forced.segments[-1].dp_kw < base.segments[-1].dp_kw  # fatter section
    for k in range(4):  # untouched runs keep their automatic picks
        assert forced.segments[k].cable_label == base.segments[k].cable_label


def test_forced_section_reaches_size_architecture():
    stage1, layout = _full_plant_inputs()
    big = [c for c in _catalogue() if c.name == "AL_400"]
    arch = size_architecture(layout, stage1, _catalogue(),
                             segment_candidates={(1, 5): big})
    assert arch.circuits[0].segments[-1].selection.cable.name == "AL_400"
    assert arch.circuits[1].segments[-1].selection.cable.name == "AL_95"
    assert arch.power_balance_ok


def test_forced_section_that_cannot_carry_the_flow_raises():
    # A forced section is never silently replaced: when it cannot carry the
    # flow, select_cable's descriptive error propagates (the backend turns it
    # into an edge-scoped issue on the drawing).
    layout = _layout_one_circuit(n_stations=5, q_inv_kvar=3_000.0)
    thin = Cable("AL_50", r_ohm_per_km=0.641, x_ohm_per_km=0.14, b_us_per_km=40.0,
                 cross_section_mm2=50, material="aluminium", rated_current_a=155,
                 rated_voltage_kv=20)
    with pytest.raises(ValueError, match="No cable can carry"):
        size_circuits(layout, _catalogue(), segment_candidates={(1, 1): [thin]},
                      max_parallel=2)


# --- size_architecture ------------------------------------------------------------

def _hv_tx() -> Transformer:
    return Transformer("HV_50MVA", s_rated_kva=50_000, uk_percent=12.5, pk_kw=180.0,
                       p0_kw=30.0, i0_percent=0.3, hv_kv=132, lv_kv=20)


def _hv_catalogue() -> list[Cable]:
    # Synthetic 132 kV export cable to prove the HV wiring before the real
    # catalogue lands (stated backlog item).
    return [
        Cable("AL_630_132kV", r_ohm_per_km=0.06, x_ohm_per_km=0.18, b_us_per_km=40.0,
              cross_section_mm2=630, material="aluminium", rated_current_a=700,
              rated_voltage_kv=132),
    ]


def _full_plant_inputs():
    stage1 = _stage1(p_inv_kw=43_000, q_inv_kvar=9_000)
    layout = arrange_plant(
        stage1, [(_tx_2500(), 18)],
        max_circuit_current_a=380.0,
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    return stage1, layout


def test_architecture_mv_interconnection_no_export():
    stage1, layout = _full_plant_inputs()
    arch = size_architecture(layout, stage1, _catalogue(), aux_p_kw=120.0, aux_q_kvar=40.0)

    assert arch.export is None
    expected_p = sum(c.p_busbar_kw for c in arch.circuits) - 120.0
    assert arch.p_poc_delivered_kw == pytest.approx(expected_p)
    assert arch.power_balance_ok
    assert arch.correction_factor == 1.0
    assert arch.n_circuits == 4


def test_architecture_with_hv_transformer():
    stage1, layout = _full_plant_inputs()
    no_hv = size_architecture(layout, stage1, _catalogue())
    with_hv = size_architecture(layout, stage1, _catalogue(), hv_transformer=_hv_tx())

    assert with_hv.export is not None
    assert with_hv.export.dp_tx_kw > 0
    assert with_hv.p_poc_delivered_kw == pytest.approx(
        no_hv.p_poc_delivered_kw - with_hv.export.dp_tx_kw
    )
    assert with_hv.power_balance_ok


def test_architecture_with_hv_cable_sized():
    stage1, layout = _full_plant_inputs()
    arch = size_architecture(
        layout, stage1, _catalogue(),
        hv_transformer=_hv_tx(),
        hv_cable_candidates=_hv_catalogue(), hv_cable_length_km=5.0,
    )

    export = arch.export
    assert export is not None and export.hv_cable is not None
    assert export.hv_cable_sized
    assert export.v_hv_kv == 132
    assert export.hv_cable.selection is not None
    assert export.hv_cable.dp_kw > 0
    assert export.hv_cable.cable_label.startswith("Al_3x")
    assert arch.power_balance_ok


def test_architecture_hv_cable_catalogue_pending():
    stage1, layout = _full_plant_inputs()
    arch = size_architecture(
        layout, stage1, _catalogue(),
        hv_transformer=_hv_tx(),
        hv_cable_candidates=[], hv_cable_length_km=5.0,
    )

    export = arch.export
    assert export is not None and export.hv_cable is not None
    assert not export.hv_cable_sized
    assert export.hv_cable.selection is None
    assert export.hv_cable.dp_kw == 0.0
    assert "not sized" in export.hv_cable.cable_label
    assert arch.power_balance_ok


def test_architecture_hv_cable_without_voltage_raises():
    stage1, layout = _full_plant_inputs()
    with pytest.raises(ValueError):
        size_architecture(layout, stage1, _catalogue(),
                          hv_cable_candidates=_hv_catalogue(), hv_cable_length_km=5.0)


def test_refined_requirement_never_falls_short():
    # Rule: the refined inverter power must deliver AT OR ABOVE the POC target —
    # overshoot is curtailable, shortfall is not acceptable.
    stage1, layout = _full_plant_inputs()
    probe = size_architecture(layout, stage1, _catalogue(),
                              hv_transformer=_hv_tx(), aux_p_kw=120.0, aux_q_kvar=40.0)
    assert probe.p_poc_delivered_kw < 43_000
    target_kw = probe.p_poc_delivered_kw * 1.01

    arch = size_architecture(
        layout, stage1, _catalogue(),
        hv_transformer=_hv_tx(), aux_p_kw=120.0, aux_q_kvar=40.0,
        p_poc_target_kw=target_kw,
    )
    assert arch.correction_factor > 1.0
    assert arch.s_inv_refined_kva == pytest.approx(
        math.hypot(arch.p_inv_refined_kw, arch.q_inv_refined_kvar)
    )
    assert arch.p_poc_refined_delivered_kw is not None
    assert arch.p_poc_refined_delivered_kw >= target_kw
    assert arch.p_poc_refined_delivered_kw <= target_kw * 1.005


def test_architecture_loss_totals_consistent():
    stage1, layout = _full_plant_inputs()
    arch = size_architecture(
        layout, stage1, _catalogue(),
        hv_transformer=_hv_tx(),
        hv_cable_candidates=_hv_catalogue(), hv_cable_length_km=5.0,
    )
    assert arch.total_active_loss_kw == pytest.approx(
        arch.total_cable_loss_kw + arch.total_transformer_loss_kw
    )
    p_in = sum(st.p_lv_kw for c in arch.circuits for st in c.stations)
    assert p_in == pytest.approx(
        arch.p_poc_delivered_kw + arch.total_active_loss_kw + arch.aux_p_kw, rel=1e-9
    )
    assert arch.all_current_ok


def test_architecture_mixed_fleet_end_to_end():
    # Full pass with a mixed fleet: balance must hold and the refined power
    # must cover the target.
    stage1 = _stage1(p_inv_kw=14_500, q_inv_kvar=2_000)
    layout = arrange_plant(
        stage1, [(_tx_9000(), 1), (_tx_3300(), 2)],
        max_circuit_current_a=500.0,
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    arch = size_architecture(layout, stage1, _catalogue(),
                             auto_hv=True, v_hv_kv=132.0,
                             p_poc_target_kw=14_000.0)
    assert arch.power_balance_ok
    assert arch.export is not None and arch.export.hv_transformer is not None
    assert arch.p_poc_refined_delivered_kw >= 14_000.0


# --- auto_hv_transformer ----------------------------------------------------------

def test_auto_hv_transformer_picks_smallest_covering_rating():
    from powertool import auto_hv_transformer

    tx = auto_hv_transformer(43_500, v_hv_kv=132, v_mv_kv=20)
    assert tx.s_rated_kva == 50_000
    assert tx.hv_kv == 132 and tx.lv_kv == 20
    assert tx.pk_kw == pytest.approx(0.0036 * 50_000)
    assert tx.p0_kw == pytest.approx(0.0006 * 50_000)
    assert tx.uk_percent == 12.5

    exact = auto_hv_transformer(50_000, v_hv_kv=132, v_mv_kv=20)
    assert exact.s_rated_kva == 50_000

    with pytest.raises(ValueError):
        auto_hv_transformer(300_000, v_hv_kv=220, v_mv_kv=33)
    with pytest.raises(ValueError):
        auto_hv_transformer(0, v_hv_kv=132, v_mv_kv=20)


def test_size_architecture_auto_hv():
    stage1, layout = _full_plant_inputs()
    arch = size_architecture(layout, stage1, _catalogue(),
                             auto_hv=True, v_hv_kv=132.0)

    export = arch.export
    assert export is not None and export.hv_transformer is not None
    assert export.hv_n_parallel == 1
    assert export.hv_transformer.s_rated_kva >= export.s_tx_through_kva
    assert export.hv_transformer.hv_kv == 132.0
    assert "(auto)" in export.hv_transformer.name
    assert arch.power_balance_ok


def test_size_architecture_auto_hv_requires_voltage():
    stage1, layout = _full_plant_inputs()
    with pytest.raises(ValueError):
        size_architecture(layout, stage1, _catalogue(), auto_hv=True)


# --- size_plant: per-branch refinement (ticket 05) ---------------------------------

def _two_branch_plant(target_multiplier_a: float, target_multiplier_b: float):
    """Two branches under one shared HV transformer with deliberately DIFFERENT
    loss profiles: branch A is a short, lightly-loaded PV-style circuit;
    branch B has a much longer MV run and a heavier aux load, so its own
    correction has to work harder to reach its own target — exactly the
    scenario ticket 05's per-branch closure exists for.
    """
    stage1_a = _stage1(p_inv_kw=14_500, q_inv_kvar=2_000)
    layout_a = arrange_plant(
        stage1_a, [(_tx_2500(), 3)],
        max_circuit_current_a=10_000.0,
        trunk_length_km=0.5, spacing_km=0.2, v_mv_kv=20.0, kind="pv",
    )
    branch_a = size_branch(layout_a, _catalogue(), aux_p_kw=50.0, aux_q_kvar=10.0)

    stage1_b = _stage1(p_inv_kw=6_500, q_inv_kvar=1_000)
    layout_b = arrange_plant(
        stage1_b, [(_tx_2500(), 2)],
        max_circuit_current_a=10_000.0,
        trunk_length_km=3.0, spacing_km=1.5, v_mv_kv=20.0, kind="bess",
    )
    branch_b = size_branch(layout_b, _catalogue(), aux_p_kw=200.0, aux_q_kvar=40.0)

    branches = [branch_a, branch_b]
    stage1s = [stage1_a, stage1_b]

    # Unrefined pass to learn each branch's own delivered figure, then set
    # each branch's target a different amount above it.
    probe = size_plant(branches, stage1s, hv_transformer=_hv_tx())
    delivered_a = probe.branch_refinements[0].p_poc_delivered_kw
    delivered_b = probe.branch_refinements[1].p_poc_delivered_kw
    targets = [delivered_a * target_multiplier_a, delivered_b * target_multiplier_b]

    return branches, stage1s, targets


def test_two_branch_refinement_meets_each_branchs_own_target_with_different_corrections():
    branches, stage1s, targets = _two_branch_plant(1.005, 1.03)

    plant = size_plant(branches, stage1s, hv_transformer=_hv_tx(),
                       p_poc_targets_kw=targets)

    assert len(plant.branch_refinements) == 2
    for refinement, target in zip(plant.branch_refinements, targets):
        assert refinement.p_poc_target_kw == pytest.approx(target)
        assert refinement.p_poc_refined_delivered_kw is not None
        assert refinement.p_poc_refined_delivered_kw >= target

    # The whole point of the per-branch closure: two differently-loaded
    # branches driven to two different targets end up with two different
    # correction scalars, not one shared plant-wide number.
    factor_a = plant.branch_refinements[0].correction_factor
    factor_b = plant.branch_refinements[1].correction_factor
    assert factor_a != pytest.approx(factor_b)
    assert plant.power_balance_ok


def test_single_branch_size_plant_matches_the_size_architecture_shim():
    # The shim (size_architecture) wraps its one branch and one Stage-1 result
    # into the list-shaped size_plant call; calling size_plant directly with
    # that same single branch must produce IDENTICAL numbers, proving the
    # single-fleet compatibility properties delegate correctly.
    stage1, layout = _full_plant_inputs()
    branch = size_branch(layout, _catalogue(), aux_p_kw=120.0, aux_q_kvar=40.0)

    direct = size_plant([branch], [stage1], hv_transformer=_hv_tx(),
                        p_poc_targets_kw=[43_000.0])
    shim = size_architecture(
        layout, stage1, _catalogue(), hv_transformer=_hv_tx(),
        aux_p_kw=120.0, aux_q_kvar=40.0, p_poc_target_kw=43_000.0,
    )

    assert direct.p_poc_delivered_kw == shim.p_poc_delivered_kw
    assert direct.q_poc_delivered_kvar == shim.q_poc_delivered_kvar
    assert direct.correction_factor == shim.correction_factor
    assert direct.p_inv_refined_kw == shim.p_inv_refined_kw
    assert direct.q_inv_refined_kvar == shim.q_inv_refined_kvar
    assert direct.s_inv_refined_kva == shim.s_inv_refined_kva
    assert direct.p_poc_refined_delivered_kw == shim.p_poc_refined_delivered_kw
    assert direct.power_balance_ok == shim.power_balance_ok
    assert shim.correction_factor > 1.0


def test_size_plant_raises_on_non_convergence(monkeypatch):
    # Force non-convergence by lowering the cap rather than inventing a
    # pathological plant: a single pass at the seeded correction under-
    # delivers (loss growth is super-linear), so a 1-iteration cap can never
    # close a real overshoot.
    stage1, layout = _full_plant_inputs()
    branch = size_branch(layout, _catalogue(), aux_p_kw=120.0, aux_q_kvar=40.0)
    monkeypatch.setattr(architecture, "_MAX_REFINE_ITERATIONS", 1)

    with pytest.raises(ValueError, match=r"did not converge within 1 iterations"):
        size_plant([branch], [stage1], hv_transformer=_hv_tx(),
                   p_poc_targets_kw=[60_000.0])


# --- arrange_plant_manual: fleet kind ------------------------------------------------

def test_manual_arrangement_kind_flows_through_to_station_result():
    stage1 = _stage1(p_inv_kw=6_500, q_inv_kvar=1_000)
    layout = arrange_plant_manual(
        stage1, [[_tx_2500(), _tx_2500()]],
        max_circuit_current_a=10_000.0, v_mv_kv=20.0, kind="bess",
    )
    assert all(p.kind == "bess" for c in layout.circuit_plans for p in c)

    branch = size_branch(layout, _catalogue(), segment_lengths=_lengths_of(layout))
    assert all(st.kind == "bess" for c in branch.circuits for st in c.stations)
