# REPRODUCE.md — regenerate every number

No quantitative value in the paper is hand-written. Each one is produced by a
script from run logs, aggregated into `experiments/results/metrics.json`, and
rendered into LaTeX macros the paper `\input`s. `paper/check_no_hardcoded.py`
fails the build if a metric-shaped literal appears in the paper prose.

## One command

```
make setup
make reproduce      # re-runs every experiment, regenerates metrics + figures
make paper          # builds paper/build/loop-paper.pdf from the generated tables
```

`make reproduce` clears `experiments/*/logs/` first, so results always come
from the current run, never from stale files.

## What runs, and what each produces

| Step | Script | Logs | Metrics |
|---|---|---|---|
| Interop demo | `demo/run_demo.py` | `experiments/interop/logs/` | lesson-to-second-runtime seconds |
| Scenarios UC1–UC5 | `scenarios/run_all.sh` | `experiments/scenarios/logs/` | per-scenario timings; UC3 fleet propagation |
| Adversarial T1–T6 + control | `adversarial/run_all.sh` | `experiments/adversarial/logs/` | detection outcomes |
| Overhead + evidence rate | `experiments/experiments.py` | `experiments/overhead/logs/`, `experiments/evidence/logs/` | added wall time and context per change; evidence-carrying rate loop vs baseline |
| Skill trigger rate (opt-in) | `experiments/trigger/run_trigger.py` | `experiments/trigger/logs/` | propose-rate over headless sessions |
| Aggregation | `experiments/metrics.py` | — | `experiments/results/metrics.json`, `paper/figures/*.tex`, `*.png` |

## The live-model experiment

The skill trigger rate (GOAL story B1) needs the `claude` CLI and API access,
so it is opt-in and excluded from `make verify` (CI runs offline):

```
make reproduce REPRODUCE_ARGS="--with-trigger"
# or directly, to control n:
.venv/bin/python experiments/trigger/run_trigger.py --n 5
```

Each run builds a fresh governed fixture in a temp dir, installs the skill and
hooks with the real CLI, marks the fixture trusted so a headless session can
use tools, and gives the agent a durable lesson. A run counts as *triggered*
when a `proposed` journal event appears — that is, the agent went through the
CLI instead of editing the managed file. Runs that fail for environmental
reasons (missing CLI, API quota) are recorded with an `error` field and
excluded from the rate denominator; `metrics.py` then reports the reason
instead of inventing a number.

### Why the trigger number survives a plain `make reproduce`

Raw logs are regenerated, not committed, so a fresh clone has no trigger
logs. To keep the committed paper auditable, the summary of the live run
behind its number is archived at
`experiments/results/trigger-archive.jsonl`. When a clone has no fresh
trigger logs, `metrics.py` falls back to that archive and marks the value
`"from_archive": true`; the metrics table then labels the source
"archived live-model run". A fresh run always wins over the archive, and
the archive is never presented as something this clone measured.

To replace it, run the experiment yourself (`--with-trigger`) and copy the
new summary over the archive.

## Run identifiers

Every log line carries a `run_id`. Every metric in `metrics.json` names the
`latest_run_id` it came from, and the paper footnotes that identifier next to
the value. To audit a number: find its `run_id` in `metrics.json`, then read
the matching file under `experiments/*/logs/`.

## Determinism and environment

The deterministic experiments (scenarios, adversarial, overhead, evidence,
interop) need only Python 3.11+, git, and Node (for the UC1 fixture's
postinstall script). Timing values naturally vary between machines; the
qualitative claims (evidence rate, detection outcomes, queue behaviour) do
not. The paper reports timings as measured means with their run identifiers,
never as machine-independent constants.
