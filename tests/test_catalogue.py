"""Tests for the on-disk component catalogue (data/*.yaml).

Guards that the real YAML loads and that the PV transformer stations carry the
agreed parameters and the 'POWER kVA - BRAND' display label.
"""

import pytest

from powertool import ComponentDatabase

# Expected PV transformer stations: key -> (rated kVA, brand, dropdown label).
PV_STATIONS = {
    "SUNGROW_MVS3200": (3200, "Sungrow", "3200 kVA - Sungrow"),
    "SUNGROW_MVS4480": (4480, "Sungrow", "4480 kVA - Sungrow"),
    "SUNGROW_MVS6400": (6400, "Sungrow", "6400 kVA - Sungrow"),
    "SUNGROW_MVS7040": (7040, "Sungrow", "7040 kVA - Sungrow"),
    "SUNGROW_MVS8960": (8960, "Sungrow", "8960 kVA - Sungrow"),
    "HUAWEI_JUPITER3000": (3300, "Huawei", "3300 kVA - Huawei"),
    "HUAWEI_JUPITER6000": (6600, "Huawei", "6600 kVA - Huawei"),
    "HUAWEI_JUPITER9000": (9000, "Huawei", "9000 kVA - Huawei"),
    "TBEA_TS3000": (3300, "TBEA", "3300 kVA - TBEA"),
    "TBEA_TS6000": (6600, "TBEA", "6600 kVA - TBEA"),
    "TBEA_TS9000": (9240, "TBEA", "9240 kVA - TBEA"),
}


@pytest.fixture(scope="module")
def db() -> ComponentDatabase:
    return ComponentDatabase.load()


def test_catalogue_loads(db):
    assert db.transformers
    assert db.cables


def test_pv_stations_present_with_labels(db):
    for key, (kva, brand, label) in PV_STATIONS.items():
        tx = db.transformers[key]
        assert tx.s_rated_kva_at_40c == kva
        assert tx.brand == brand
        assert tx.display_name == label


def test_pv_station_design_assumptions(db):
    # uk = 8 %, P0 = 0.1 % of rating, Pk = 1 % of rating (agreed assumptions).
    for key, (kva, _, _) in PV_STATIONS.items():
        tx = db.transformers[key]
        assert tx.uk_percent == 8.0
        assert tx.p0_kw == pytest.approx(0.001 * kva)
        assert tx.pk_kw == pytest.approx(0.01 * kva)
        assert tx.i0_percent == 0.0
        assert tx.lv_kv == 0.8
        # The loss model must be well-formed (uk > resistive part) for every unit.
        assert tx.ux_percent > 0
        dp, dq = tx.losses(kva)  # at full load, no error and positive losses
        assert dp > 0 and dq > 0


def test_only_branded_pv_stations(db):
    # The generic placeholders were removed: every catalogue transformer is a
    # branded PV station now (the HV transformer is auto-sized, not catalogued).
    assert "HV_50MVA_132_20kV" not in db.transformers
    assert "MV_2500kVA_20_0.8kV" not in db.transformers
    assert set(db.transformers) == set(PV_STATIONS)
    assert all(tx.brand for tx in db.transformers.values())


def test_bess_solutions_load(db):
    assert db.bess_solutions
    for sol in db.bess_solutions.values():
        assert sol.brand and sol.series and sol.model
        assert sol.e_nominal_kwh > 0
        assert sol.pcs_s_kva > 0
        assert sol.pcs_count >= 1
        assert sol.pcs_lv_kv > 0
        assert sol.duration_h > 0


def test_sungrow_powertitan_entry_present_with_published_parameters(db):
    # The only entry in the catalogue: the invented placeholders are gone, and
    # this one carries the real datasheet figures, keyed by a slug of brand
    # and model.
    sol = db.bess_solutions["sungrow-st6900ux-4h"]
    assert sol.brand == "Sungrow"
    assert sol.series == "PowerTitan 3.0"
    assert sol.model == "ST6900UX-4H"
    assert sol.display_name == "PowerTitan 3.0 — ST6900UX-4H"
    assert sol.e_nominal_kwh == 6904.0
    assert sol.pcs_s_kva == 450.0
    assert sol.pcs_count == 4
    assert sol.pcs_lv_kv == 0.69
    assert sol.duration_h == 4.0
    # The datasheet publishes no auxiliary figure: None, not zero — a real
    # zero and a datasheet's silence are not the same value (ticket 07).
    assert sol.aux_p_kw is None
    assert sol.aux_q_kvar is None
    assert sol.preliminary is True


def test_no_bess_solution_is_placeholder_data(db):
    assert set(db.bess_solutions) == {"sungrow-st6900ux-4h", "sungrow-st6680ux-2h"}


def test_bess_station_transformers_load_and_pair_with_solutions(db):
    # A SEPARATE catalogue from the PV transformer stations.
    assert db.bess_transformers
    assert set(db.bess_transformers) & set(db.transformers) == set()

    # Every placeholder solution has at least one BESS station transformer
    # whose LV rating matches its PCS voltage.
    for sol in db.bess_solutions.values():
        assert any(
            tx.lv_kv == pytest.approx(sol.pcs_lv_kv) for tx in db.bess_transformers.values()
        ), f"no BESS station transformer pairs with {sol.name}'s PCS voltage"


def test_pairing_lives_on_the_station_transformer(db):
    # The pairing carries the container count per station, keyed by station
    # transformer, then solution key — the shorter list to maintain by hand
    # (one station transformer pairs with few solutions).
    assert db.bess_pairings["GENERIC_BESS_TX_2750_LV069"] == {"sungrow-st6900ux-4h": 1}
    assert db.bess_pairings["GENERIC_BESS_TX_4000_LV069"] == {"sungrow-st6900ux-4h": 2}


def test_a_station_transformer_may_be_sold_with_nothing(db):
    # GENERIC_BESS_TX_1750_LV100 exists deliberately unpaired: it exercises
    # bess_lv_mismatch (its LV disagrees with every solution's PCS voltage),
    # and it must not silently inherit another transformer's pairing.
    assert db.bess_pairings.get("GENERIC_BESS_TX_1750_LV100") in (None, {})


def test_transformer_stays_bess_agnostic():
    # paired_solutions is popped out of the YAML entry before the Transformer
    # is built — Transformer is shared with the PV catalogue and carries no
    # BESS-specific field.
    from powertool.components import Transformer
    assert "paired_solutions" not in Transformer.__dataclass_fields__


def test_the_real_sungrow_station_carries_its_confirmed_container_count(db):
    # 4 containers, confirmed by the project owner rather than by the datasheet,
    # which states no count at all. Pinned because the number has no paper
    # source in the repo: if it changes, it must change against a citation.
    assert db.bess_pairings["SUNGROW_MVS7400_LS"] == {"sungrow-st6900ux-4h": 4}


def test_the_0_5c_sungrow_station_carries_its_confirmed_container_count(db):
    # 2 containers, confirmed by the project owner rather than by the
    # datasheet, which states no count at all — same standing as the
    # SUNGROW_MVS7400_LS pairing above.
    assert db.bess_pairings["SUNGROW_MVS7080_LS"] == {"sungrow-st6680ux-2h": 2}
