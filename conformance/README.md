# Conformance suite

This directory is the conformance suite for spec `loop/v0.1`.

## Layout

```
conformance/
  golden/              # schema-level corpus (milestone m1)
    changeset/
      valid/           # every file MUST validate against the schema
      invalid/         # REQUIRED-FAILURE: every file MUST fail validation
    evidence/          # same valid/invalid split
    policy/
    journal-entry/
    registry/
  cases/               # executor-level golden cases (milestone m2)
  driver/              # subprocess driver interface for ANY executor (milestone m2)
```

## Schema-level check (m1)

`make check-schemas` runs `agentloop check-schemas --golden conformance/golden`. It:

1. Compiles the five normative schemas in `spec/schemas/`.
2. Validates every file under `*/valid/`. One failure fails the run.
3. Validates every file under `*/invalid/`. These are REQUIRED-FAILURE
   cases: if one of them PASSES validation, the run fails. This proves
   the schemas reject what they must reject.

Instance files are JSON (`.json`) or YAML (`.yaml`), matching how each
object lives on disk: ChangeSet, Evidence, and Journal entries are JSON;
Policy and Registry are YAML.

## Executor-level suite (m2, skeleton)

The executor suite drives ANY executor through a small subprocess
contract: known ChangeSets in, expected journal out. The reference CLI
must pass; a deliberately broken executor stub must fail. Defined at
milestone m2.
