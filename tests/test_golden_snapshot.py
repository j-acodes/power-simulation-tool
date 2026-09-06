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

from powertool.database import ComponentDatabase

from golden_snapshot import BASELINE, build_snapshot, _serialise


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
