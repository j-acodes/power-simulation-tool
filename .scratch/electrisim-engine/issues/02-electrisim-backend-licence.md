# Under what licence is Electrisim's backend published?

**Type:** research
**Status:** resolved
**Blocked by:** None

## Question

The fork's frontend carries Apache-2.0 (`frontend/LICENSE`); the backend folder has no
licence file. Upstream is `electrisim/appElectrisimBackend` on GitHub. What licence (if
any) covers the backend code, and what does it permit for (a) reading it as a reference,
(b) copying modules into a proprietary internal company tool, (c) depending on
pandapower (BSD-3) and lightsim2grid (MPL-2.0) directly? Note obligations (attribution,
NOTICE, copyleft) for each path.

## Answer

Upstream `electrisim/appElectrisimBackend` (a personal GitHub account) has **no LICENSE
file** — GitHub reports none, and none appears in its tree or history. Its README says "Apache
License 2.0 - see LICENSE", pointing at a file that does not exist. The frontend's Apache-2.0
LICENSE is genuine, though it is the unfilled template.

- **(a) Read as a reference:** fine, no obligations.
- **(b) Copy modules into this tool:** fine only if the README's Apache-2.0 statement counts
  as a grant; otherwise default copyright applies and copying needs the owner's
  permission. Cheapest fix: ask the owner to add the LICENSE file or confirm in writing.
  If confirmed, keep the licence text and notices and mark changes.
- **(c) Depend on pandapower (BSD-3) / lightsim2grid (MPL-2.0):** fine for internal,
  unmodified use; BSD needs notice retention on redistribution, and MPL is file-level
  copyleft only.
- **Flag:** `andes` is GPL-3.0-or-later; do not depend on it or copy
  `andes_electrisim.py` (already out of scope). Read `opendssdirect.py`'s custom BSD-style
  licence before any use.

Not legal advice. Detail and sources: branch `research/electrisim-backend-licence`,
`.scratch/electrisim-engine/research/electrisim-backend-licence.md`.
