"""Tests for the backward-sweep PV inverter-sizing solver.

These validate the solver against independently hand-computed results and check
the power-balance conservation law that the engine relies on.
"""

import math

import pytest

from powertool import (
    Cable,
    Chain,
    ChainElement,
    Transformer,
    size_generation,
    size_generation_pq,
    size_pv_inverters,
)


def test_single_transformer_unity_pf():
    # One MV/LV transformer, 2000 kW at unity PF (Q_poc = 0).
    t = Transformer("t", s_rated_kva=2500, uk_percent=6.0, pk_kw=24.0, p0_kw=2.5, i0_percent=0.8)
    chain = Chain([ChainElement(t, v_kv=20)])
    res = size_pv_inverters(chain, p_poc_kw=2000, pf_target=1.0)

    # Active: copper at 80% load + iron.
    exp_dp = 24.0 * (2000 / 2500) ** 2 + 2.5
    assert res.p_inv_kw == pytest.approx(2000 + exp_dp)

    # Reactive: only the transformer (no POC reactive at unity PF).
    ux = math.sqrt(6.0**2 - 0.96**2)
    exp_dq = ux / 100 * 2000**2 / 2500 + 0.8 / 100 * 2500
    assert res.q_inv_kvar == pytest.approx(exp_dq)
    assert res.s_inv_kva == pytest.approx(math.hypot(res.p_inv_kw, res.q_inv_kvar))
    assert res.power_balance_ok


def test_cable_reactive_is_series_only_and_never_negative():
    # Worst-case sizing convention: cable charging is computed but NOT netted into the
    # reactive, so the cable's reactive contribution is the series I^2X only (>= 0),
    # even when charging would otherwise dominate.
    cable = Cable("c", r_ohm_per_km=0.125, x_ohm_per_km=0.110, b_us_per_km=60.0)
    chain = Chain([ChainElement(cable, v_kv=20, length_km=2.0)])
    res = size_pv_inverters(chain, p_poc_kw=3000, pf_target=1.0)

    i = 3000 / (math.sqrt(3) * 20)
    exp_dp = 3 * i * i * (0.125 * 2) / 1000
    exp_dq_series = 3 * i * i * (0.110 * 2) / 1000
    assert res.p_inv_kw == pytest.approx(3000 + exp_dp)
    assert res.q_inv_kvar == pytest.approx(exp_dq_series)  # series only, not netted
    assert res.q_inv_kvar >= 0
    assert res.losses[0].q_charging_kvar > 0  # charging still computed for information
    assert res.power_balance_ok


def test_power_factor_sets_poc_reactive():
    # Q_poc = P * tan(acos(PF)), injected (positive).
    t = Transformer("t", s_rated_kva=5000, uk_percent=6.0, pk_kw=40.0)
    chain = Chain([ChainElement(t, v_kv=20)])
    res = size_pv_inverters(chain, p_poc_kw=4000, pf_target=0.95)
    assert res.q_poc_kvar == pytest.approx(4000 * math.tan(math.acos(0.95)))
    assert res.q_poc_kvar > 0


def test_active_power_monotonically_increases_toward_inverter():
    # Walking from POC to inverter, active power can only grow (losses add).
    t = Transformer("t", s_rated_kva=2500, uk_percent=6.0, pk_kw=24.0, p0_kw=2.5)
    cable = Cable("c", r_ohm_per_km=0.1, x_ohm_per_km=0.1)
    chain = Chain(
        [
            ChainElement(t, v_kv=20, label="trafo"),
            ChainElement(cable, v_kv=20, length_km=1.0, label="cable"),
        ]
    )
    res = size_pv_inverters(chain, p_poc_kw=2000, pf_target=0.95)
    assert res.p_inv_kw > 2000
    assert all(e.dp_kw >= 0 for e in res.losses)


def test_parallel_cables_reduce_series_losses():
    # n parallel circuits share the current: series loss scales as 1/n.
    cable = Cable("c", r_ohm_per_km=0.1, x_ohm_per_km=0.1, b_us_per_km=0.0)
    one = Chain([ChainElement(cable, v_kv=20, length_km=1.0, n_parallel=1)])
    four = Chain([ChainElement(cable, v_kv=20, length_km=1.0, n_parallel=4)])
    loss1 = size_pv_inverters(one, 5000, 1.0).total_active_loss_kw
    loss4 = size_pv_inverters(four, 5000, 1.0).total_active_loss_kw
    assert loss4 == pytest.approx(loss1 / 4)


@pytest.mark.parametrize("bad_pf", [0.0, -0.1, 1.5])
def test_invalid_power_factor_raises(bad_pf):
    t = Transformer("t", s_rated_kva=2500, uk_percent=6.0, pk_kw=24.0)
    chain = Chain([ChainElement(t, v_kv=20)])
    with pytest.raises(ValueError):
        size_pv_inverters(chain, p_poc_kw=2000, pf_target=bad_pf)


def test_invalid_poc_power_raises():
    t = Transformer("t", s_rated_kva=2500, uk_percent=6.0, pk_kw=24.0)
    chain = Chain([ChainElement(t, v_kv=20)])
    with pytest.raises(ValueError):
        size_pv_inverters(chain, p_poc_kw=-100, pf_target=1.0)


def test_power_factor_form_delegates_to_reactive_in_form():
    # size_generation must compute Q from the PF target and delegate to
    # size_generation_pq; both forms produce identical results for the same
    # effective (P, Q) at the head of the chain.
    t = Transformer("t", s_rated_kva=5000, uk_percent=6.0, pk_kw=40.0)
    chain = Chain([ChainElement(t, v_kv=20)])
    p_poc_kw, pf_target = 4000.0, 0.95
    q_poc_kvar = p_poc_kw * math.tan(math.acos(pf_target))

    via_pf = size_generation(chain, p_poc_kw=p_poc_kw, pf_target=pf_target)
    via_pq = size_generation_pq(chain, p_head_kw=p_poc_kw, q_head_kvar=q_poc_kvar)

    assert via_pf.p_inv_kw == pytest.approx(via_pq.p_inv_kw)
    assert via_pf.q_inv_kvar == pytest.approx(via_pq.q_inv_kvar)
    assert via_pf.s_inv_kva == pytest.approx(via_pq.s_inv_kva)
    assert via_pf.q_poc_kvar == pytest.approx(via_pq.q_poc_kvar)


def test_size_pv_inverters_alias_is_deprecated_but_equivalent():
    t = Transformer("t", s_rated_kva=2500, uk_percent=6.0, pk_kw=24.0)
    chain = Chain([ChainElement(t, v_kv=20)])
    with pytest.warns(DeprecationWarning):
        via_alias = size_pv_inverters(chain, p_poc_kw=2000, pf_target=1.0)
    via_new_name = size_generation(chain, p_poc_kw=2000, pf_target=1.0)
    assert via_alias.p_inv_kw == pytest.approx(via_new_name.p_inv_kw)


def test_power_factor_target_is_echoed_verbatim():
    # pf_target echoes what the caller ASKED FOR, not an effective power factor
    # recomputed from P and Q. The two agree to within an ulp, so an approx
    # comparison would pass either way — this asserts exact equality on purpose,
    # because they are different quantities and only one of them is a target.
    t = Transformer("t", s_rated_kva=5000, uk_percent=6.0, pk_kw=40.0)
    chain = Chain([ChainElement(t, v_kv=20)])
    for pf in (0.8, 0.92, 0.95, 0.995, 1.0):
        result = size_generation(chain, p_poc_kw=4000.0, pf_target=pf)
        assert result.pf_target == pf
