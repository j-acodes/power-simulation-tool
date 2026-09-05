# 07: Warn when a solution publishes no auxiliary consumption

**What to build:** A sizing engineer using a product whose datasheet omits auxiliary consumption
is told so — where they pick it, and again where it would have counted — without being blocked.

Sungrow's PowerTitan 3.0 datasheet publishes no auxiliary consumption figure anywhere on the page.
The **auxiliary load** attached to a BESS busbar is therefore understated by that station's worth
of draw, silently, and the engineer has no way to know.

A solution without a published figure stores zero and raises an **informational** notice. This is
a new severity, distinct from the errors already raised for an unknown solution or an LV mismatch:
nothing fails, nothing is blocked, and a design carrying this notice still solves and still passes
compliance. A gap in a supplier's datasheet is not the engineer's error.

The notice appears in two places, deliberately. In the specification view, so the engineer sees it
before choosing the product. And in design validation, so it follows the understated figure into
the busbar auxiliary load rather than only appearing where it was first read.

**Blocked by:** 01 (Reshape the BESS solution around a declared discharge duration), 04 (Read a
component's full specification full-screen).

**Status:** ready-for-agent

- [ ] Design validation carries an informational severity, distinct from the existing errors
- [ ] A design using a solution with no published auxiliary consumption raises an informational
      notice naming the solution
- [ ] That design still solves, still passes compliance, and is not blocked in any way
- [ ] The specification view says when a solution publishes no auxiliary consumption
- [ ] A solution that does publish auxiliary consumption raises no notice
- [ ] An existing error-severity issue is still reported as an error and still fails the design
