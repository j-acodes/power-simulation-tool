"""Unit tests for the component physics models.

Expected values are computed by hand from the underlying physics so these are a
genuine cross-check, not a snapshot of whatever the code happens to produce.
"""

import math

import pytest

from powertool.components import Cable, Transformer, current_a


def test_current_three_phase():
    # I = S / (sqrt(3) * V):  5000 kVA at 20 kV -> 144.34 A
    assert current_a(5000, 20) == pytest.approx(5000 / (math.sqrt(3) * 20))
    assert current_a(5000, 20) == pytest.approx(144.3376, abs=1e-3)


def test_current_rejects_nonpositive_voltage():
    with pytest.raises(ValueError):
        current_a(1000, 0)


def test_cable_series_losses():
    # 2 km, S = 5000 kVA at 20 kV.  I = 144.3376 A
    # dP = 3 I^2 (r*L) / 1000,  dQ = 3 I^2 (x*L) / 1000
    cable = Cable("c", r_ohm_per_km=0.125, x_ohm_per_km=0.110)
    i = 5000 / (math.sqrt(3) * 20)
    exp_dp = 3 * i * i * (0.125 * 2) / 1000
    exp_dq = 3 * i * i * (0.110 * 2) / 1000
    dp, dq = cable.series_losses(5000, 20, 2.0)
    assert dp == pytest.approx(exp_dp)
    assert dq == pytest.approx(exp_dq)
    assert dp == pytest.approx(15.625, abs=1e-3)


def test_cable_charging():
    # Q_charging = V^2 * B_us / 1000.  20 kV, 60 uS/km, 2 km -> 48 kvar
    cable = Cable("c", r_ohm_per_km=0.1, x_ohm_per_km=0.1, b_us_per_km=60.0)
    assert cable.charging_kvar(20, 2.0) == pytest.approx(48.0)


def test_transformer_rated_losses():
    # At rated load: copper = Pk, plus iron = P0.
    t = Transformer("t", s_rated_kva=2500, uk_percent=6.0, pk_kw=24.0, p0_kw=2.5, i0_percent=0.8)
    dp, dq = t.losses(2500)
    assert dp == pytest.approx(24.0 + 2.5)
    # ux% = sqrt(uk^2 - ur^2), ur% = 100*Pk/Sr = 0.96
    assert t.ux_percent == pytest.approx(math.sqrt(6.0**2 - 0.96**2))
    # dQ = ux%/100 * Sr + i0%/100 * Sr  (at rated)
    exp_dq = t.ux_percent / 100 * 2500 + 0.8 / 100 * 2500
    assert dq == pytest.approx(exp_dq)


def test_transformer_copper_scales_with_load_squared():
    # At half load copper loss is a quarter; iron is unchanged.
    t = Transformer("t", s_rated_kva=2500, uk_percent=6.0, pk_kw=24.0, p0_kw=2.5)
    dp, _ = t.losses(1250)
    assert dp == pytest.approx(24.0 * 0.25 + 2.5)


def test_transformer_invalid_uk_raises():
    # uk% smaller than the resistive part implied by Pk is non-physical.
    t = Transformer("bad", s_rated_kva=1000, uk_percent=0.1, pk_kw=50.0)
    with pytest.raises(ValueError):
        _ = t.ux_percent
