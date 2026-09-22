"""Tests for the SLD layout model and its rendering (ticket 01: a standalone
single-busbar PV plant with an HV interconnection).

Per the SLD spec, a good test asserts on what a reader of the drawing would
see — tags, counts, order — never on coordinates or drawing primitives. The
architecture fixtures are built through the existing engine entry points, the
same way :mod:`test_architecture` and :mod:`test_pdf_report` do.
"""

import re
import sys

import pytest

sys.path.insert(0, "tests")

from powertool.architecture import (                          # noqa: E402
    BusbarSection,
    arrange_plant,
    size_architecture,
    size_branch,
    size_plant,
)
from powertool.sld import Sheet, build_sld_pdf, sheet_to_drawing, sld_sheets  # noqa: E402

from test_architecture import _catalogue, _full_plant_inputs, _hv_tx, _stage1, _tx_2500  # noqa: E402


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
    # labels carry the tag only, per this ticket's scope
    for eid in station_ids_in_order:
        assert by_id[eid].labels == [by_id[eid].tag]


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


def test_grid_side_chain_elements_carry_no_tag_in_this_ticket():
    # Figure labels land in ticket 02; only TS/C/BB get a tag in ticket 01.
    arch = _pv_plant_arch()
    sheet = sld_sheets(arch)[0]
    chain_kinds = {"poc", "metering", "disconnector", "hv_breaker",
                   "hv_transformer", "export_cable", "mv_breaker"}
    for e in sheet.elements:
        if e.kind in chain_kinds:
            assert e.tag is None
            assert e.labels == []


# --- out of scope: ticket 01 raises rather than draws something wrong --------

def test_hybrid_plant_is_out_of_scope():
    with pytest.raises(ValueError, match="single-fleet"):
        sld_sheets(_hybrid_arch())


def test_bess_fleet_is_out_of_scope():
    with pytest.raises(ValueError, match="PV plants only"):
        sld_sheets(_bess_plant_arch())


def test_multi_busbar_plant_is_out_of_scope():
    with pytest.raises(ValueError, match="single busbar"):
        sld_sheets(_multi_busbar_arch())


def test_mv_interconnection_is_out_of_scope():
    with pytest.raises(ValueError, match="HV interconnection"):
        sld_sheets(_mv_interconnection_arch())


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
