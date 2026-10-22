# What reactive-power envelopes do the target markets require at the POC?

**Type:** research
**Status:** open
**Blocked by:** None

## Question

For Spain, Portugal, Poland, France, Croatia, Italy and Germany: which document sets the
reactive-power requirement at the connection point for PV and BESS power park modules
(by NC RfG type B/C/D and connection voltage), and what are the P-Q envelope and U-Q
envelope values (Q/Pmax limits against P and against voltage, voltage bands, any
storage-specific or import-mode rule)? Name document, version and clause for each.

Then compare against Electrisim's templates in
`rea-power-system-sim/frontend/src/main/webapp/js/electrisim/dialogs/RPCDialog.js`
(P-Q ~lines 9–170, U-Q ~177–220): which markets are present, which match the sources, and
which are missing (Portugal, France and Croatia were not seen when charting).
