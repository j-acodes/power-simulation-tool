"""Tests for the SLD layout model and its rendering: a standalone single-busbar
PV plant with an HV interconnection (ticket 01: structure and tags; ticket 02:
the sized figures, the legend, the indicative-devices note and † fallback
marking).

Per the SLD spec, a good test asserts on what a reader of the drawing would
see — tags, counts, order, label text — never on coordinates or drawing
primitives. The architecture fixtures are built through the existing engine
entry points, the same way :mod:`test_architecture` and :mod:`test_pdf_report`
do; the inverter-label tests go one layer up, through a drawn diagram (the
inverter model/count is diagram-layer information the engine-level fixtures
never carry — see :mod:`powertool.sld`'s module docstring).
"""

import re
import sys

import pytest

sys.path.insert(0, "tests")

from powertool import Transformer                              # noqa: E402
from powertool.architecture import (                          # noqa: E402
    BusbarSection,
    arrange_plant,
    size_architecture,
    size_branch,
    size_plant,
)
from powertool.components import DEFAULT_SWITCHGEAR_RATED_CURRENT_A  # noqa: E402
from powertool.graph import branches_summary, graph_to_inputs, sld_fleets  # noqa: E402
from powertool.sld import (                                    # noqa: E402
    Sheet,
    aux_transformer_rating,
    build_sld_pdf,
    sheet_to_drawing,
    sld_sheets,
)

from backend.main import db                                    # noqa: E402
from backend.solve import solve_architecture                   # noqa: E402
from test_architecture import _catalogue, _full_plant_inputs, _hv_tx, _stage1, _tx_2500  # noqa: E402
from test_graph import _edge, _node, _settings                 # noqa: E402
from test_hybrid import _hybrid_with_drawn_bess               # noqa: E402
from test_pdf_report import _hybrid_with_hv_export             # noqa: E402


# --- fixtures -----------------------------------------------------------------

def _pv_plant_arch():
    """The ticket-01 target case: one busbar, one PV fleet, HV interconnection.
    4 circuits (5+5+4+4), 18 stations — the golden 45 MW example fleet."""
    stage1, layout = _full_plant_inputs()
    return size_architecture(layout, stage1, _catalogue(), hv_transformer=_hv_tx())


def _bess_plant_arch():
    stage1 = _stage1(p_inv_kw=43_000, q_inv_kvar=9_000)
    layout = arrange_plant(
        stage1, [(_tx_2500(rmu_rated_current_a=380.0), 18)],
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0, kind="bess",
    )
    return size_architecture(layout, stage1, _catalogue(), hv_transformer=_hv_tx())


def _multi_busbar_arch():
    stage1, layout = _full_plant_inputs()
    branch = size_branch(
        layout, _catalogue(),
        sections=[
            BusbarSection(busbar_id="a", circuit_indices=[1, 2]),
            BusbarSection(busbar_id="b", circuit_indices=[3, 4]),
        ],
    )
    return size_plant([branch], [stage1], hv_transformer=_hv_tx())


def _hybrid_arch():
    stage1, layout = _full_plant_inputs()
    branch = size_branch(layout, _catalogue())
    return size_plant([branch, branch], [stage1, stage1], hv_transformer=_hv_tx())


def _mv_interconnection_arch():
    stage1, layout = _full_plant_inputs()
    return size_architecture(layout, stage1, _catalogue())  # no hv_transformer


# --- fixtures: isolated fallback cases (ticket 02) ------------------------

def _tx_no_cable_entry(rmu_rated_current_a: float = 400.0) -> Transformer:
    """A station transformer with a PUBLISHED switchgear rating but no
    published cable entry — isolates the cable-entry † from the switchgear
    one (the opposite of ``_tx_2500()``, which always publishes cable entry
    regardless of its own ``rmu_rated_current_a`` argument)."""
    return Transformer("TX_2500_NO_ENTRY", s_rated_kva_at_40c=2500, uk_percent=6.0,
                       pk_kw=24.0, p0_kw=2.5, i0_percent=0.8, hv_kv=20, lv_kv=0.8,
                       rmu_rated_current_a=rmu_rated_current_a)


def _small_pv_arch(tx: Transformer, *, n_stations: int = 3):
    """A small single-circuit PV plant on ``tx`` — just big enough to size, so
    the fallback tests stay isolated from the 45 MW fixture's own figures."""
    stage1 = _stage1(p_inv_kw=6_000, q_inv_kvar=1_500)
    layout = arrange_plant(
        stage1, [(tx, n_stations)], trunk_length_km=0.5, spacing_km=0.3, v_mv_kv=20.0,
    )
    return size_architecture(layout, stage1, _catalogue(), hv_transformer=_hv_tx())


# --- fixtures: a drawn diagram, for the inverter model/count labels -------

def _pv_diagram_with_hv(*, p_target_mw: float = 8.0, model: str = "SUNGROW_MVS3200",
                        pv_inverter: str = "sungrow-sg350hx-20",
                        inverter_count: int = 10) -> dict:
    """The smallest drawn diagram in this ticket's scope: POC -> HV transformer
    -> busbar -> one circuit -> one PV station block, auto-arranged into
    however many stations the target power needs. Mirrors
    ``test_pdf_report._hybrid_with_hv_export``'s POC/HV wiring, minus the
    hybrid/aux parts this ticket doesn't touch."""
    return {
        "schema_version": 1,
        "settings": _settings(hv_kv=132.0),
        "nodes": [
            _node("poc", "poc", p_target_mw=p_target_mw, pf=0.95),
            _node("hv", "hv_tx", mode="auto", n_parallel=1),
            _node("bus", "busbar"),
            _node("s1", "station", mode="catalogue", model=model,
                  pv_inverter=pv_inverter, inverter_count=inverter_count),
        ],
        "edges": [
            _edge("e_export", "poc", "hv", length_m=1500.0),
            _edge("e_hvmv", "hv", "bus", length_m=0.0),
            _edge("e_t1", "bus", "s1", length_m=800.0),
        ],
    }


def _sheet_from_diagram(diagram: dict, *, feeder_pin_a: float | None = None) -> Sheet:
    """Solve ``diagram`` and build its sheet, mirroring ``backend.solve.
    sld_pdf``'s own ``fleets`` assembly (``branches_summary`` merged with
    ``sld_fleets``) rather than calling ``sld_sheets`` directly with a
    hand-built dict — so a test exercises the real merge, pins included."""
    if feeder_pin_a is not None:
        # The busbar node is "bus"; "e_t1" is circuit 1's trunk edge — same
        # convention as test_graph.py's pinned-feeder fixtures.
        bus_node = next(n for n in diagram["nodes"] if n["id"] == "bus")
        bus_node["props"]["feeder_switchgear_pins_a"] = {"e_t1": feeder_pin_a}
    inputs = graph_to_inputs(diagram, db)
    stage1s, _layouts, arch = solve_architecture(inputs, db)
    fleets = branches_summary(inputs, arch, stage1s)
    for fleet, pv in zip(fleets, sld_fleets(inputs)):
        fleet.update(pv)
    return sld_sheets(arch, fleets=fleets)[0]


# --- layout model ---------------------------------------------------------------

def test_one_sheet_for_a_one_busbar_pv_plant():
    sheets = sld_sheets(_pv_plant_arch())
    assert len(sheets) == 1
    assert isinstance(sheets[0], Sheet)
    assert sheets[0].busbar_tag == "BB1"


def test_one_element_per_station_the_architecture_holds():
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    n_stations = sum(len(c.stations) for c in arch.branches[0].circuits)
    station_elements = [e for e in sheet.elements if e.kind == "station"]
    assert len(station_elements) == n_stations == 18


def test_ts_numbering_follows_circuit_then_position():
    arch = _pv_plant_arch()
    branch = arch.branches[0]
    section = branch.sections[0]
    sheet = sld_sheets(arch)[0]

    by_id = {e.id: e for e in sheet.elements}
    by_index = {c.index: c for c in branch.circuits}
    expected_tags = []
    for c_idx in section.circuit_indices:
        circuit = by_index[c_idx]
        for station in sorted(circuit.stations, key=lambda s: s.index):
            expected_tags.append(f"station_{c_idx}_{station.index}")

    station_ids_in_order = [e.id for e in sheet.elements if e.kind == "station"]
    assert station_ids_in_order == expected_tags

    ts_tags = [by_id[eid].tag for eid in station_ids_in_order]
    assert ts_tags == [f"TS{i + 1}" for i in range(len(ts_tags))]
    # Ticket 02: the tag is still the first label, followed by the station's
    # own figures (transformer model key, kVA — see test_station_labels_*).
    for eid in station_ids_in_order:
        assert by_id[eid].labels[0] == by_id[eid].tag


def test_c_tags_follow_circuit_order():
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    feeder_tags = [e.tag for e in sheet.elements if e.kind == "feeder_breaker"]
    assert feeder_tags == ["C1", "C2", "C3", "C4"]


def test_grid_side_chain_elements_present_in_order():
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    kinds = [e.kind for e in sheet.elements]
    expected_prefix = [
        "poc", "metering", "disconnector", "hv_breaker", "hv_transformer",
        "export_cable", "mv_breaker", "busbar",
    ]
    assert kinds[: len(expected_prefix)] == expected_prefix


def test_grid_side_chain_elements_carry_no_tag():
    # No grid-side chain element is ever tagged (TS/C/BB only) — ticket 02
    # gives poc/hv_transformer figure labels (see the dedicated tests below),
    # but the untagged devices stay bare.
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    chain_kinds = {"poc", "metering", "disconnector", "hv_breaker",
                   "hv_transformer", "export_cable", "mv_breaker"}
    untagged_and_unlabeled = {"metering", "disconnector", "hv_breaker", "mv_breaker"}
    for e in sheet.elements:
        if e.kind in chain_kinds:
            assert e.tag is None
            if e.kind in untagged_and_unlabeled:
                assert e.labels == []


# --- figure labels (ticket 02) ---------------------------------------------

def test_poc_label_shows_voltage_and_delivered_mw():
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    poc = next(e for e in sheet.elements if e.kind == "poc")
    mw = arch.p_poc_delivered_kw / 1000.0
    assert poc.labels == [f"{arch.export.v_hv_kv:g} kV", f"{mw:.2f} MW"]


def test_hv_transformer_label_shows_catalogue_key_and_mva():
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    hv = next(e for e in sheet.elements if e.kind == "hv_transformer")
    tx = arch.export.hv_transformer
    # The catalogue key, not StationResult's display-label convention.
    assert hv.labels[0] == tx.name == "HV_50MVA"
    assert hv.labels[1] == f"{tx.s_rated_kva_at_40c / 1000:.1f} MVA"


def test_busbar_label_shows_tag_and_voltage():
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    busbar = next(e for e in sheet.elements if e.kind == "busbar")
    v_mv = arch.branches[0].sections[0].v_mv_kv
    assert busbar.labels == ["BB1", f"{v_mv:g} kV"]


def test_feeder_label_shows_tag_and_busbar_switchgear_rating():
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    feeders = sorted(
        (e for e in sheet.elements if e.kind == "feeder_breaker"),
        key=lambda e: e.tag,
    )
    # Circuits 1/2 both head 344 A -> 630 A on the ladder; 3/4 head 275 A ->
    # also 630 A (see the fixture's own i_trunk_a figures) — every feeder on
    # this no-fallback fixture reads the sized rating with no †.
    for feeder in feeders:
        assert feeder.labels[1].endswith(" A")
        assert "†" not in feeder.labels[1]


def test_circuit_segment_labels_carry_cable_and_length_taper_and_parallel_run():
    # The 45 MW fixture's own circuit 1 already tapers (busbar-end segments
    # ride 2 parallel Al 95mm^2 runs, the far end drops to a single run) —
    # see the module's numeric trace during implementation.
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    circuit = arch.branches[0].circuits[0]
    segs = {
        e.id: e for e in sheet.elements if e.kind == "cable_label"
        and e.id.startswith("segment_1_")
    }
    assert len(segs) == len(circuit.segments) == 5

    trunk = segs["segment_1_1"]
    # Plain reading form, not the catalogue key: runs x material phases x section.
    assert circuit.segments[0].cable_label == "Al_3x2x95_20kV"
    assert trunk.labels[0] == "2 × Al 3×95 mm²"
    assert trunk.labels[1] == f"{circuit.segments[0].length_km:g} km"

    far = segs["segment_1_5"]
    far_sel = circuit.segments[4].selection
    assert far_sel.n_parallel == 1
    assert far.labels[0] == f"Al 3×{far_sel.cable.cross_section_mm2:g} mm²"  # one run: no count
    # Tapered: the far segment's own cable differs from the trunk's.
    assert far.labels[0] != trunk.labels[0]


def test_station_label_shows_catalogue_model_key_and_kva():
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    station = next(e for e in sheet.elements if e.id == "station_1_1")
    st = arch.branches[0].circuits[0].stations[0]
    plan = arch.branches[0].layout.circuit_plans[0][0]
    assert station.labels[0] == "TS1"
    assert station.labels[1] == plan.transformer.name == "TX_2500"
    assert station.labels[2] == f"{st.s_rated_kva:,.0f} kVA"


def test_station_label_uses_catalogue_key_not_display_label():
    # TX_2500 (above) has no brand, so its display label coincides with its
    # key — SUNGROW_MVS3200 (via the drawn-diagram fixture) does not, proving
    # the label is really the key and not StationResult.model.
    sheet = _sheet_from_diagram(_pv_diagram_with_hv())
    station = next(e for e in sheet.elements if e.kind == "station")
    tx = db.transformers["SUNGROW_MVS3200"]
    assert tx.display_name != tx.name
    assert station.labels[1] == tx.name == "SUNGROW_MVS3200"
    assert tx.display_name not in station.labels


def test_station_without_fleets_has_no_inverter_line():
    # Every engine-level fixture in this file omits ``fleets`` — the drawing
    # still builds, just without the inverter line (see the module docstring).
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    station = next(e for e in sheet.elements if e.id == "station_1_1")
    assert len(station.labels) == 3
    assert not any(line.startswith("×") for line in station.labels)


def test_station_inverter_line_shows_count_and_catalogue_model_key():
    sheet = _sheet_from_diagram(_pv_diagram_with_hv())
    station = next(e for e in sheet.elements if e.kind == "station")
    assert station.labels[-1] == "× 10 sungrow-sg350hx-20"


def test_legend_and_indicative_note_present():
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    assert sheet.legend  # non-empty, every symbol kind this sheet actually used
    kinds = [k for k, _caption in sheet.legend]
    assert len(kinds) == len(set(kinds))  # no duplicate entries
    assert "station" in kinds and "busbar" in kinds and "poc" in kinds
    assert "Protection devices are indicative; the tool does not size them." in sheet.notes


def test_legend_has_one_entry_for_every_breaker_role():
    # hv_breaker, mv_breaker and feeder_breaker draw the identical IEC
    # breaker square — one "Circuit breaker" legend entry, not three.
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    captions = [caption for _kind, caption in sheet.legend]
    assert captions.count("Circuit breaker") == 1
    assert len(captions) == len(set(captions))  # no duplicate captions at all


# --- feeder rating: sized vs. pinned (ticket 02) ----------------------------

def test_feeder_shows_the_sized_busbar_switchgear_rating_no_dagger():
    # The feeder is busbar switchgear (sized off the ladder), never a value
    # this module assumes — it never carries a † even on a fallback design
    # (see the switchgear-fallback test below, which uses this same fixture).
    arch = _small_pv_arch(_tx_2500())
    sheet = sld_sheets(arch)[0]
    feeder = next(e for e in sheet.elements if e.kind == "feeder_breaker")
    assert feeder.labels[1] == f"{DEFAULT_SWITCHGEAR_RATED_CURRENT_A:,.0f} A"


def test_pinned_feeder_shows_the_pinned_value():
    sheet = _sheet_from_diagram(_pv_diagram_with_hv(), feeder_pin_a=800.0)
    feeder = next(e for e in sheet.elements if e.kind == "feeder_breaker")
    assert feeder.labels[1] == "800 A"


# --- † assumed values (ticket 02) -------------------------------------------

def test_switchgear_fallback_marks_the_station_and_lists_a_note():
    arch = _small_pv_arch(_tx_2500())  # rmu_rated_current_a unset -> 630 A fallback
    sheet = sld_sheets(arch)[0]
    stations = [e for e in sheet.elements if e.kind == "station"]
    assert stations and all(e.labels[0].endswith("†") for e in stations)
    assert all(e.tag is not None and not e.tag.endswith("†") for e in stations)  # bare tag
    assert any("stations marked †" in n for n in sheet.notes)
    # The feeder is a different piece of equipment (busbar switchgear) — it
    # is never marked for a station-level fallback.
    feeder = next(e for e in sheet.elements if e.kind == "feeder_breaker")
    assert "†" not in feeder.labels[1]
    # The cable-entry fallback is a separate fact — TX_2500 publishes its own
    # cable entry regardless of its switchgear rating (see the fixture).
    segs = [e for e in sheet.elements if e.kind == "cable_label"]
    assert all("†" not in e.labels[0] for e in segs)
    assert not any("cable entry is published" in n for n in sheet.notes)


def test_no_fallback_design_has_no_dagger_and_no_fallback_note():
    arch = _pv_plant_arch()  # 380 A published switchgear, published cable entry
    sheet = sld_sheets(arch)[0]
    for e in sheet.elements:
        assert all("†" not in line for line in e.labels)
    assert sheet.notes == ["Protection devices are indicative; the tool does not size them."]


def test_cable_entry_fallback_marks_the_segment_and_lists_a_note():
    arch = _small_pv_arch(_tx_no_cable_entry())  # cable entry unset -> 2x300mm^2 fallback
    sheet = sld_sheets(arch)[0]
    segs = [e for e in sheet.elements if e.kind == "cable_label"]
    assert all(e.labels[0].endswith("†") for e in segs)
    assert any("cable entry is published" in n for n in sheet.notes)
    # This fixture's switchgear rating IS published (see the fixture) — no
    # station should be marked.
    stations = [e for e in sheet.elements if e.kind == "station"]
    assert all(not e.labels[0].endswith("†") for e in stations)
    assert not any("stations marked †" in n for n in sheet.notes)


# --- every topology the tool solves (ticket 03) --------------------------------

def _sheets_from_diagram(diagram: dict) -> list[Sheet]:
    """Every sheet of ``diagram``, with ``fleets`` assembled the way
    ``backend.solve.sld_pdf`` does (see ``_sheet_from_diagram``)."""
    inputs = graph_to_inputs(diagram, db)
    stage1s, _layouts, arch = solve_architecture(inputs, db)
    fleets = branches_summary(inputs, arch, stage1s)
    for fleet, extra in zip(fleets, sld_fleets(inputs)):
        fleet.update(extra)
    return sld_sheets(arch, fleets=fleets)


def _stations(sheet: Sheet) -> list:
    return [e for e in sheet.elements if e.kind in ("station", "bess_station")]


def test_several_busbars_give_one_sheet_each_with_plant_wide_tags():
    sheets = sld_sheets(_multi_busbar_arch())
    assert [s.busbar_tag for s in sheets] == ["BB1", "BB2"]
    assert [e.tag for e in sheets[0].elements if e.kind == "feeder_breaker"] == ["C1", "C2"]
    assert [e.tag for e in sheets[1].elements if e.kind == "feeder_breaker"] == ["C3", "C4"]
    ts = [e.tag for s in sheets for e in _stations(s)]
    assert ts == [f"TS{i + 1}" for i in range(18)]  # continues across sheets
    assert len(_stations(sheets[0])) == 10  # circuits 1-2: 5 + 5
    for sheet in sheets:  # each sheet reads on its own: the whole chain to the POC
        assert [e.kind for e in sheet.elements][:1] == ["poc"]
        busbar = next(e for e in sheet.elements if e.kind == "busbar")
        assert busbar.labels[0] == sheet.busbar_tag


def test_hybrid_gives_a_pv_and_a_bess_sheet_both_with_the_shared_poc_and_hv_transformer():
    sheets = _sheets_from_diagram(_hybrid_with_hv_export())
    assert [s.busbar_tag for s in sheets] == ["BB1", "BB2"]
    assert {e.kind for e in _stations(sheets[0])} == {"station"}
    assert {e.kind for e in _stations(sheets[1])} == {"bess_station"}

    def shared(sheet, kind):
        return next(e for e in sheet.elements if e.kind == kind).labels

    for kind in ("poc", "hv_transformer"):
        assert shared(sheets[0], kind) == shared(sheets[1], kind) != []
    # Tags stay plant-wide across the two fleets.
    assert [e.tag for e in sheets[1].elements if e.kind == "feeder_breaker"] == ["C2"]
    assert _stations(sheets[1])[0].tag == f"TS{len(_stations(sheets[0])) + 1}"


def test_mv_interconnection_chain_has_no_hv_transformer():
    arch = _mv_interconnection_arch()
    sheet = sld_sheets(arch)[0]
    kinds = [e.kind for e in sheet.elements]
    assert kinds[:5] == ["poc", "metering", "mv_breaker", "export_cable", "busbar"]
    assert not {"hv_transformer", "hv_breaker", "disconnector"} & set(kinds)
    poc = next(e for e in sheet.elements if e.kind == "poc")
    assert poc.labels[0] == f"{arch.branches[0].sections[0].v_mv_kv:g} kV"


def test_mv_hybrid_draws_each_busbars_own_export_chain():
    sheets = _sheets_from_diagram(_hybrid_with_drawn_bess(p_target_bess_mw=2.0))
    assert len(sheets) == 2
    for sheet in sheets:
        kinds = [e.kind for e in sheet.elements]
        assert "hv_transformer" not in kinds
        assert kinds[:5] == ["poc", "metering", "mv_breaker", "export_cable", "busbar"]


def test_bess_station_labels_pcs_count_and_battery_mwh():
    sheets = _sheets_from_diagram(_hybrid_with_hv_export())
    station = _stations(sheets[1])[0]
    solution = db.bess_solutions["sungrow-st6900ux-4h"]
    containers = db.bess_pairings["GENERIC_BESS_TX_2750_LV069"]["sungrow-st6900ux-4h"]
    assert station.labels[1] == "GENERIC_BESS_TX_2750_LV069"
    assert station.labels[-2] == f"× {containers * solution.pcs_count} sungrow-st6900ux-4h"
    assert station.labels[-1] == f"{containers * solution.e_nominal_kwh / 1000:.2f} MWh"


def test_bess_station_without_fleets_has_no_pcs_or_battery_line():
    sheet = sld_sheets(_bess_plant_arch())[0]
    stations = _stations(sheet)
    assert stations and all(e.kind == "bess_station" for e in stations)
    assert all(len(e.labels) == 3 for e in stations)
    assert "bess_station" in [k for k, _caption in sheet.legend]


def test_feeder_pin_is_read_from_its_own_busbar():
    diagram = _hybrid_with_hv_export()
    bus_b = next(n for n in diagram["nodes"] if n["id"] == "bus_b")
    bus_b["props"]["feeder_switchgear_pins_a"] = {"e_tb1": 800.0}
    pv_sheet, bess_sheet = _sheets_from_diagram(diagram)
    pv_feeder = next(e for e in pv_sheet.elements if e.kind == "feeder_breaker")
    bess_feeder = next(e for e in bess_sheet.elements if e.kind == "feeder_breaker")
    assert bess_feeder.labels[1] == "800 A"
    assert pv_feeder.labels[1] != "800 A"


def test_hybrid_pdf_has_one_page_per_busbar_sheet():
    sheets = _sheets_from_diagram(_hybrid_with_hv_export())
    assert _page_count(build_sld_pdf(sheets)) == 2


# --- auxiliary transformer (drawing only, ticket 04) ---------------------------

@pytest.mark.parametrize("p_kw, q_kvar, expected", [
    (128.0, 0.0, "160 kVA"),        # S / 0.8 exactly 160: that rating
    (128.1, 0.0, "250 kVA"),        # just above: the next rating
    (120.0, 160.0, "250 kVA"),      # Q counts: S = 200, P alone would give 160
    (0.0, 0.0, "50 kVA"),           # smallest rating
    (2000.0, 0.0, "2500 kVA"),      # top of the range
    (2000.1, 0.0, "> 2500 kVA†"),   # above it
    (None, None, "kVA TBD†"),       # unpublished
])
def test_aux_transformer_rating(p_kw, q_kvar, expected):
    assert aux_transformer_rating(p_kw, q_kvar) == expected


def _aux(sheet: Sheet, kind: str) -> list:
    return [e for e in sheet.elements if e.kind == kind]


def test_busbar_without_an_auxiliary_load_has_no_aux_feeder_or_note():
    sheet = _sheet_from_diagram(_pv_diagram_with_hv())
    assert _aux(sheet, "aux_transformer") == [] and _aux(sheet, "load") == []
    assert not [n for n in sheet.notes if "drawing only" in n]


def test_bess_busbar_draws_each_auxiliary_load_on_its_own_feeder():
    pv_sheet, bess_sheet = _sheets_from_diagram(_hybrid_with_hv_export())
    # The PV busbar's own aux node (50 kW + 10 kvar) comes first, plant-wide.
    assert [e.tag for e in _aux(pv_sheet, "aux_transformer")] == ["AUX1"]

    # The BESS busbar's drawn aux node (40 kW + 8 kvar -> S/0.8 = 51 kVA) and
    # its BESS solution's own auxiliaries, which the supplier does not publish.
    txs = _aux(bess_sheet, "aux_transformer")
    assert [e.tag for e in txs] == ["AUX2", "AUX3"]
    assert txs[0].labels == ["AUX2", "100 kVA", "20/0.4 kV"]
    assert txs[1].labels == ["AUX3", "kVA TBD†", "20/0.4 kV"]
    loads = _aux(bess_sheet, "load")
    assert loads[0].labels == ["40 kW"]
    assert loads[1].labels == ["BESS auxiliaries", "kW TBD†"]

    # Each on its own feeder: busbar -> breaker -> AUX transformer -> load.
    by_id = {e.id: e for e in bess_sheet.elements}
    edges = {(c.from_id, c.to_id) for c in bess_sheet.connections}
    for tx, load in zip(txs, loads):
        breaker = next(by_id[a] for a, b in edges if b == tx.id)
        assert breaker.kind == "aux_breaker"
        assert ("busbar", breaker.id) in edges
        assert (tx.id, load.id) in edges
    assert {"aux_transformer", "load"} <= {k for k, _caption in bess_sheet.legend}


def test_aux_notes_list_the_drawing_only_rule_and_each_dagger():
    _pv_sheet, bess_sheet = _sheets_from_diagram(_hybrid_with_hv_export())
    drawing_only = [n for n in bess_sheet.notes if "drawing only" in n]
    assert len(drawing_only) == 1 and "loss calculation" in drawing_only[0]
    assert any("sungrow-st6900ux-4h" in n and "AUX3" in n for n in bess_sheet.notes)


def test_aux_above_the_largest_rating_is_marked_and_noted():
    diagram = _hybrid_with_hv_export()
    aux = next(n for n in diagram["nodes"] if n["id"] == "aux")
    aux["props"].update(p_kw=3000.0, q_kvar=0.0)
    pv_sheet, _bess_sheet = _sheets_from_diagram(diagram)
    tx = _aux(pv_sheet, "aux_transformer")[0]
    assert tx.labels[1] == "> 2500 kVA†"
    assert any("AUX1" in n and "2500 kVA" in n for n in pv_sheet.notes)


# --- title block: project name --------------------------------------------------

def _strings(node) -> list[str]:
    """Every ``String`` shape's text under a ReportLab node — walking the
    in-memory Drawing directly, never parsing rendered PDF bytes."""
    texts: list[str] = []
    for child in getattr(node, "contents", None) or []:
        texts.extend(_strings(child))
    text = getattr(node, "text", None)
    if text is not None:
        texts.append(text)
    return texts


def test_title_block_shows_project_name_when_given():
    sheet = sld_sheets(_pv_plant_arch())[0]
    drawing = sheet_to_drawing(sheet, project_name="Acme Energy", design_name="Test plant")
    texts = _strings(drawing)
    assert "Acme Energy" in texts
    assert "Test plant" in texts


def test_title_block_omits_project_name_when_not_given():
    sheet = sld_sheets(_pv_plant_arch())[0]
    drawing = sheet_to_drawing(sheet, design_name="Test plant")
    texts = _strings(drawing)
    assert "Test plant" in texts
    assert "" not in texts


# --- rendering smoke test -----------------------------------------------------

def _page_count(pdf_bytes: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?!s)", pdf_bytes))


def _media_boxes(pdf_bytes: bytes) -> list[str]:
    return [m.decode() for m in re.findall(rb"/MediaBox\s*\[[^\]]*\]", pdf_bytes)]


def test_standalone_pdf_is_non_empty_a3_landscape_one_page_per_sheet():
    sheets = sld_sheets(_pv_plant_arch())
    pdf = build_sld_pdf(sheets, project_name="Acme Energy", design_name="Test plant")

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000
    assert _page_count(pdf) == len(sheets) == 1

    boxes = _media_boxes(pdf)
    assert len(boxes) == 1
    nums = [float(n) for n in re.findall(r"[\d.]+", boxes[0])]
    width, height = nums[2] - nums[0], nums[3] - nums[1]
    assert width > height  # landscape
    # A3 = 297 x 420 mm; landscape width ~= 1190.6 pt, height ~= 841.9 pt.
    assert width == pytest.approx(1190.55, abs=1.0)
    assert height == pytest.approx(841.89, abs=1.0)
