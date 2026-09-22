"""Tests for the plant architecture (Stage 2) and the mixed transformer fleet.

Rules: the station fleet (models + counts) comes from Stage 1 and runs at
uniform per-unit loading (each station's share is proportional to its rating);
stations are grouped into MV circuits respecting each station's own
switchgear rated current (ADR-0006), with the current computed from the
actual MV-side power (LV share minus the station transformer's own losses),
never from the nameplate; within a circuit the biggest stations sit nearest
the substation.
"""

import math
from dataclasses import replace

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
    BusbarSection,
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


def _tx_2500(rmu_rated_current_a: float | None = None) -> Transformer:
    # Representative 2500 kVA 20/0.8 kV station transformer. An explicit
    # switchgear rating lets a test reproduce a specific circuit split
    # (ADR-0006); omitted, it falls back to DEFAULT_SWITCHGEAR_RATED_CURRENT_A.
    # A published 2 x 400 mm^2 cable entry keeps this fixture's existing
    # cable-selection tests exercising cross-sections above the engine's
    # 2 x 300 mm^2 fallback (ADR-0007) — the cable-entry FALLBACK itself has
    # its own dedicated tests using a station that publishes none.
    return Transformer("TX_2500", s_rated_kva_at_40c=2500, uk_percent=6.0, pk_kw=24.0,
                       p0_kw=2.5, i0_percent=0.8, hv_kv=20, lv_kv=0.8,
                       rmu_rated_current_a=rmu_rated_current_a,
                       cable_entry_cables_per_phase=2,
                       cable_entry_max_cross_section_mm2=400)


def _tx_9000() -> Transformer:
    # A big PV station, parameters per the project's design assumptions.
    return Transformer("TX_9000", s_rated_kva_at_40c=9000, uk_percent=8.0, pk_kw=90.0,
                       p0_kw=9.0, i0_percent=0.0, lv_kv=0.8, brand="BrandA",
                       cable_entry_cables_per_phase=2,
                       cable_entry_max_cross_section_mm2=400)


def _tx_3300() -> Transformer:
    return Transformer("TX_3300", s_rated_kva_at_40c=3300, uk_percent=8.0, pk_kw=33.0,
                       p0_kw=3.3, i0_percent=0.0, lv_kv=0.8, brand="BrandB",
                       cable_entry_cables_per_phase=2,
                       cable_entry_max_cross_section_mm2=400)


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
    bad = Transformer("BAD", s_rated_kva_at_40c=100, uk_percent=50.0, pk_kw=40.0, p0_kw=80.0)
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
#
# assign_circuits takes a per-station rating list, not a scalar cap (ADR-0006):
# a circuit is admitted only when every position's accumulated current stays
# within the MINIMUM switchgear rating among the stations already placed in
# it. Identical ratings reproduce the old scalar-cap arithmetic exactly.

def test_assign_worked_example_18_capped_at_5():
    # 18 identical stations, 380 A rating each at 70 A each -> balanced 5+5+4+4.
    bins = assign_circuits([70.0] * 18, [380.0] * 18)
    assert sorted((len(b) for b in bins), reverse=True) == [5, 5, 4, 4]
    assert sorted(i for b in bins for i in b) == list(range(18))


def test_assign_even_split():
    assert [len(b) for b in assign_circuits([70.0] * 15, [380.0] * 15)] == [5, 5, 5]


def test_assign_single_circuit_when_cap_allows():
    assert [len(b) for b in assign_circuits([10.0] * 6, [1000.0] * 6)] == [6]


def test_assign_one_station():
    assert assign_circuits([70.0], [380.0]) == [[0]]


def test_assign_station_exceeds_cap_raises():
    # A station's OWN current alone above its OWN rating raises immediately.
    with pytest.raises(ValueError, match="switchgear rated current"):
        assign_circuits([100.0] * 4, [50.0] * 4)


def test_assign_exact_cap_boundary():
    # Rating exactly 5x the station current must allow 5 per circuit.
    assert [len(b) for b in assign_circuits([76.0] * 10, [380.0] * 10)] == [5, 5]


def test_assign_mixed_currents_respect_cap():
    currents = [300.0, 300.0, 100.0, 100.0, 100.0, 100.0]
    ratings = [400.0] * 6
    bins = assign_circuits(currents, ratings)
    assert len(bins) == 3  # lower bound: 1000/400 -> 3 circuits
    for b in bins:
        assert sum(currents[i] for i in b) <= 400.0 + 1e-9
    assert sorted(i for b in bins for i in b) == list(range(6))


def test_assign_invariants():
    for n in (1, 2, 7, 18, 23, 40):
        bins = assign_circuits([70.0] * n, [380.0] * n)
        sizes = [len(b) for b in bins]
        assert sum(sizes) == n
        assert max(sizes) - min(sizes) <= 1  # identical stations stay balanced
        assert max(sizes) <= math.floor(380.0 / 70.0)


def test_assign_ratings_length_must_match_stations():
    with pytest.raises(ValueError):
        assign_circuits([70.0, 70.0], [380.0])


def test_assign_circuit_ceiling_is_the_minimum_rating_of_its_own_stations():
    # A low-rated station constrains the WHOLE circuit it lands in, not just
    # its own position: a 630 A and a 150 A station (both individually within
    # their own rating) cannot share a circuit once their combined current
    # exceeds 150 A, even though the 630 A station alone would allow much more.
    currents = [100.0, 100.0]
    ratings = [630.0, 150.0]
    bins = assign_circuits(currents, ratings)
    assert sorted(len(b) for b in bins) == [1, 1]  # forced into separate circuits


def test_assign_mixed_ratings_pack_together_within_the_lower_ceiling():
    # Two 100 A stations rated 630 A each pack onto one circuit with a third,
    # lower-rated 150 A station at 40 A, since 100+100+40 = 240 <= 150 is
    # false — so the 150 A station must end up alone or with enough headroom.
    # Here it fits alongside ONE 100 A station (140 <= 150) but not both.
    currents = [100.0, 100.0, 40.0]
    ratings = [630.0, 630.0, 150.0]
    bins = assign_circuits(currents, ratings)
    for b in bins:
        assert sum(currents[i] for i in b) <= min(ratings[i] for i in b) + 1e-9


# --- arrange_plant ----------------------------------------------------------------

def test_arrange_plant_45mw_example():
    # 18 x 2500 kVA from Stage 1; per-station MV current ~69 A, so a 380 A
    # switchgear rating gives at most 5 per circuit -> 4 circuits, 5+5+4+4.
    stage1 = _stage1(p_inv_kw=43_000, q_inv_kvar=9_000)
    layout = arrange_plant(
        stage1, [(_tx_2500(rmu_rated_current_a=380.0), 18)],
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
    # Every circuit respects each station's own switchgear rated current.
    for circuit in layout.circuit_plans:
        assert sum(p.i_a for p in circuit) <= 380.0 + 1e-9


def test_arrange_mixed_fleet_shares_and_ordering():
    # 1x9000 + 2x3300: shares proportional to rating, biggest nearest the
    # substation (position 0) in its circuit. Default (unpublished) 630 A
    # switchgear rating comfortably covers this fleet's combined current, so
    # it all lands on one circuit without any override needed.
    stage1 = _stage1(p_inv_kw=14_500, q_inv_kvar=2_000)
    layout = arrange_plant(
        stage1, [(_tx_3300(), 2), (_tx_9000(), 1)],  # order given must not matter
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    assert layout.n_transformers == 3
    assert layout.n_circuits == 1
    plans = layout.circuit_plans[0]
    assert [p.transformer.s_rated_kva_at_40c for p in plans] == [9000, 3300, 3300]
    big, small = plans[0], plans[1]
    assert big.p_lv_kw / small.p_lv_kw == pytest.approx(9000 / 3300)
    assert big.loading == pytest.approx(small.loading)  # uniform per-unit loading
    assert big.loading == pytest.approx(stage1.s_inv_kva / 15_600)


def test_arrange_loading_flag():
    stage1 = _stage1(p_inv_kw=20_000, q_inv_kvar=0.0)  # 20 MVA on 15.6 MVA fleet
    layout = arrange_plant(
        stage1, [(_tx_9000(), 1), (_tx_3300(), 2)],
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    assert layout.fleet_loading > 1.0
    assert not layout.loading_ok


def test_arrange_plant_invalid_inputs():
    stage1 = _stage1(43_000, 9_000)
    with pytest.raises(ValueError):
        arrange_plant(stage1, [(_tx_2500(), 18)],
                      trunk_length_km=-1.0, spacing_km=0.35, v_mv_kv=20.0)
    with pytest.raises(ValueError):
        arrange_plant(stage1, [],
                      trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0)


# --- Stage-1 busbar opening (ADR-0007, ticket 06) ---------------------------------

def test_arrange_plant_one_busbar_fits_stays_one_group():
    # 45 MW reference plant (4 circuits, well under the 12-feeder default and
    # nowhere near 4000 A): unchanged from before this ticket, one busbar.
    stage1 = _stage1(p_inv_kw=43_000, q_inv_kvar=9_000)
    layout = arrange_plant(
        stage1, [(_tx_2500(rmu_rated_current_a=380.0), 18)],
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    assert layout.busbar_groups == [[0, 1, 2, 3]]
    assert layout.n_busbars == 1


def test_arrange_plant_thirteen_circuits_at_the_default_limit_opens_a_second_busbar():
    # 13 stations, each forced into its own circuit (a 40 A switchgear rating
    # admits one ~34.4 A station but not two): the default 12-feeder limit
    # (well below the 4000 A cap here) splits the 13th circuit onto a second
    # busbar, 12 + 1, without reordering any circuit.
    stage1 = _stage1(p_inv_kw=13 * 1_200, q_inv_kvar=0.0)
    layout = arrange_plant(
        stage1, [(_tx_2500(rmu_rated_current_a=40.0), 13)],
        trunk_length_km=0.5, spacing_km=0.2, v_mv_kv=20.0,
    )
    assert layout.circuit_sizes == [1] * 13
    assert layout.busbar_groups == [list(range(12)), [12]]
    assert layout.n_busbars == 2


def test_arrange_plant_feeders_per_busbar_setting_is_honoured():
    # Same 13-single-station-circuit plant, but with the limit lowered to 5:
    # three busbars (5 + 5 + 3), proving the split follows the SETTING, not a
    # hard-coded 12.
    stage1 = _stage1(p_inv_kw=13 * 1_200, q_inv_kvar=0.0)
    layout = arrange_plant(
        stage1, [(_tx_2500(rmu_rated_current_a=40.0), 13)],
        trunk_length_km=0.5, spacing_km=0.2, v_mv_kv=20.0,
        feeders_per_busbar=5,
    )
    assert layout.busbar_groups == [
        [0, 1, 2, 3, 4], [5, 6, 7, 8, 9], [10, 11, 12],
    ]


def test_arrange_plant_busbar_total_above_4000a_opens_a_second_busbar_regardless_of_feeder_count():
    # Two stations, each forced into its own circuit by a 2200 A switchgear
    # ceiling (one station's own ~2191 A fits, two combined would not), each
    # circuit near 2191 A: together they would put a single busbar at
    # ~4383 A, above the 4000 A ladder top, even though only 2 of the
    # default 12 feeder slots would be used.
    tx = Transformer("BIG", s_rated_kva_at_40c=76_000, uk_percent=8.0, pk_kw=304.0,
                     p0_kw=45.0, i0_percent=0.3, lv_kv=0.8,
                     rmu_rated_current_a=2200.0)
    stage1 = _stage1(p_inv_kw=152_000.0, q_inv_kvar=0.0)
    layout = arrange_plant(
        stage1, [(tx, 2)],
        trunk_length_km=0.5, spacing_km=0.2, v_mv_kv=20.0,
    )
    assert layout.circuit_sizes == [1, 1]
    single_busbar_a = current_a(
        math.hypot(sum(p.p_mv_kw for c in layout.circuit_plans for p in c),
                   sum(p.q_mv_kvar for c in layout.circuit_plans for p in c)),
        20.0,
    )
    assert single_busbar_a > 4000.0
    assert layout.busbar_groups == [[0], [1]]
    assert layout.n_busbars == 2


def test_arrange_plant_manual_never_splits_into_more_than_one_busbar_group():
    # A drawn diagram's busbars come from the diagram itself (validated at a
    # higher layer, ticket 05); arrange_plant_manual's own layout is always
    # one group, whatever it is handed — 13 circuits included.
    stage1 = _stage1(p_inv_kw=13 * 1_200, q_inv_kvar=0.0)
    tx = _tx_2500(rmu_rated_current_a=40.0)
    circuits = [[tx] for _ in range(13)]
    layout = arrange_plant_manual(stage1, circuits, v_mv_kv=20.0)
    assert layout.busbar_groups == [list(range(13))]
    assert layout.n_busbars == 1


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
        stage1, _as_drawn(auto), v_mv_kv=auto.v_mv_kv,
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

    manual_refinement = manual_arch.branch_refinements[0]
    auto_refinement = auto_arch.branch_refinements[0]
    assert manual_arch.p_poc_delivered_kw == auto_arch.p_poc_delivered_kw
    assert manual_arch.q_poc_delivered_kvar == auto_arch.q_poc_delivered_kvar
    assert manual_refinement.correction_factor == auto_refinement.correction_factor
    assert manual_refinement.s_inv_refined_kva == auto_refinement.s_inv_refined_kva
    assert manual_arch.total_active_loss_kw == auto_arch.total_active_loss_kw
    for got, expected in zip(manual_arch.branches[0].circuits, auto_arch.branches[0].circuits):
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
    layout = arrange_plant_manual(stage1, drawn, v_mv_kv=20.0)

    assert layout.circuit_sizes == [1, 2]
    assert [[p.transformer.s_rated_kva_at_40c for p in c] for c in layout.circuit_plans] == \
           [[3300], [3300, 9000]]
    # Same fleet, auto-arranged: one circuit, biggest station nearest the busbar.
    auto = arrange_plant(stage1, [(_tx_3300(), 2), (_tx_9000(), 1)],
                         trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0)
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
        v_mv_kv=20.0,
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


def test_manual_arrangement_accepts_a_drawing_over_a_stations_switchgear_rating():
    # The user drew it: architecture.py never refuses to solve a circuit whose
    # THROUGH current exceeds a station's own switchgear rating — that
    # judgment is powertool.graph's ``switchgear_through_current_exceeded``
    # warning, not architecture's own. It always reports the number.
    tx_big = replace(_tx_9000(), rmu_rated_current_a=350.0)
    tx_small = replace(_tx_3300(), rmu_rated_current_a=350.0)
    stage1 = _stage1(p_inv_kw=14_500, q_inv_kvar=2_000)
    layout = arrange_plant_manual(stage1, [[tx_big, tx_small]], v_mv_kv=20.0)
    (circuit,) = size_circuits(layout, _catalogue(),
                               segment_lengths=_lengths_of(layout))
    # Each station is within its OWN current alone...
    assert layout.circuit_plans[0][0].i_a < 350.0
    assert layout.circuit_plans[0][1].i_a < 350.0
    # ...but the near station's THROUGH current (both, combined) is not.
    assert circuit.stations[0].through_current_a > 350.0
    assert circuit.i_trunk_a == pytest.approx(circuit.stations[0].through_current_a)


def test_manual_arrangement_needs_stations():
    stage1 = _stage1(43_000, 9_000)
    with pytest.raises(ValueError):
        arrange_plant_manual(stage1, [], v_mv_kv=20.0)
    with pytest.raises(ValueError):
        arrange_plant_manual(stage1, [[_tx_2500()], []], v_mv_kv=20.0)


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
    # n identical 2500 kVA stations in a single circuit: the default
    # (unpublished) 630 A switchgear rating comfortably covers a handful of
    # ~70 A stations, so they all land on one circuit.
    stage1 = _stage1(p_inv_kw=2_400.0 * n_stations, q_inv_kvar=q_inv_kvar)
    return arrange_plant(
        stage1, [(_tx_2500(), n_stations)],
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


def test_trunk_current_within_switchgear_rating():
    layout = _layout_one_circuit(n_stations=3)
    (circuit,) = size_circuits(layout, _catalogue())
    rating = layout.circuit_plans[0][0].transformer.switchgear_rated_current_a
    assert circuit.i_trunk_a <= rating


def test_through_current_reads_the_accumulated_segment_walk_not_a_second_computation():
    layout = _layout_one_circuit(n_stations=3)
    (circuit,) = size_circuits(layout, _catalogue())
    # Position 1 is nearest the substation: its through current is its own
    # plus every station downstream of it, i.e. exactly the trunk current.
    assert circuit.stations[0].through_current_a == pytest.approx(circuit.i_trunk_a)
    # The far station's through current is just its own.
    assert circuit.stations[-1].through_current_a == pytest.approx(
        layout.circuit_plans[0][-1].i_a)
    # Every station's through current is current_a() of the SAME s_kva already
    # stored on its own segment — proof this reads the walk, not a second one.
    for station, segment in zip(circuit.stations, circuit.segments):
        assert station.through_current_a == pytest.approx(
            current_a(segment.s_kva, layout.v_mv_kv))


# --- Cable entry bounds circuit cables (ADR-0007) ---------------------------


def test_segment_bound_is_the_stricter_of_its_two_ends():
    # Station 1 (near the busbar) publishes a generous cable entry; station 2
    # (far) publishes a tight one. The far segment (station 2 to station 1)
    # must respect station 2's tighter bound even though station 1's is wide.
    near = Transformer("NEAR", s_rated_kva_at_40c=9000, uk_percent=8.0, pk_kw=90.0,
                       p0_kw=9.0, i0_percent=0.0, lv_kv=0.8, rmu_rated_current_a=2000.0,
                       cable_entry_cables_per_phase=3, cable_entry_max_cross_section_mm2=500.0)
    far_tx = Transformer("FAR", s_rated_kva_at_40c=3300, uk_percent=8.0, pk_kw=33.0,
                         p0_kw=3.3, i0_percent=0.0, lv_kv=0.8, rmu_rated_current_a=2000.0,
                         cable_entry_cables_per_phase=1, cable_entry_max_cross_section_mm2=150.0)
    stage1 = _stage1(p_inv_kw=8_000.0, q_inv_kvar=1_500.0)
    layout = arrange_plant_manual(stage1, [[near, far_tx]], v_mv_kv=20.0)
    (circuit,) = size_circuits(
        layout, _catalogue(), segment_lengths={(1, 1): 0.8, (1, 2): 0.35})

    far_segment = circuit.segments[-1]  # station 2 (FAR) to station 1 (NEAR)
    assert far_segment.selection is not None
    assert far_segment.selection.n_parallel <= 1  # FAR's own limit, not NEAR's 3
    assert far_segment.selection.cable.cross_section_mm2 <= 150  # FAR's own cap


def test_segment_with_no_admissible_cable_is_flagged_not_raised():
    # Two stations whose own current is comfortably within their own cable
    # entry, but whose SUM (the trunk's cumulative current) is not — the
    # trunk is recorded unsized and the circuit still solves (ADR-0007);
    # this is deliberately NOT the own-current hard error below.
    tx = Transformer("MID", s_rated_kva_at_40c=9000, uk_percent=8.0, pk_kw=90.0,
                     p0_kw=9.0, i0_percent=0.0, lv_kv=0.8, rmu_rated_current_a=2000.0)
    stage1 = _stage1(p_inv_kw=16_000.0, q_inv_kvar=0.0)
    layout = arrange_plant_manual(stage1, [[tx, tx]], v_mv_kv=20.0)
    for plan in layout.circuit_plans[0]:
        assert plan.i_a < 300.0  # comfortably under the fallback's ~376 A ceiling

    (circuit,) = size_circuits(layout, _catalogue())

    trunk = circuit.segments[0]
    assert trunk.selection is None
    assert "cable entry" in trunk.cable_label
    assert trunk.dp_kw == 0.0
    far_segment = circuit.segments[-1]
    assert far_segment.selection is not None  # only the trunk is flagged


def test_station_over_own_switchgear_rating_raises_at_auto_arrangement():
    # assign_circuits screens this before any circuit is even formed
    # (ADR-0006): a station whose OWN current alone exceeds its OWN
    # switchgear rated current is a hard error, the catalogue entry is
    # self-contradictory.
    tx = replace(_tx_2500(), rmu_rated_current_a=50.0)  # far below its own MV current
    stage1 = _stage1(p_inv_kw=2_400.0, q_inv_kvar=500.0)
    with pytest.raises(ValueError, match="switchgear rated current"):
        arrange_plant(stage1, [(tx, 1)],
                      trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0)


def test_station_over_own_switchgear_rating_raises_before_any_cable_is_sized():
    # A DRAWN plant skips assign_circuits entirely (arrange_plant_manual keeps
    # the drawn order verbatim, see its own docstring), so size_circuits is
    # the last line of defense for the same hard error.
    tx = replace(_tx_2500(), rmu_rated_current_a=50.0)  # far below its own MV current
    stage1 = _stage1(p_inv_kw=2_400.0, q_inv_kvar=500.0)
    layout = arrange_plant_manual(stage1, [[tx]], v_mv_kv=20.0)
    with pytest.raises(ValueError, match="switchgear rated current"):
        size_circuits(layout, _catalogue())


def test_station_over_own_cable_entry_raises_at_auto_arrangement():
    # Same standing as the switchgear hard error above, for cable entry
    # (ADR-0007): arrange_plant's cable_candidates path screens a station
    # whose own current alone no cable within its own cable entry can carry,
    # before any circuit is even formed.
    tx = replace(_tx_2500(), cable_entry_cables_per_phase=1,
                 cable_entry_max_cross_section_mm2=50.0)  # no catalogue cable fits
    stage1 = _stage1(p_inv_kw=2_400.0, q_inv_kvar=500.0)
    with pytest.raises(ValueError, match="cable entry"):
        arrange_plant(stage1, [(tx, 1)],
                      trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
                      cable_candidates=_catalogue())


def test_arrange_plant_without_cable_candidates_skips_the_cable_entry_check():
    # cable_candidates is opt-in: omitted (the default), grouping considers
    # switchgear only, unaffected by a station's cable entry — existing
    # callers with no cable catalogue in scope keep today's behaviour.
    tx = replace(_tx_2500(), cable_entry_cables_per_phase=1,
                 cable_entry_max_cross_section_mm2=50.0)
    stage1 = _stage1(p_inv_kw=2_400.0, q_inv_kvar=500.0)
    layout = arrange_plant(stage1, [(tx, 1)],
                           trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0)
    assert layout.circuit_sizes == [1]


def test_station_over_own_cable_entry_raises_before_any_cable_is_sized():
    # A DRAWN plant skips assign_circuits entirely, so size_circuits is the
    # last line of defense for the same hard error (ADR-0007).
    tx = replace(_tx_2500(), cable_entry_cables_per_phase=1,
                 cable_entry_max_cross_section_mm2=50.0)
    stage1 = _stage1(p_inv_kw=2_400.0, q_inv_kvar=500.0)
    layout = arrange_plant_manual(stage1, [[tx]], v_mv_kv=20.0)
    with pytest.raises(ValueError, match="cable entry"):
        size_circuits(layout, _catalogue())


def test_arrange_plant_with_an_empty_cable_catalogue_skips_the_cable_entry_check():
    # An empty (not None) cable_candidates means "no MV cable catalogue for
    # this voltage yet" — a different problem from an inadmissible cable
    # entry, so it must not raise the cable-entry hard error here either.
    tx = replace(_tx_2500(), cable_entry_cables_per_phase=1,
                 cable_entry_max_cross_section_mm2=50.0)
    stage1 = _stage1(p_inv_kw=2_400.0, q_inv_kvar=500.0)
    layout = arrange_plant(stage1, [(tx, 1)],
                           trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
                           cable_candidates=[])
    assert layout.circuit_sizes == [1]


def test_size_circuits_with_an_empty_cable_catalogue_raises_the_existing_no_cable_error():
    # Same distinction as above at the size_circuits level: an empty
    # catalogue must surface select_cable's own "no usable cables" error, not
    # the cable-entry-specific one — even for a station whose own current
    # would otherwise trip the cable-entry hard error.
    tx = replace(_tx_2500(), cable_entry_cables_per_phase=1,
                 cable_entry_max_cross_section_mm2=50.0)
    stage1 = _stage1(p_inv_kw=2_400.0, q_inv_kvar=500.0)
    layout = arrange_plant_manual(stage1, [[tx]], v_mv_kv=20.0)
    with pytest.raises(ValueError, match="No usable cables in the catalogue"):
        size_circuits(layout, [])


def test_cable_candidates_narrows_stage1_grouping_to_admissible_circuits():
    # Two identical stations whose own current comfortably fits their own
    # switchgear (2000 A, generous) but whose SUM exceeds what the fallback
    # cable entry (2 x 300 mm^2, ~376 A here with only AL_95 <= 300 mm^2 in
    # this catalogue) can carry: switchgear-only grouping packs them into one
    # circuit; cable-entry-aware grouping must split them (ADR-0007's
    # "Stage-1 grouping only forms circuits in which every segment has an
    # admissible cable").
    tx = Transformer("BIG", s_rated_kva_at_40c=9000, uk_percent=8.0, pk_kw=90.0,
                     p0_kw=9.0, i0_percent=0.0, lv_kv=0.8, rmu_rated_current_a=2000.0)
    stage1 = _stage1(p_inv_kw=16_000.0, q_inv_kvar=0.0)

    switchgear_only = arrange_plant(stage1, [(tx, 2)],
                                    trunk_length_km=0.5, spacing_km=0.2, v_mv_kv=20.0)
    assert switchgear_only.circuit_sizes == [2]

    cable_aware = arrange_plant(stage1, [(tx, 2)],
                                trunk_length_km=0.5, spacing_km=0.2, v_mv_kv=20.0,
                                cable_candidates=_catalogue())
    assert cable_aware.circuit_sizes == [1, 1]


def test_stage1_grouping_ceiling_also_respects_the_fixed_busbar_end():
    # A station publishing a GENEROUS cable entry (4 x 630 mm^2) still gets
    # grouped against the busbar-end ceiling: the trunk's other end is always
    # the busbar, which has no station to publish a figure and so always
    # falls back to 2 x 300 mm^2 (ADR-0007) — a station's own wide entry
    # cannot widen that. Two such stations sum past the fallback's ~376 A
    # ceiling (only AL_95 <= 300 mm^2 in this catalogue) even though each
    # station's OWN entry would allow far more.
    tx = Transformer("BIG", s_rated_kva_at_40c=9000, uk_percent=8.0, pk_kw=90.0,
                     p0_kw=9.0, i0_percent=0.0, lv_kv=0.8, rmu_rated_current_a=2000.0,
                     cable_entry_cables_per_phase=4, cable_entry_max_cross_section_mm2=630.0)
    stage1 = _stage1(p_inv_kw=16_000.0, q_inv_kvar=0.0)

    layout = arrange_plant(stage1, [(tx, 2)],
                           trunk_length_km=0.5, spacing_km=0.2, v_mv_kv=20.0,
                           cable_candidates=_catalogue())
    assert layout.circuit_sizes == [1, 1]


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
        stage1, [(_tx_2500(rmu_rated_current_a=380.0), 18)],
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    circuits = size_circuits(layout, _catalogue())
    assert [len(c.stations) for c in circuits] == [5, 5, 4, 4]
    assert all(c.i_trunk_a <= 380.0 + 1e-9 for c in circuits)
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
    assert arch.branches[0].circuits[0].segments[-1].selection.cable.name == "AL_400"
    assert arch.branches[0].circuits[1].segments[-1].selection.cable.name == "AL_95"
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
    return Transformer("HV_50MVA", s_rated_kva_at_40c=50_000, uk_percent=12.5, pk_kw=180.0,
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
    # 380 A switchgear rating gives the same 5+5+4+4 split as the golden
    # 45 MW example (see test_arrange_plant_45mw_example).
    stage1 = _stage1(p_inv_kw=43_000, q_inv_kvar=9_000)
    layout = arrange_plant(
        stage1, [(_tx_2500(rmu_rated_current_a=380.0), 18)],
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    return stage1, layout


def test_architecture_mv_interconnection_no_export():
    stage1, layout = _full_plant_inputs()
    arch = size_architecture(layout, stage1, _catalogue(), aux_p_kw=120.0, aux_q_kvar=40.0)

    assert arch.export is None
    expected_p = sum(c.p_busbar_kw for c in arch.branches[0].circuits) - 120.0
    assert arch.p_poc_delivered_kw == pytest.approx(expected_p)
    assert arch.power_balance_ok
    assert arch.branch_refinements[0].correction_factor == 1.0
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
    refinement = arch.branch_refinements[0]
    assert refinement.correction_factor > 1.0
    assert refinement.s_inv_refined_kva == pytest.approx(
        math.hypot(refinement.p_inv_refined_kw, refinement.q_inv_refined_kvar)
    )
    assert refinement.p_poc_refined_delivered_kw is not None
    assert refinement.p_poc_refined_delivered_kw >= target_kw
    assert refinement.p_poc_refined_delivered_kw <= target_kw * 1.005


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
    p_in = sum(st.p_lv_kw for c in arch.branches[0].circuits for st in c.stations)
    assert p_in == pytest.approx(
        arch.p_poc_delivered_kw + arch.total_active_loss_kw + arch.branches[0].aux_p_kw,
        rel=1e-9
    )
    assert arch.all_current_ok


def test_architecture_mixed_fleet_end_to_end():
    # Full pass with a mixed fleet: balance must hold and the refined power
    # must cover the target.
    stage1 = _stage1(p_inv_kw=14_500, q_inv_kvar=2_000)
    layout = arrange_plant(
        stage1, [(replace(_tx_9000(), rmu_rated_current_a=500.0), 1),
                 (replace(_tx_3300(), rmu_rated_current_a=500.0), 2)],
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    arch = size_architecture(layout, stage1, _catalogue(),
                             auto_hv=True, v_hv_kv=132.0,
                             p_poc_target_kw=14_000.0)
    assert arch.power_balance_ok
    assert arch.export is not None and arch.export.hv_transformer is not None
    assert arch.branch_refinements[0].p_poc_refined_delivered_kw >= 14_000.0


# --- auto_hv_transformer ----------------------------------------------------------

def test_auto_hv_transformer_picks_smallest_covering_rating():
    from powertool import auto_hv_transformer

    tx = auto_hv_transformer(43_500, v_hv_kv=132, v_mv_kv=20)
    assert tx.s_rated_kva_at_40c == 50_000
    assert tx.hv_kv == 132 and tx.lv_kv == 20
    assert tx.pk_kw == pytest.approx(0.0036 * 50_000)
    assert tx.p0_kw == pytest.approx(0.0006 * 50_000)
    assert tx.uk_percent == 12.5

    exact = auto_hv_transformer(50_000, v_hv_kv=132, v_mv_kv=20)
    assert exact.s_rated_kva_at_40c == 50_000

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
    assert export.hv_transformer.s_rated_kva_at_40c >= export.s_tx_through_kva
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
        trunk_length_km=0.5, spacing_km=0.2, v_mv_kv=20.0, kind="pv",
    )
    branch_a = size_branch(layout_a, _catalogue(), aux_p_kw=50.0, aux_q_kvar=10.0)

    stage1_b = _stage1(p_inv_kw=6_500, q_inv_kvar=1_000)
    layout_b = arrange_plant(
        stage1_b, [(_tx_2500(), 2)],
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


def test_recompute_operating_point_preserves_complete_branch_details():
    stage1, layout = _full_plant_inputs()
    branch = size_branch(layout, _catalogue(), aux_p_kw=120.0, aux_q_kvar=40.0)

    recomputed = architecture.recompute_branch(branch, stage1, 1.0)
    station = recomputed.circuits[0].stations[0]
    original = branch.circuits[0].stations[0]

    assert station.p_lv_kw == pytest.approx(original.p_lv_kw)
    assert station.q_lv_kvar == pytest.approx(original.q_lv_kvar)
    assert station.s_mv_kva == pytest.approx(original.s_mv_kva)
    assert recomputed.circuits[0].segments[0].p_kw == pytest.approx(
        branch.circuits[0].segments[0].p_kw)
    assert recomputed.circuits[0].segments[0].dp_kw == pytest.approx(
        branch.circuits[0].segments[0].dp_kw)


def test_recompute_operating_point_updates_uniform_loading_and_current():
    stage1, layout = _full_plant_inputs()
    layout = replace(layout, max_loading=0.90)
    # The x1.10 correction below pushes the trunk current just past what
    # AL_95 (the only _catalogue() cable within the fixed 300 mm^2 busbar-end
    # cable entry, ADR-0007) can carry at 2 parallel runs; AL_300 keeps this
    # scenario sized so the assertions below still exercise the recomputed
    # cable-current arithmetic rather than a flagged-unsized segment.
    catalogue = _catalogue() + [
        Cable("AL_300", r_ohm_per_km=0.10, x_ohm_per_km=0.115, b_us_per_km=45.0,
              cross_section_mm2=300, material="aluminium", rated_current_a=300,
              rated_voltage_kv=20),
    ]
    branch = size_branch(layout, catalogue)
    recomputed = architecture.recompute_branch(branch, stage1, 1.10)
    fleet_loading = stage1.s_inv_kva * 1.10 / layout.s_fleet_kva
    station = recomputed.circuits[0].stations[0]
    assert recomputed.layout.fleet_loading == pytest.approx(fleet_loading)
    assert station.loading == pytest.approx(fleet_loading)
    assert recomputed.layout.loading_ok is False
    plan = recomputed.layout.circuit_plans[0][0]
    assert plan.i_a == pytest.approx(current_a(station.s_mv_kva, layout.v_mv_kv))
    selection = recomputed.circuits[0].segments[0].selection
    assert selection is not None
    assert selection.current_per_circuit_a == pytest.approx(
        current_a(recomputed.circuits[0].segments[0].s_kva, layout.v_mv_kv)
        / selection.n_parallel)


def test_refinement_reselects_auto_cable_from_original_catalogue():
    stage1 = _stage1(p_inv_kw=1_000.0, q_inv_kvar=200.0)
    layout = arrange_plant(
        stage1, [(_tx_2500(), 1)],
        trunk_length_km=10.0, spacing_km=0.35, v_mv_kv=20.0,
    )
    # AL_400 (400 mm^2) is now excluded from the trunk regardless of the
    # station's own published cable entry: the busbar end of a circuit's
    # first cable always counts as the engine's 2 x 300 mm^2 cable-entry
    # fallback (ADR-0007), since no busbar switchgear is sized/published yet.
    # AL_300 stands in as the escalation target that still fits.
    catalogue = _catalogue() + [
        Cable("AL_300", r_ohm_per_km=0.10, x_ohm_per_km=0.115, b_us_per_km=45.0,
              cross_section_mm2=300, material="aluminium", rated_current_a=470,
              rated_voltage_kv=20),
    ]
    initial = size_branch(layout, catalogue, max_parallel=1)
    assert initial.circuits[0].segments[0].cable_label == "Al_3x1x95_20kV"

    refined = size_architecture(
        layout, stage1, catalogue, max_parallel=1, p_poc_target_kw=2_200.0,
        q_poc_target_kvar=0.0,
    )
    assert refined.branch_refinements[0].p_poc_delivered_kw == pytest.approx(
        initial.p_busbar_kw
    )
    assert refined.branch_refinements[0].p_poc_refined_delivered_kw >= 2_200.0 - 1e-5
    assert refined.branches[0].circuits[0].segments[0].cable_label == "Al_3x1x300_20kV"


def test_forced_cable_crossing_after_refinement_is_not_swallowed():
    stage1 = _stage1(p_inv_kw=1_000.0, q_inv_kvar=200.0)
    layout = arrange_plant(
        stage1, [(_tx_2500(), 1)],
        trunk_length_km=10.0, spacing_km=0.35, v_mv_kv=20.0,
    )
    cable = _catalogue()[0]
    branch = size_branch(layout, [cable], max_parallel=1,
                         segment_candidates={(1, 1): [cable]})
    with pytest.raises(ValueError, match="No cable can carry"):
        size_plant(
            [branch], [stage1], max_parallel=1, p_poc_targets_kw=[2_200.0],
            q_poc_targets_kvar=[0.0],
        )


def test_single_branch_size_plant_matches_the_size_architecture_shim():
    # The shim (size_architecture) wraps its one branch and one Stage-1 result
    # into the list-shaped size_plant call; calling size_plant directly with
    # that same single branch must produce IDENTICAL numbers.
    stage1, layout = _full_plant_inputs()
    branch = size_branch(layout, _catalogue(), aux_p_kw=120.0, aux_q_kvar=40.0)

    direct = size_plant([branch], [stage1], hv_transformer=_hv_tx(),
                        p_poc_targets_kw=[43_000.0])
    shim = size_architecture(
        layout, stage1, _catalogue(), hv_transformer=_hv_tx(),
        aux_p_kw=120.0, aux_q_kvar=40.0, p_poc_target_kw=43_000.0,
    )
    direct_refinement = direct.branch_refinements[0]
    shim_refinement = shim.branch_refinements[0]

    assert direct.p_poc_delivered_kw == shim.p_poc_delivered_kw
    assert direct.q_poc_delivered_kvar == shim.q_poc_delivered_kvar
    assert direct_refinement.correction_factor == shim_refinement.correction_factor
    assert direct_refinement.p_inv_refined_kw == shim_refinement.p_inv_refined_kw
    assert direct_refinement.q_inv_refined_kvar == shim_refinement.q_inv_refined_kvar
    assert direct_refinement.s_inv_refined_kva == shim_refinement.s_inv_refined_kva
    assert (direct_refinement.p_poc_refined_delivered_kw
            == shim_refinement.p_poc_refined_delivered_kw)
    assert direct.power_balance_ok == shim.power_balance_ok
    assert shim_refinement.correction_factor > 1.0


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
        v_mv_kv=20.0, kind="bess",
    )
    assert all(p.kind == "bess" for c in layout.circuit_plans for p in c)

    branch = size_branch(layout, _catalogue(), segment_lengths=_lengths_of(layout))
    assert all(st.kind == "bess" for c in branch.circuits for st in c.stations)


# --- BusbarSection: several busbars per branch (ticket 05) -------------------

def test_no_sections_argument_builds_one_implicit_section_matching_the_scalar_aux_path():
    stage1, layout = _full_plant_inputs()
    branch = size_branch(layout, _catalogue(), aux_p_kw=120.0, aux_q_kvar=40.0)

    assert len(branch.sections) == 1
    section = branch.sections[0]
    assert section.circuit_indices == [c.index for c in branch.circuits]
    assert (section.aux_p_kw, section.aux_q_kvar) == (120.0, 40.0)
    assert branch.aux_p_kw == pytest.approx(120.0)
    assert branch.aux_q_kvar == pytest.approx(40.0)
    # Byte-identical: the branch-level totals are exactly the sole section's
    # own totals (a sum over one element), the same arithmetic as before this
    # ticket split circuits into sections at all.
    assert branch.p_busbar_kw == section.p_busbar_kw
    assert branch.q_busbar_kvar == section.q_busbar_kvar


def test_splitting_circuits_into_two_sections_isolates_each_sections_own_aux():
    # 4 circuits (indices 1-4); split 1,2 onto busbar "a" and 3,4 onto "b".
    stage1, layout = _full_plant_inputs()
    base = size_branch(
        layout, _catalogue(),
        sections=[
            BusbarSection(busbar_id="a", circuit_indices=[1, 2]),
            BusbarSection(busbar_id="b", circuit_indices=[3, 4]),
        ],
    )
    with_aux_on_b = size_branch(
        layout, _catalogue(),
        sections=[
            BusbarSection(busbar_id="a", circuit_indices=[1, 2]),
            BusbarSection(busbar_id="b", circuit_indices=[3, 4],
                         aux_p_kw=200.0, aux_q_kvar=40.0),
        ],
    )
    section_a_base, section_b_base = base.sections
    section_a_aux, section_b_aux = with_aux_on_b.sections

    # Busbar A's own current is untouched by an aux load drawn on busbar B —
    # size_branch never lets one busbar's aux leak into another's total.
    assert section_a_aux.busbar_current_a == pytest.approx(section_a_base.busbar_current_a)
    assert section_a_aux.p_busbar_kw == pytest.approx(section_a_base.p_busbar_kw)
    # Busbar B's own current absorbs the direct subtraction.
    assert section_b_aux.p_busbar_kw == pytest.approx(section_b_base.p_busbar_kw - 200.0)
    assert section_b_aux.busbar_current_a < section_b_base.busbar_current_a
    # The fleet-level (branch) total still sees the whole 200 kW / 40 kvar.
    assert with_aux_on_b.aux_p_kw == pytest.approx(base.aux_p_kw + 200.0)
    assert with_aux_on_b.aux_q_kvar == pytest.approx(base.aux_q_kvar + 40.0)


def test_each_sections_own_export_cable_is_sized_on_its_own_busbar_total():
    stage1, layout = _full_plant_inputs()
    branch = size_branch(
        layout, _catalogue(),
        sections=[
            BusbarSection(busbar_id="a", circuit_indices=[1, 2],
                         export_edge_id="exp_a", export_length_km=1.0,
                         export_candidates=_catalogue()),
            BusbarSection(busbar_id="b", circuit_indices=[3, 4],
                         export_edge_id="exp_b", export_length_km=3.0,
                         export_candidates=_catalogue()),
        ],
    )
    section_a, section_b = branch.sections
    assert section_a.mv_export is not None and section_b.mv_export is not None
    assert section_a.mv_export.s_kva == pytest.approx(
        math.hypot(section_a.p_busbar_kw, section_a.q_busbar_kvar))
    assert section_b.mv_export.s_kva == pytest.approx(
        math.hypot(section_b.p_busbar_kw, section_b.q_busbar_kvar))
    assert section_a.mv_export.length_km == 1.0
    assert section_b.mv_export.length_km == 3.0
    # Different length AND different circuit membership -> different losses;
    # neither section's export cable was sized on the OTHER's total.
    assert section_a.mv_export.dp_kw != section_b.mv_export.dp_kw


def test_recompute_branch_preserves_the_section_partition():
    stage1, layout = _full_plant_inputs()
    branch = size_branch(
        layout, _catalogue(),
        sections=[
            BusbarSection(busbar_id="a", circuit_indices=[1, 2], aux_p_kw=50.0),
            BusbarSection(busbar_id="b", circuit_indices=[3, 4], aux_p_kw=200.0),
        ],
    )
    recomputed = architecture.recompute_branch(branch, stage1, 1.2)

    assert len(recomputed.sections) == 2
    assert [s.busbar_id for s in recomputed.sections] == ["a", "b"]
    assert [s.circuit_indices for s in recomputed.sections] == [[1, 2], [3, 4]]
    assert [s.aux_p_kw for s in recomputed.sections] == [50.0, 200.0]
