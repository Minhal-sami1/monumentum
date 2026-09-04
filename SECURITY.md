# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |

## Reporting a vulnerability

Report privately. Use GitHub's **Report a vulnerability** form on this
repository's Security tab. Do not open a public issue for a security report.

You will get an acknowledgement within 7 days. Please include the version,
a minimal reproduction, and the invariant you believe is broken.

## What counts as a vulnerability

Monumentum's security contract is its six invariants (spec §11). A report
is in scope if it shows any of these can be violated by a Producer, a
pulled ChangeSet, or file-plane tampering:

- **I1** — a ChangeSet that targets `.monumentum/**`, or a policy change that is not human-only and journaled
- **I2** — an edit or deletion in the journal that `monumentum verify` does not detect
- **I3** — an L2/L3 application without an `independent` evidence record
- **I4** — a target outside `targets_allow` that passes validation
- **I5** — an applied ChangeSet that cannot be rolled back to exact prior content
- **I6** — a Distributor serving, or an executor accepting, an unsigned or badly signed ChangeSet

Also in scope: the PreToolUse guard failing to deny an edit to a managed
target; a `reproducible_check` that can be satisfied without the recorded
outcome.

## Out of scope

Governed-profile features (transparency log, Rego gates, audit export) are
specified but not implemented in v1. Reports against them are design
feedback, not vulnerabilities; open an issue.
