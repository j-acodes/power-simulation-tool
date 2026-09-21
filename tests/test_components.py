"""Unit tests for the component physics models.

Expected values are computed by hand from the underlying physics so these are a
genuine cross-check, not a snapshot of whatever the code happens to produce.
"""

import math

import pytest

from powertool.components import (
    BUSBAR_SWITCHGEAR_LADDER_A,
    DEFAULT_CABLE_ENTRY_CABLES_PER_PHASE,
    DEFAULT_CABLE_ENTRY_MAX_CROSS_SECTION_MM2,
    DEFAULT_SWITCHGEAR_RATED_CURRENT_A,
    Cable,
    Transformer,
    current_a,
    size_busbar_switchgear_rating,
)


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
    t = Transformer("t", s_rated_kva_at_40c=2500, uk_percent=6.0, pk_kw=24.0, p0_kw=2.5, i0_percent=0.8)
    dp, dq = t.losses(2500)
    assert dp == pytest.approx(24.0 + 2.5)
    # ux% = sqrt(uk^2 - ur^2), ur% = 100*Pk/Sr = 0.96
    assert t.ux_percent == pytest.approx(math.sqrt(6.0**2 - 0.96**2))
    # dQ = ux%/100 * Sr + i0%/100 * Sr  (at rated)
    exp_dq = t.ux_percent / 100 * 2500 + 0.8 / 100 * 2500
    assert dq == pytest.approx(exp_dq)


def test_transformer_copper_scales_with_load_squared():
    # At half load copper loss is a quarter; iron is unchanged.
    t = Transformer("t", s_rated_kva_at_40c=2500, uk_percent=6.0, pk_kw=24.0, p0_kw=2.5)
    dp, _ = t.losses(1250)
    assert dp == pytest.approx(24.0 * 0.25 + 2.5)


def test_transformer_invalid_uk_raises():
    # uk% smaller than the resistive part implied by Pk is non-physical.
    t = Transformer("bad", s_rated_kva_at_40c=1000, uk_percent=0.1, pk_kw=50.0)
    with pytest.raises(ValueError):
        _ = t.ux_percent


# --- rating_at: lookup only, never interpolated (ADR-0004) -----------------

def test_rating_at_returns_the_published_30c_figure():
    t = Transformer("t", s_rated_kva_at_40c=2750, s_rated_kva_at_30c=3080,
                    uk_percent=8.0, pk_kw=27.5)
    assert t.rating_at(30.0) == 3080
    assert t.rating_at(40.0) == 2750


def test_rating_at_falls_back_upward_when_30c_is_null():
    # 30 C is not published: the nearest published ambient AT OR ABOVE 30 C
    # is 40 C, so that (lower, conservative) figure is returned — never an
    # interpolated value.
    t = Transformer("t", s_rated_kva_at_40c=2750, s_rated_kva_at_30c=None,
                    uk_percent=8.0, pk_kw=27.5)
    assert t.rating_at(30.0) == 2750
    # A requested ambient above every published one falls back to the
    # highest published ambient — still the 40 C figure here.
    assert t.rating_at(50.0) == 2750


def test_rating_at_never_interpolates():
    t = Transformer("t", s_rated_kva_at_40c=2750, s_rated_kva_at_30c=3080,
                    uk_percent=8.0, pk_kw=27.5)
    # An ambient strictly between the two published points still resolves to
    # the nearest published ambient at or above it (40 C), not an average.
    assert t.rating_at(35.0) == 2750


# --- BessSolution: the discharge duration is declared, never derived --------

def _solution(**overrides):
    from powertool.components import BessSolution
    params = dict(
        name="TEST_BESS", brand="Acme", series="Series", model="Model",
        e_nominal_kwh=5000.0, pcs_s_kva=1250.0, pcs_count=2, pcs_lv_kv=0.69,
        duration_h=4.0, aux_p_kw=40.0, aux_q_kvar=10.0,
    )
    params.update(overrides)
    return BessSolution(**params)


def test_display_name_leads_with_series_and_qualifies_with_model():
    sol = _solution(series="PowerTitan 3.0", model="ST6900UX-4H")
    assert sol.display_name == "PowerTitan 3.0 — ST6900UX-4H"


# --- Switchgear rated current (ADR-0006) ---------------------------------


def test_switchgear_rated_current_uses_the_published_figure():
    t = Transformer("t", s_rated_kva_at_40c=3200, uk_percent=8.0, pk_kw=32.0,
                    p0_kw=3.2, i0_percent=0.0, rmu_rated_current_a=630)
    assert t.switchgear_rated_current_a == 630
    assert t.switchgear_rating_published is True


def test_switchgear_rated_current_falls_back_when_unpublished():
    # Silence is not the absence of a limit: it resolves to the standard
    # ring-main-unit size, and says it was defaulted. See ADR-0006.
    t = Transformer("t", s_rated_kva_at_40c=3300, uk_percent=8.0, pk_kw=33.0,
                    p0_kw=3.3, i0_percent=0.0, rmu_rated_current_a=None)
    assert t.switchgear_rated_current_a == DEFAULT_SWITCHGEAR_RATED_CURRENT_A
    assert t.switchgear_rated_current_a == 630.0
    assert t.switchgear_rating_published is False


def test_switchgear_rated_current_never_resolves_to_no_limit():
    for published in (None, 630, 1250):
        t = Transformer("t", s_rated_kva_at_40c=3200, uk_percent=8.0, pk_kw=32.0,
                        p0_kw=3.2, i0_percent=0.0, rmu_rated_current_a=published)
        assert t.switchgear_rated_current_a > 0
        assert math.isfinite(t.switchgear_rated_current_a)


def test_switchgear_rated_current_rejects_a_nonpositive_published_figure():
    with pytest.raises(ValueError):
        Transformer("t", s_rated_kva_at_40c=3200, uk_percent=8.0, pk_kw=32.0,
                    p0_kw=3.2, i0_percent=0.0, rmu_rated_current_a=0)


# --- Cable entry (ADR-0007) --------------------------------------------------


def _tx(**overrides):
    params = dict(name="t", s_rated_kva_at_40c=3200, uk_percent=8.0, pk_kw=32.0,
                  p0_kw=3.2, i0_percent=0.0)
    params.update(overrides)
    return Transformer(**params)


def test_cable_entry_uses_the_published_figures():
    t = _tx(cable_entry_cables_per_phase=3, cable_entry_max_cross_section_mm2=500.0)
    assert t.cable_entry_published is True
    assert t.cable_entry_parallel_limit == 3
    assert t.cable_entry_cross_section_limit_mm2 == 500.0


def test_cable_entry_falls_back_when_unpublished():
    # Silence is not the absence of a limit (ADR-0007, same stance as the
    # switchgear rated current in ADR-0006).
    t = _tx()
    assert t.cable_entry_published is False
    assert t.cable_entry_parallel_limit == DEFAULT_CABLE_ENTRY_CABLES_PER_PHASE
    assert t.cable_entry_parallel_limit == 2
    assert t.cable_entry_cross_section_limit_mm2 == DEFAULT_CABLE_ENTRY_MAX_CROSS_SECTION_MM2
    assert t.cable_entry_cross_section_limit_mm2 == 300.0


def test_cable_entry_treats_one_published_figure_alone_as_unpublished():
    # One cable entry per station model (CONTEXT.md): a datasheet publishing
    # only one of the pair is never mixed with the fallback for the other.
    only_cables = _tx(cable_entry_cables_per_phase=3)
    assert only_cables.cable_entry_published is False
    assert only_cables.cable_entry_parallel_limit == DEFAULT_CABLE_ENTRY_CABLES_PER_PHASE
    assert only_cables.cable_entry_cross_section_limit_mm2 == DEFAULT_CABLE_ENTRY_MAX_CROSS_SECTION_MM2

    only_cross_section = _tx(cable_entry_max_cross_section_mm2=500.0)
    assert only_cross_section.cable_entry_published is False
    assert only_cross_section.cable_entry_parallel_limit == DEFAULT_CABLE_ENTRY_CABLES_PER_PHASE
    assert only_cross_section.cable_entry_cross_section_limit_mm2 == DEFAULT_CABLE_ENTRY_MAX_CROSS_SECTION_MM2


def test_cable_entry_never_resolves_to_no_limit():
    for cables, mm2 in ((None, None), (2, 300.0), (4, 630.0)):
        t = _tx(cable_entry_cables_per_phase=cables, cable_entry_max_cross_section_mm2=mm2)
        assert t.cable_entry_parallel_limit > 0
        assert math.isfinite(t.cable_entry_parallel_limit)
        assert t.cable_entry_cross_section_limit_mm2 > 0
        assert math.isfinite(t.cable_entry_cross_section_limit_mm2)


def test_cable_entry_rejects_a_nonpositive_published_cables_per_phase():
    with pytest.raises(ValueError):
        _tx(cable_entry_cables_per_phase=0, cable_entry_max_cross_section_mm2=300.0)


def test_cable_entry_rejects_a_non_integer_cables_per_phase():
    with pytest.raises(ValueError):
        _tx(cable_entry_cables_per_phase=2.5, cable_entry_max_cross_section_mm2=300.0)


def test_cable_entry_rejects_a_nonpositive_published_cross_section():
    with pytest.raises(ValueError):
        _tx(cable_entry_cables_per_phase=2, cable_entry_max_cross_section_mm2=0)


def test_size_busbar_switchgear_rating_picks_smallest_admissible_ladder_step():
    # Exactly the bottom rung resolves to itself — no margin, and the 1e-9
    # tolerance means it never spuriously escalates.
    assert size_busbar_switchgear_rating(630.0) == 630.0
    # One amp over steps up to the next rung.
    assert size_busbar_switchgear_rating(631.0) == 800.0
    # Exactly the top rung still resolves — it is admissible, not excluded.
    assert size_busbar_switchgear_rating(4000.0) == 4000.0
    # A hair over the top has no admissible size.
    assert size_busbar_switchgear_rating(4000.1) is None
    assert size_busbar_switchgear_rating(0.0) == BUSBAR_SWITCHGEAR_LADDER_A[0]
