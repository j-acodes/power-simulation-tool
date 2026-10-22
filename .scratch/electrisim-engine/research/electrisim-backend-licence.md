# Electrisim backend licence

Researched 2026-10-22. Not legal advice. Sources are GitHub API / raw files and PyPI metadata read on that date.

## Findings

1. **The upstream backend repo has no LICENSE file and GitHub detects no licence.**
   `gh api repos/electrisim/appElectrisimBackend` returns `license: null`; the repo root and the full git tree contain no LICENSE/NOTICE/COPYING file; no commit ever touched a `LICENSE` path.
   https://github.com/electrisim/appElectrisimBackend
2. **But the backend README claims Apache-2.0.** Its "License" section says "This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file", and the intro calls Electrisim "open-source". The linked file does not exist. The fork's `backend/README.md` (line 458-460) carries the same text.
   https://github.com/electrisim/appElectrisimBackend/blob/main/README.md
3. **The frontend repo is Apache-2.0 with a LICENSE file** (GitHub detects `Apache-2.0`; README repeats it). The LICENSE is the unfilled stock text: the appendix still reads `Copyright {yyyy} {name of copyright owner}`, so no named copyright holder or year.
   https://github.com/electrisim/appElectrisimFrontend (LICENSE, README)
4. **No organisation.** `electrisim` is a GitHub *user* account (name "Electrisim", blog electrisim.com, 3 public repos: backend, frontend, `lite191svgjs`). Org endpoints return 404. Backend licence: none detected; frontend: Apache-2.0; `lite191svgjs`: none.
5. **No per-file licence headers** in the backend files sampled (`app.py`, `pandapower_electrisim.py`, `opendss_electrisim.py`). The local fork (`power-sim-upgrade/rea-power-system-sim/backend`) has no licence file either.

## Interpretation (the unknown part)

Legally, code with no licence file is "all rights reserved" by default. The README statement is a clear, public statement of intent to use Apache-2.0, and the sister repo does ship Apache-2.0, so Apache-2.0 is the most probable intended licence. But the grant is not backed by a licence text in the repo, the copyright holder is unnamed, and I cannot say whether a README line alone is enough to be enforceable or relied on. **Unknown. A lawyer, or a written confirmation (or an added LICENSE file) from the author, would settle it.** Cheapest fix: open an issue/email asking the owner to add the LICENSE file.

## Verdict per path

### (a) Reading as a reference: OK, high confidence
Reading public source and learning from it, without copying, needs no licence grant. Obligations: none. (Copying expression, not just ideas, is where licensing starts to matter.)

### (b) Copying modules into a proprietary internal tool: conditionally OK, medium-low confidence
- **If Apache-2.0 applies (as the README states):** permitted, including for proprietary and commercial use, with no copyleft. Obligations (Apache-2.0 s.4): include a copy of the licence; keep copyright/attribution notices; mark files you changed; carry any upstream NOTICE file (none exists in either repo); patent grant comes with it. Source need not be released. Internal-only use triggers few redistribution duties anyway.
- **If the README is not a valid grant:** default copyright applies and copying is not permitted without the owner's consent.
- Risk reducer: get the owner to add a LICENSE file naming the copyright holder, or obtain written permission. Keep a note of the README text and commit hash you copied from.
- Per-module caution: the code imports third-party engines with their own terms (see below); copying a module that imports `andes_electrisim` pulls in ANDES's licence consequences.

### (c) Depending directly on pandapower and lightsim2grid: OK, high confidence
- **pandapower:** BSD-3-Clause (LICENSE file; PyPI classifier BSD; GitHub shows NOASSERTION only because of the copyright block formatting). Copyright University of Kassel, Fraunhofer IEE and contributors. Obligations: keep the copyright notice, conditions and disclaimer when redistributing source or binaries (a notices file for shipped binaries); do not use the authors' names to endorse. No copyleft. Internal use: effectively none.
  https://github.com/e2nIEE/pandapower/blob/develop/LICENSE
- **lightsim2grid:** MPL-2.0 (LICENSE.md; GitHub detects MPL-2.0). File-level weak copyleft: if you modify lightsim2grid's own MPL files and distribute them, those modified files must be offered under MPL-2.0. Using it unmodified as an installed dependency from proprietary code imposes no obligation on your code. Internal-only use: no distribution, so no obligation. If you ship a product that bundles it, keep its licence text and tell recipients where the source is. It optionally links SuiteSparse KLU and Eigen (own licences, not examined here; check if you build or ship binaries yourself).
  https://github.com/Grid2op/lightsim2grid/blob/master/LICENSE.md
- Electrisim pins `pandapower==3.3.2` and `lightsim2grid==1.0.0`; PyPI now has 3.5.6 and 1.2.0. Licences of those PyPI releases are the same families (BSD / MPL-2.0 classifiers).

## Other dependencies in upstream `requirements.txt` (flagged, not asked)
Upstream backend requires: Flask, flask-cors, gunicorn, pandapower, lightsim2grid, matplotlib, pandas, numpy, numba, opendssdirect.py, arcflash-calc, pint, andes, opender.
- **andes: GPL-3.0-or-later** (PyPI classifier; GitHub LICENSE text is GPLv3 "or any later version"; `pyproject.toml` `GPL-3.0-or-later`). This is strong copyleft. Importing it into a program that you distribute may make the combined work GPL; purely internal, undistributed use does not trigger distribution duties, but a hosted service or any hand-over to a third party needs a lawyer's view. Safest for a proprietary tool: do not depend on or copy `andes_electrisim.py` (the ANDES path, `app.py` lines ~872-908 in the fork).
  https://github.com/curent/andes/blob/master/LICENSE
- **opendssdirect.py:** custom BSD-style licence (NREL/Alliance for Sustainable Energy notice). It contains a clause (item 3) that research entities redistributing must publish source under the same licence; PyPI marks it "Other/Proprietary". Read the full text before shipping. The OpenDSS engine itself is a separate EPRI licence, not checked.
  https://github.com/dss-extensions/OpenDSSDirect.py/blob/master/LICENSE
- **opender:** PyPI classifier BSD. **arcflash-calc:** PyPI classifier MIT. Not checked against source repos.

## Sources
- https://github.com/electrisim/appElectrisimBackend (+ `gh api repos/electrisim/appElectrisimBackend`, git tree, commits-by-path)
- https://github.com/electrisim/appElectrisimFrontend (LICENSE, README)
- https://github.com/electrisim (user profile, repo list)
- https://github.com/e2nIEE/pandapower/blob/develop/LICENSE
- https://github.com/Grid2op/lightsim2grid/blob/master/LICENSE.md
- https://github.com/curent/andes (LICENSE, pyproject.toml); https://pypi.org/project/andes/
- https://github.com/dss-extensions/OpenDSSDirect.py/blob/master/LICENSE
- https://pypi.org/project/opender/ , https://pypi.org/project/arcflash-calc/
- Apache-2.0 text: https://www.apache.org/licenses/LICENSE-2.0 ; MPL-2.0: https://www.mozilla.org/MPL/2.0/
- Local fork (read-only): C:\Users\JavierAguilar\my-projects\power-sim-upgrade\rea-power-system-sim\backend
