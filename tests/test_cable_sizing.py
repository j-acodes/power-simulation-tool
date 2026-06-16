"""Tests for automatic cable selection.

Rule: number of parallel circuits set by ampacity (fewest circuits for which a
cable fits within max utilization), then the smallest cross-section that also
meets the admissible power-loss budget. Voltage drop is an optional extra cap.
"""

import math

import pytest

from powertool import (
    AutoCable,
    Cable,
    Chain,
    ChainElement,
    select_cable,
    size_pv_inverters,
)
from powertool.cable_sizing import CableSelection


def _catalogue():
    # Two aluminium MV cables: a small and a large cross-section.
    return [
        Cable("AL_240", r_ohm_per_km=0.125, x_ohm_per_km=0.110, b_us_per_km=60.0,
              cross_section_mm2=240, rated_current_a=420, rated_voltage_kv=20),
        Cable("AL_630", r_ohm_per_km=0.0469, x_ohm_per_km=0.098, b_us_per_km=95.0,
              cross_section_mm2=630, rated_current_a=700, rated_voltage_kv=20),
    ]


def test_small_load_single_circuit_smallest_cable():
    # ~5 MVA at 20 kV over 500 m: one circuit, smallest cable, loss well within budget.
    sel = select_cable(_catalogue(), s_kva=5000, v_kv=20, length_km=0.5,
                       cos_phi=1.0, sin_phi=0.0, max_loss_percent=1.30)
    assert sel.n_parallel == 1
    assert sel.cable.name == "AL_240"
    assert sel.utilization < 0.80
    assert sel.loss_percent <= 1.30


def test_ampacity_sets_fewest_circuits_then_section():
    # ~49.6 MVA at 20 kV: a single 630 can't carry it within 80%, so circuits grow.
    # At 3 circuits the 630 fits ampacity; the 240 does not -> 630 x3.
    sel = select_cable(_catalogue(), s_kva=49_644, v_kv=20, length_km=2.5,
                       cos_phi=0.910, sin_phi=0.414, max_loss_percent=1.30)
    assert sel.n_parallel == 3
    assert sel.cable.name == "AL_630"
    assert sel.utilization <= 0.80 + 1e-9
    assert sel.loss_percent <= 1.30 + 1e-9


def test_loss_budget_forces_more_conductor_than_ampacity_alone():
    # Long line, modest current: ampacity allows one small cable, but the loss
    # budget forces a bigger section / more circuits.
    cat = _catalogue()
    loose = select_cable(cat, s_kva=8000, v_kv=20, length_km=20.0,
                         cos_phi=0.95, sin_phi=0.312, max_loss_percent=6.0)
    strict = select_cable(cat, s_kva=8000, v_kv=20, length_km=20.0,
                          cos_phi=0.95, sin_phi=0.312, max_loss_percent=1.0)
    loose_area = loose.cable.cross_section_mm2 * loose.n_parallel
    strict_area = strict.cable.cross_section_mm2 * strict.n_parallel
    assert strict_area > loose_area
    assert strict.loss_percent <= 1.0 + 1e-9
    assert loose.loss_percent <= 6.0 + 1e-9


def test_export_budget_scales_with_length():
    auto = AutoCable(candidates=_catalogue(), max_loss_percent_base=0.0,
                     max_loss_percent_per_km=0.1)
    assert auto.admissible_loss_percent(10.0) == pytest.approx(1.0)
    assert auto.admissible_loss_percent(2.5) == pytest.approx(0.25)


def test_collection_budget_is_constant():
    auto = AutoCable(candidates=_catalogue(), max_loss_percent_base=1.30,
                     max_loss_percent_per_km=0.0)
    assert auto.admissible_loss_percent(5.0) == pytest.approx(1.30)


def test_optional_voltage_drop_cap_still_enforced():
    # With a tight voltage-drop cap, the chosen cable must respect it.
    sel = select_cable(_catalogue(), s_kva=8000, v_kv=20, length_km=20.0,
                       cos_phi=0.95, sin_phi=0.312, max_loss_percent=6.0,
                       max_vdrop_percent=2.0)
    assert sel.vdrop_percent <= 2.0 + 1e-9


def test_raises_when_nothing_fits():
    with pytest.raises(ValueError):
        select_cable(_catalogue(), s_kva=200_000, v_kv=20, length_km=0.5,
                     cos_phi=1.0, sin_phi=0.0, max_loss_percent=1.30, max_parallel=1)


def test_autocable_in_chain_records_and_balances():
    chain = Chain([
        ChainElement(
            AutoCable(candidates=_catalogue(), max_utilization=0.80,
                      max_loss_percent_base=1.30, max_loss_percent_per_km=0.0),
            v_kv=20, length_km=2.5, label="MV collector",
        ),
    ])
    res = size_pv_inverters(chain, p_poc_kw=20_000, pf_target=0.95)
    row = res.losses[0]
    assert row.selected_cable in {"AL_240", "AL_630"}
    assert row.n_parallel >= 1
    assert row.utilization <= 0.80 + 1e-9
    assert row.loss_percent <= 1.30 + 1e-9
    assert res.power_balance_ok
    sel = select_cable(_catalogue(), 20_000, 20, 2.5, 0.95, 0.312, max_loss_percent=1.30)
    assert isinstance(sel, CableSelection)


# --- worst-case sizing (length unknown, full budget consumed) -------------------

def test_worst_case_pins_loss_at_budget():
    from powertool.cable_sizing import select_cable_worst_case

    sel, length_km = select_cable_worst_case(
        _catalogue(), s_kva=5000, v_kv=20, cos_phi=0.98,
        sin_phi=math.sqrt(1 - 0.98**2), loss_percent=1.30)
    assert sel.loss_percent == pytest.approx(1.30)
    assert length_km > 0
    # The implied length, fed back through the exact loss formula, must give
    # exactly the budget loss.
    i_c = sel.current_per_circuit_a
    dp = 3 * i_c * i_c * sel.cable.r_ohm_per_km * length_km * sel.n_parallel / 1000
    assert dp == pytest.approx(0.013 * 5000 * 0.98)


def test_worst_case_chain_element_without_length():
    # An AutoCable with no length in the Stage-1 chain runs the worst-case path:
    # the section consumes exactly its base budget.
    auto = AutoCable(candidates=_catalogue(), max_utilization=0.80,
                     max_loss_percent_base=1.30, name="conceptual MV")
    chain = Chain([ChainElement(auto, v_kv=20)])
    res = size_pv_inverters(chain, p_poc_kw=5000, pf_target=0.98)

    (loss,) = res.losses
    assert loss.kind == "Cable (worst case)"
    assert loss.loss_percent == pytest.approx(1.30)
    assert loss.dp_kw == pytest.approx(0.013 * loss.s_through_kva *
                                       (5000 / loss.s_through_kva), rel=1e-6)
    assert loss.length_km is not None and loss.length_km > 0
    # Reactive series loss follows the selected cable's X/R ratio.
    xr = loss.dq_kvar / loss.dp_kw
    cable = next(c for c in _catalogue() if c.name == loss.selected_cable)
    assert xr == pytest.approx(cable.x_ohm_per_km / cable.r_ohm_per_km)


def test_worst_case_is_conservative_vs_short_cable():
    # A known short cable loses less than the worst-case assumption.
    auto_wc = AutoCable(candidates=_catalogue(), max_loss_percent_base=1.30, name="wc")
    auto_short = AutoCable(candidates=_catalogue(), max_loss_percent_base=1.30, name="short")
    wc = size_pv_inverters(Chain([ChainElement(auto_wc, v_kv=20)]),
                           p_poc_kw=5000, pf_target=0.98)
    short = size_pv_inverters(Chain([ChainElement(auto_short, v_kv=20, length_km=0.2)]),
                              p_poc_kw=5000, pf_target=0.98)
    assert wc.p_inv_kw > short.p_inv_kw
