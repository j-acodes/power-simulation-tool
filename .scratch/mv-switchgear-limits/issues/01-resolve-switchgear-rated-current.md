# 01: Resolve a station's switchgear rated current, with a fallback for silence

**What to build:** every transformer station resolves a switchgear rated current that the
engine can read. A station whose supplier publishes the figure resolves to it. A station whose
supplier does not resolves to the standard 630 A ring-main-unit size and raises a notice naming
the station and saying the figure was defaulted, not published. Silence never resolves to "no
limit". The specification view presents the figure as one the engine reads rather than as a
transcribed supplier fact.

Nothing enforces the limit yet — this ticket only makes it available and honest about its
provenance.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] `rmu_rated_current_a` is a simulated parameter on the transformer station; the rest of the
      RMU block stays typed.
- [x] The five Sungrow MVS PV stations and both real BESS stations resolve to their published
      630 A.
- [x] All three Huawei JUPITER stations resolve to 630 A and each raises a fallback notice.
- [x] The 630 A fallback constant lives in the engine, not in any YAML file.
- [x] A resolved rating reports whether it was published or defaulted.
- [x] Prior art followed: the notice reads like
      `test_missing_30c_inverter_power_falls_back_to_40c_with_notice`.
- [x] `tests/test_catalogue.py` covers published, unpublished and provenance.
- [x] The full Python suite passes. `golden_baseline.json` moves only by the ten new fallback
      notices it now captures — the diff contains no numeric movement, which is what "no number
      moves" was asking for. Verified by reading the diff.
