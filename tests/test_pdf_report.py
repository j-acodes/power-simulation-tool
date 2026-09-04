"""Tests for the PDF sizing report — the artefact that stands alone in a design review.

The story (ReportLab's flowable list) is built by a pure function, so these
tests read the text the report will contain without parsing a PDF or shelling
out to an extractor. `build_pdf_report` still runs end to end below, so the
flowables are known to render.
"""

import sys

import pytest

sys.path.insert(0, "tests")

from backend.main import db                                  # noqa: E402
from backend.solve import report_pdf, solve_architecture     # noqa: E402
from powertool.components import conversion_label            # noqa: E402
from powertool.graph import branches_summary, graph_to_inputs  # noqa: E402
from powertool.pdf_report import build_pdf_report, report_story  # noqa: E402

from test_graph import _minimal                              # noqa: E402
from test_hybrid import _bess_only, _hybrid_with_drawn_bess  # noqa: E402


def _hybrid_with_hv_export() -> dict:
    """A hybrid whose two fleets sit under ONE MV/HV transformer and export run.

    The plain hybrid fixture is MV-interconnected, so it has no export step at
    all — which is exactly why the unconditional "shared" annotation slipped
    through review of the fixtures alone.
    """
    diagram = _hybrid_with_drawn_bess(p_target_bess_mw=2.0)
    diagram["settings"]["tiers"]["hv_kv"] = 132.0
    diagram["nodes"].append(
        {"id": "hv", "kind": "hv_tx", "x": 0.0, "y": 0.0,
         "props": {"mode": "auto", "n_parallel": 1}})
    # Re-root both busbars under the transformer, and give the export a length.
    for edge in diagram["edges"]:
        if edge["source"] == "poc" and edge["target"] in ("bus", "bus_b"):
            edge["source"] = "hv"
    diagram["edges"].append(
        {"id": "e_export", "source": "poc", "target": "hv", "tier": "hv",
         "length_m": 1500.0, "sizing": {"mode": "auto"}})
    return diagram


def _story_text(diagram) -> str:
    """Every scrap of text the report would render, as one string."""
    inputs = graph_to_inputs(diagram, db)
    stage1s, _layouts, arch = solve_architecture(inputs, db)
    fleets = branches_summary(inputs, arch, stage1s)
    story = report_story(stage1s, arch, fleets=fleets, plant_name="Test plant",
                         when="2026-09-04 12:00")
    out = []

    def walk(flowables):
        for f in flowables:
            if hasattr(f, "text"):
                out.append(str(f.text))
            for attr in ("_cellvalues", "_content"):
                rows = getattr(f, attr, None)
                if rows:
                    for row in rows:
                        walk(row if isinstance(row, list) else [row])
    walk(story)
    return " ".join(out)


# --- the conversion device is labelled, not renamed --------------------------

def test_conversion_label_is_per_fleet_kind():
    assert conversion_label("bess") == "PCS"
    assert conversion_label("pv") == "inverter"


def test_an_unknown_fleet_kind_reads_as_the_neutral_default():
    # Presentation must never be the thing that raises: a report is the last
    # place to discover an unrecognised kind, and "inverter" is the pre-BESS
    # default the rest of the code already falls back to.
    assert conversion_label("nonsense") == "inverter"


def test_a_bess_report_says_pcs_and_a_pv_report_says_inverter():
    bess = _story_text(_bess_only(duration=4.0))
    assert "PCS" in bess
    pv = _story_text(_minimal())
    assert "inverter" in pv.lower()
    assert "PCS" not in pv


# --- what a BESS design needs to be assessed without the tool open -----------

def test_the_report_carries_containers_and_the_energy_outcome():
    text = _story_text(_bess_only(duration=4.0, p_target_mw=3.0))
    assert "Containers" in text
    assert "8" in text                       # 8 containers at 4 h, from the table
    assert "40.0" in text                    # 40 MWh delivered
    assert "12.0" in text                    # 12 MWh required
    assert "Delivered energy" in text


def test_a_shortfall_is_stated_as_a_shortfall():
    # A design review has to be able to see the verdict, not re-derive it.
    text = _story_text(_bess_only(duration=4.0, p_target_mw=12.0))
    assert "SHORT" in text.upper()


def test_per_fleet_loading_appears_for_each_fleet_of_a_hybrid():
    text = _story_text(_hybrid_with_drawn_bess(p_target_bess_mw=2.0))
    assert text.count("Fleet loading") >= 2


def test_the_two_fleets_of_a_hybrid_are_presented_distinctly():
    text = _story_text(_hybrid_with_drawn_bess(p_target_bess_mw=2.0))
    # Each fleet gets its own named section rather than one merged station table.
    assert "PV fleet" in text
    assert "BESS fleet" in text


def test_a_single_fleet_report_keeps_stage_2_as_one_table():
    """A PV-only report must read exactly as it did before hybrids existed.

    With one fleet the plant IS the fleet, so the plant totals and the fleet's
    own figures belong in one table in their original order. Verified against
    the rendered document when this landed (identical but for the timestamp);
    pinned here on the ordering that made it so, because the property is
    invisible to every other test and would rot silently.
    """
    text = _story_text(_minimal())
    for label in ("LV/MV transformers", "MV circuits", "Fleet loading",
                  "Worst trunk current", "Total cable losses", "Power-balance check"):
        assert label in text, label
    # The fleet's own maximum is a hybrid-only annotation: on a single-fleet
    # report it is noise that was not there before.
    assert "max 100%" not in text
    # One Stage-2 quantity table, not a plant table plus a fleet table.
    assert text.count("Stage 2 results") == 1


def test_a_single_fleet_report_never_calls_a_step_shared():
    """The MV/HV transformer and export cable are listed once and annotated
    "shared" — but only where a second fleet is in fact sharing them.

    Caught in review: the annotation went out unconditionally, so a PV-only HV
    plant read "(MV/HV, shared)" about a step nothing shares, and "Export
    (shared)" no longer fitted its column and wrapped to three lines, detaching
    the row's figures from their label. The fixture this was first checked
    against had no HV export at all, which is why it was missed — so both
    fixtures are exercised here.
    """
    from test_graph import _hv_diagram
    for diagram in (_minimal(), _hv_diagram(), _bess_only(duration=4.0)):
        assert "shared" not in _story_text(diagram)

    # A hybrid with a real export step genuinely does share it, and says so.
    assert "shared" in _story_text(_hybrid_with_hv_export())


def test_a_pv_only_report_has_no_bess_sections():
    text = _story_text(_minimal())
    for absent in ("Containers", "Delivered energy", "BESS fleet"):
        assert absent not in text, absent


# --- the endpoint no longer refuses a hybrid --------------------------------

def test_a_hybrid_design_now_produces_a_pdf():
    # Ticket 07 made this a deliberate 400 rather than a report describing one
    # fleet and silently omitting the other. This ticket is what lifts it.
    pdf = report_pdf(_hybrid_with_drawn_bess(p_target_bess_mw=2.0), db, "Hybrid plant")
    assert pdf[:4] == b"%PDF"


def test_a_single_fleet_design_still_produces_a_pdf():
    assert build_pdf_report(
        *_render_args(_minimal()), plant_name="PV plant")[:4] == b"%PDF"


def _render_args(diagram):
    inputs = graph_to_inputs(diagram, db)
    stage1s, _layouts, arch = solve_architecture(inputs, db)
    return stage1s, arch


def test_build_pdf_report_needs_the_fleet_figures_to_report_them():
    # fleets is optional so the engine-level callers in tests/ keep working, but
    # a report built without it simply omits the per-fleet sections rather than
    # inventing them.
    stage1s, arch = _render_args(_bess_only(duration=4.0))
    assert build_pdf_report(stage1s, arch, plant_name="No fleets")[:4] == b"%PDF"
