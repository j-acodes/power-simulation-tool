"""The engine still produces the numbers it produced before.

This is the one test that asserts figures nobody chose to assert. It exists
because the suite's other tests pin what someone thought to pin, and a refactor
moves what nobody thought of.

It was a manual script for most of its life — captured from a worktree, diffed
by hand, run only when someone remembered. That is how it went nine fixtures
deep on PV-only designs and stayed blind to every BESS change for a whole
feature. Being a real test is the point: it now runs whether or not anyone
remembers it.
"""
import json
import math

from powertool.architecture import arrange_plant, size_circuits
from powertool.database import ComponentDatabase
from powertool.sizing import SizingResult

from golden_snapshot import BASELINE, build_snapshot, _serialise


def test_hand_computed_anchor_before_regenerating_the_baseline():
    """Pin one design's circuit count and trunk through current, computed BY
    HAND from the catalogue before the baseline below is trusted to move
    under it (ADR-0006: circuit grouping now reads each station's own
    switchgear rated current, not the retired flat 400 A cap).

    Design: 16 identical SUNGROW_MVS3200 stations (catalogue: s_rated_kva_at_40c
    3200, pk_kw 32.0, p0_kw 3.2, uk_percent 8.0, i0_percent 0.0,
    rmu_rated_current_a 630 — PUBLISHED, from the ``sungrow_common`` YAML
    anchor, not the ADR-0006 fallback) carrying a unity-PF Stage-1 output of
    38,400 kW / 0 kvar, split evenly: 2,400 kW / 0 kvar LV share each.

    Per-station transformer loss at that share (Transformer.losses, ur/ux
    split from uk and pk):
      ur% = 100 * pk / s_rated = 100 * 32.0 / 3200 = 1.0
      ux% = sqrt(uk% ** 2 - ur% ** 2) = sqrt(8.0**2 - 1.0**2) = sqrt(63) = 7.937254 (6 dp)
      load_ratio_sq = (2400 / 3200) ** 2 = 0.5625
      dP = pk * load_ratio_sq + p0 = 32.0 * 0.5625 + 3.2 = 18.0 + 3.2 = 21.2 kW
      dQ = (ux% / 100) * s_lv**2 / s_rated + 0  (i0% = 0)
         = 0.07937254 * 2400**2 / 3200 = 0.07937254 * 1800 = 142.870572 kvar (6 dp)

    Station MV-side output (forward power flow, losses subtracted):
      P_mv = 2400 - 21.2 = 2378.8 kW
      Q_mv = 0 - 142.870572 = -142.870572 kvar
      S_mv = hypot(2378.8, 142.870572) = 2383.086536 kVA (6 dp)
      I_station = S_mv / (sqrt(3) * 20) = 2383.086536 / 34.641016 = 68.793783 A (6 dp)

    Circuit grouping (assign_circuits, ADR-0006): packing bounds each circuit
    by the NOMINAL station currents (never the real, loss-reduced through
    current, which downstream cable losses only ever reduce). 16
    stations draw 16 * 68.793783 = 1100.700528 A, so the lower bound is
    ceil(1100.700528 / 630) = 2 circuits of 8, each 8 * 68.793783 =
    550.350264 A — inside the published 630 A rating. The retired 400 A cap
    allows at most 5 stations (5 * 68.793783 = 343.968913 A; 6 would be 412.76 A),
    so 3 circuits cannot hold 16 and it needed [4, 4, 4, 4]: this anchor is
    chosen so the two rules disagree.

    Trunk through current (position 1, nearest the substation): the REAL
    segment-walk figure, the eight station outputs less the series losses of
    the 7 spans downstream of the trunk (spans 2-8, cables as the selector
    chose them at 0.5 km trunk / 0.2 km spacing):
      sum dP = 14.544646 + 7.883582 + 7.047718 + 7.250591 + 6.728368
               + 4.650095 + 1.163080 = 49.268080 kW
      sum dQ = 7.483667 + 9.574376 + 6.863742 + 4.667568 + 2.857707
               + 1.396391 + 0.349265 = 33.192716 kvar
      P = 8 * 2378.8 - 49.268080 = 18981.131920 kW
      Q = 8 * -142.870572 - 33.192716 = -1176.157292 kvar
      I_trunk = hypot(P, Q) / (sqrt(3) * 20) = 19017.537036 / 34.641016
              = 548.989006 A  (below the 550.350264 A nominal packing bound)
    """
    tx = ComponentDatabase.load().transformer("SUNGROW_MVS3200")
    assert tx.s_rated_kva_at_40c == 3200
    assert tx.pk_kw == 32.0 and tx.p0_kw == 3.2
    assert tx.uk_percent == 8.0 and tx.i0_percent == 0.0
    assert tx.rmu_rated_current_a == 630.0  # PUBLISHED, not the fallback
    assert tx.switchgear_rated_current_a == 630.0

    stage1 = SizingResult(
        p_poc_kw=0.0, q_poc_kvar=0.0, pf_target=1.0,
        p_inv_kw=38_400.0, q_inv_kvar=0.0, s_inv_kva=38_400.0,
        pf_inv=1.0, losses=[], power_balance_ok=True,
    )
    layout = arrange_plant(
        stage1, [(tx, 16)],
        trunk_length_km=0.5, spacing_km=0.2, v_mv_kv=20.0,
    )
    assert layout.circuit_sizes == [8, 8]  # the retired 400 A cap gave [4, 4, 4, 4]

    plan = layout.circuit_plans[0][0]
    assert abs(plan.p_mv_kw - 2378.8) < 1e-6
    assert abs(plan.i_a - 68.793783) < 1e-6

    cables = ComponentDatabase.load().cables_for_voltage(20.0)
    circuits = size_circuits(layout, cables)
    nominal_bound = 8 * plan.i_a  # == 550.350264 A, the packing ceiling used above
    assert abs(nominal_bound - 550.350264) < 1e-5
    assert nominal_bound > 400.0  # would not fit under the retired cap
    spans = circuits[0].segments[1:]
    assert abs(sum(sg.dp_kw for sg in spans) - 49.268080) < 1e-5
    assert abs(sum(sg.dq_series_kvar for sg in spans) - 33.192716) < 1e-5
    for circuit in circuits:
        assert abs(circuit.i_trunk_a - 548.989006) < 1e-5
    assert circuits[0].i_trunk_a == circuits[1].i_trunk_a  # identical circuits


def _differences(expected, actual, path="") -> list[str]:
    """Every leaf path where two snapshots disagree, as readable strings.

    A whole-blob equality check reports "these two 200 KB strings differ",
    which tells you nothing about what moved. This names the figures.
    """
    if isinstance(expected, dict) and isinstance(actual, dict):
        out = []
        for key in sorted(set(expected) | set(actual)):
            here = f"{path}.{key}" if path else str(key)
            if key not in expected:
                out.append(f"{here}: added, now {actual[key]!r}")
            elif key not in actual:
                out.append(f"{here}: removed, was {expected[key]!r}")
            else:
                out += _differences(expected[key], actual[key], here)
        return out
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{path}: length {len(expected)} -> {len(actual)}"]
        out = []
        for i, (e, a) in enumerate(zip(expected, actual)):
            out += _differences(e, a, f"{path}[{i}]")
        return out
    return [] if expected == actual else [f"{path}: {expected!r} -> {actual!r}"]


def test_the_engine_still_produces_the_captured_numbers():
    expected = json.loads(BASELINE.read_text())
    actual = json.loads(_serialise(build_snapshot(ComponentDatabase.load())))

    diffs = _differences(expected, actual)
    assert not diffs, (
        f"{len(diffs)} value(s) moved against tests/golden_baseline.json:\n  "
        + "\n  ".join(diffs[:40])
        + ("\n  …" if len(diffs) > 40 else "")
        + "\n\nIf the change is intended, regenerate and READ the diff:\n"
        "  .venv/bin/python -m tests.golden_snapshot\n"
        "  git diff tests/golden_baseline.json"
    )


def test_the_snapshot_would_notice_a_change():
    """The baseline is compared, not merely loaded.

    A snapshot test that passes against anything is worse than none, because it
    reports safety it does not provide — which is exactly the failure this file
    was rescued from. So: perturb one captured figure and require the
    comparison to object.
    """
    expected = json.loads(BASELINE.read_text())
    perturbed = json.loads(json.dumps(expected))
    perturbed["bess_3mw_4h_tx4000"]["results"]["summary"]["branches"][0]["e_delivered_kwh"] = 1.0

    diffs = _differences(expected, perturbed)
    assert diffs, "the comparison cannot see a changed figure"
    assert any("e_delivered_kwh" in d for d in diffs)
