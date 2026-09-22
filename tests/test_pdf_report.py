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
from powertool.graph import branches_summary, fallback_notices, graph_to_inputs  # noqa: E402
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
                         when="2026-09-04 12:00",
                         feeders_per_busbar=inputs.feeders_per_busbar,
                         notices=[n.message for n in fallback_notices(arch)])
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
    # sungrow-st6900ux-4h: 1 container at its declared 4 h duration, 6904 kWh.
    text = _story_text(_bess_only(duration=4.0, p_target_mw=1.0))
    assert "Containers" in text
    assert "6.9 MWh (needs 4.0 MWh) — OK" in text
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


def test_the_report_states_the_feeders_per_busbar_limit():
    # ADR-0007, ticket 06: the Stage-1 planning rule is carried through for
    # display, default and overridden alike.
    text = _story_text(_minimal())
    assert "Feeders per busbar limit" in text
    assert "12" in text

    diagram = _minimal()
    diagram["settings"]["rules"]["feeders_per_busbar"] = 6
    text = _story_text(diagram)
    assert "Feeders per busbar limit" in text
    assert "6" in text


def test_the_report_lists_the_sized_busbar_switchgear():
    # ADR-0007: the busbar, export switchgear and each feeder, sized rating
    # beside its current.
    text = _story_text(_minimal())
    assert "Busbar switchgear" in text
    assert "Export switchgear" in text
    assert "Circuit 1 feeder" in text
    assert "630 A (sized)" in text


def test_a_pinned_busbar_switchgear_rating_is_marked_pinned_not_sized():
    # ADR-0007, ticket 04: a pinned rating is reported exactly as pinned, and
    # the still-unpinned parts (export switchgear, the feeder) keep reading
    # as sized.
    diagram = _minimal()
    diagram["nodes"][1]["props"]["busbar_switchgear_pin_a"] = 800.0
    text = _story_text(diagram)
    assert "800 A (pinned)" in text
    assert "630 A (sized)" in text  # export switchgear and the feeder


def test_the_report_names_the_circuits_binding_limit():
    # Ticket 07: the default catalogue's station switchgear fallback binds,
    # named beside the feeder row it decided the size of.
    text = _story_text(_minimal())
    assert "Binding limit" in text
    assert "Station switchgear" in text


def test_the_report_lists_each_stations_through_and_rated_current():
    # Ticket 07: through current beside switchgear rated current, per station
    # — a figure _transformer_rows aggregates away by model.
    text = _story_text(_minimal())
    assert "93 / 630 A" in text  # s1's through current (~92.9 A) / 630 A fallback


def test_the_report_lists_every_fallback_notice():
    # The default catalogue publishes neither switchgear rated current nor
    # cable entry, so both fallbacks are used and both are stated.
    text = _story_text(_minimal())
    assert "Notices" in text
    assert "No switchgear rated current is published" in text
    assert "No cable entry is published" in text


def test_the_report_shows_feeders_used_against_the_limit():
    # Ticket 07: feeder count vs. the feeders-per-busbar rule, and the
    # busbar's own current against the 4,000 A ladder top.
    text = _story_text(_minimal())
    assert "1 / 12" in text
    assert "4,000 A" in text


def test_a_busbar_switchgear_section_appears_for_each_fleet_of_a_hybrid():
    text = _story_text(_hybrid_with_drawn_bess(p_target_bess_mw=2.0))
    assert text.count("Busbar switchgear") >= 2


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


# --- the SLD sheets embedded after the summary (SLD export, ticket 06) -------

def _sld_story(diagram) -> list:
    """The report story with the design's SLD sheets, built the way the
    endpoint builds them — the same sheets the standalone download renders."""
    from backend.solve import design_sld_sheets
    inputs = graph_to_inputs(diagram, db)
    stage1s, _layouts, arch = solve_architecture(inputs, db)
    fleets = branches_summary(inputs, arch, stage1s)
    return report_story(stage1s, arch, fleets=fleets, plant_name="Test plant",
                        notices=[n.message for n in fallback_notices(arch)],
                        sld_sheets=design_sld_sheets(inputs, arch, fleets))


def _sld_placement(story) -> tuple[list[int], list[str], int, int]:
    """Indices of the drawings, the caption text right after each, and the
    indices of the last summary/notice flowable and the Methodology heading."""
    from reportlab.graphics.shapes import Drawing
    drawings = [i for i, f in enumerate(story) if isinstance(f, Drawing)]
    captions = [str(getattr(story[i + 1], "text", "")) for i in drawings]
    methodology = next(i for i, f in enumerate(story)
                       if str(getattr(f, "text", "")) == "Methodology")
    summary = next(i for i, f in enumerate(story)
                   if str(getattr(f, "text", "")) == "Plant summary")
    return drawings, captions, summary, methodology


def test_the_report_embeds_each_sld_sheet_after_the_summary_with_a_caption():
    story = _sld_story(_minimal())
    drawings, captions, summary, methodology = _sld_placement(story)
    assert len(drawings) == 1
    assert summary < drawings[0] < methodology
    assert "Sheet 1" in captions[0] and "BB1" in captions[0]
    assert "Download SLD" in captions[0]


def test_a_hybrid_report_embeds_one_sheet_per_busbar():
    story = _sld_story(_hybrid_with_drawn_bess(p_target_bess_mw=2.0))
    drawings, captions, summary, methodology = _sld_placement(story)
    assert len(drawings) == 2
    assert all(summary < d < methodology for d in drawings)
    assert ["BB1" in captions[0], "BB2" in captions[1]] == [True, True]


def test_the_embedded_sheets_come_after_the_notices():
    story = _sld_story(_minimal())
    notices = [i for i, f in enumerate(story) if str(getattr(f, "text", "")) == "Notices"]
    drawings, *_ = _sld_placement(story)
    assert all(n < drawings[0] for n in notices)


def test_an_embedded_sheet_fits_the_a4_text_width_and_stays_vector():
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.pagesizes import A4
    from powertool.pdf_report import _MARGIN
    story = _sld_story(_minimal())
    drawing = next(f for f in story if isinstance(f, Drawing))
    assert drawing.width == pytest.approx(A4[0] - 2 * _MARGIN)
    assert drawing.height < drawing.width      # still landscape


def test_the_report_pdf_carries_the_sld_page():
    pdf = report_pdf(_hybrid_with_drawn_bess(p_target_bess_mw=2.0), db, "Hybrid plant")
    assert pdf[:4] == b"%PDF"


def test_the_embedded_sheet_carries_the_project_name_in_its_title_block():
    from reportlab.graphics.shapes import Drawing, String
    from backend.solve import design_sld_sheets
    inputs = graph_to_inputs(_minimal(), db)
    stage1s, _layouts, arch = solve_architecture(inputs, db)
    fleets = branches_summary(inputs, arch, stage1s)
    story = report_story(stage1s, arch, fleets=fleets, plant_name="Test plant",
                         project_name="Acme Energy Co",
                         sld_sheets=design_sld_sheets(inputs, arch, fleets))
    drawing = next(f for f in story if isinstance(f, Drawing))

    def texts(node):
        for c in getattr(node, "contents", []):
            if isinstance(c, String):
                yield c.text
            yield from texts(c)
    assert "Acme Energy Co" in set(texts(drawing))
