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

## Executor-level suite (m2)

`make conformance` runs `conformance/runner.py` against the reference
CLI. The runner drives ANY executor through a subprocess contract and
inspects only the file plane afterwards — it never imports executor code.

### The subprocess contract

Every invocation is `<executor-cmd> -C <workspace> <verb> [args...]`,
run with the workspace as the working directory.

| Verb | Exit codes |
|---|---|
| `init` | 0 scaffolded |
| `propose (--from-dir D \| --layer L --target T... --patch F --rationale R --producer P --id ID)` | 0 validated, 1 rejected |
| `evidence <id> --record F [--artifact F]` | 0 attached |
| `gate <id>` | 0 approved, 1 rejected, 2 queued |
| `apply <id>` | 0 applied, 1 rejected/failed |
| `approve <id> --actor A` | 0 applied, 1 refused |
| `reject <id> --actor A [--reason R]` | 0 rejected |
| `rollback <id> [--actor A]` | 0 rolled back |
| `verify [path]` | 0 intact, 1 problems found |
| `log --json` | 0; one JSON journal entry per line |

### Case format

`cases/<id>/case.yaml` plus a `files/` dir that seeds a fresh temp
workspace. Steps run in order:

- `run: [verb, args...]` with optional `expect_exit` (default 0);
  `{case}` in an argument expands to the case directory.
- `expect_file: {path, equals|contains|not_contains|absent}` checks the
  file plane mid-run.
- `edit_file: {path, find, replace}` simulates out-of-band tampering
  (globs allowed), for the T4/T6-style cases.

At the end the runner compares the journal's full event sequence to
`expected_events` and, unless `final_verify: false`, requires `verify`
to exit 0.

### Negative test (D2)

`conformance/stubs/broken_executor.py` speaks the contract but skips
gates, queues nothing, and journals without a hash chain. The suite MUST
fail it; `tests/test_conformance.py` asserts both directions.
