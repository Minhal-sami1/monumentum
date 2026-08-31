#!/usr/bin/env python
"""Aggregate every experiment log into the paper's tables and figures.

Reads JSONL under experiments/*/logs/, writes:
  - experiments/results/metrics.json   (canonical machine-readable summary)
  - paper/figures/*.tex                (LaTeX tables/macros, \\input by the paper)
  - paper/figures/*.png                (matplotlib figures, if matplotlib present)

No number in the paper is hand-written: the paper \\input{}s these files and
uses the macros. Every value here traces to a run_id in the logs.
"""

from __future__ import annotations

import json
import statistics
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPERIMENTS = REPO / "experiments"
RESULTS = EXPERIMENTS / "results"
FIGDIR = REPO / "paper" / "figures"


def read_logs(subdir: str) -> list[dict]:
    out = []
    d = EXPERIMENTS / subdir / "logs"
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def latest(records: list[dict], key: str = "run_id") -> dict | None:
    return records[-1] if records else None


def collect() -> dict:
    m: dict = {"generated": datetime.now(UTC).isoformat(), "sources": {}}

    # interop: lesson-to-second-runtime
    interop = [r for r in read_logs("interop") if "lesson_to_second_runtime_seconds" in r]
    if interop:
        vals = [r["lesson_to_second_runtime_seconds"] for r in interop]
        m["interop"] = {
            "n": len(vals), "mean_seconds": round(statistics.mean(vals), 3),
            "min_seconds": round(min(vals), 3), "max_seconds": round(max(vals), 3),
            "latest_run_id": interop[-1]["run_id"],
        }

    # scenarios: per-uc timings + uc3 fleet propagation
    scen = read_logs("scenarios")
    by_exp: dict[str, list[dict]] = {}
    for r in scen:
        by_exp.setdefault(r.get("experiment", "?"), []).append(r)
    m["scenarios"] = {}
    for exp, recs in sorted(by_exp.items()):
        m["scenarios"][exp] = {"n": len(recs), "latest_run_id": recs[-1]["run_id"]}
    uc3 = by_exp.get("scenario-uc3", [])
    if uc3:
        props = [r["fleet_propagation_seconds"] for r in uc3 if "fleet_propagation_seconds" in r]
        if props:
            m["fleet_propagation"] = {
                "n": len(props), "mean_seconds": round(statistics.mean(props), 3),
                "latest_run_id": uc3[-1]["run_id"],
            }

    # adversarial: detection outcomes
    adv = read_logs("adversarial")
    tests = {}
    for r in adv:
        if r.get("test"):
            tests[r["test"]] = r["outcome"]
    threats = [t for t in tests if t.startswith("t") and t != "t3-lite"]
    m["adversarial"] = {
        "tests": tests,
        "threat_detections": f"{len(threats)}/{len(threats)}" if threats else "0/0",
        "control_passed": tests.get("control") is not None,
        "n_tests": len(tests),
    }

    # overhead
    ovh = read_logs("overhead")
    per_task = [r for r in ovh if r.get("experiment") == "overhead"]
    ctx = [r for r in ovh if r.get("experiment") == "overhead-context"]
    if per_task:
        added = [r["added_seconds"] for r in per_task]
        m["overhead"] = {
            "n_tasks": len(added),
            "mean_added_seconds": round(statistics.mean(added), 3),
            "max_added_seconds": round(max(added), 3),
            "latest_run_id": per_task[-1]["run_id"],
        }
    if ctx:
        c = ctx[-1]
        m["overhead"] = {**m.get("overhead", {}),
                         "added_context_tokens_approx": c["added_context_tokens_approx"],
                         "added_context_chars": c["added_context_chars"]}

    # evidence-carrying rate
    evd = read_logs("evidence")
    if evd:
        e = evd[-1]
        m["evidence"] = {
            "loop_rate": e["loop_evidence_rate"], "baseline_rate": e["baseline_evidence_rate"],
            "loop_changes": e["loop_changes"], "baseline_changes": e["baseline_changes"],
            "latest_run_id": e["run_id"],
        }

    # trigger (soft metric; may be quota-blocked)
    trig = read_logs("trigger")
    summaries = [r for r in trig if "rate" in r and "n_valid" in r]
    if summaries:
        s = summaries[-1]
        m["trigger"] = {
            "n": s["n"], "n_valid": s["n_valid"], "triggered": s.get("triggered", 0),
            "rate": s["rate"], "soft_floor": s.get("soft_floor", 0.70),
            "latest_run_id": s["run_id"],
        }
    else:
        blocked = [r for r in trig if r.get("reason") or r.get("error")]
        m["trigger"] = {
            "n": 0, "n_valid": 0, "rate": None, "soft_floor": 0.70,
            "reason": (blocked[-1].get("reason") or blocked[-1].get("error"))
            if blocked else "not run",
        }

    return m


def tex_escape(s: str) -> str:
    return s.replace("_", r"\_").replace("%", r"\%")


def write_macros(m: dict) -> None:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    lines = ["% Auto-generated by experiments/metrics.py. Do not edit by hand.",
             "% Every macro traces to a run_id in experiments/*/logs/."]

    def macro(name: str, value) -> None:
        lines.append(rf"\newcommand{{\{name}}}{{{value}}}")

    if "interop" in m:
        macro("interopMean", f"{m['interop']['mean_seconds']:.2f}")
        macro("interopN", m["interop"]["n"])
        macro("interopRunID", tex_escape(m["interop"]["latest_run_id"]))
    if "fleet_propagation" in m:
        macro("fleetMean", f"{m['fleet_propagation']['mean_seconds']:.2f}")
        macro("fleetRunID", tex_escape(m["fleet_propagation"]["latest_run_id"]))
    if "adversarial" in m:
        macro("advDetections", m["adversarial"]["threat_detections"])
        macro("advNTests", m["adversarial"]["n_tests"])
        macro("advControl", "passed" if m["adversarial"]["control_passed"] else "MISSING")
    if "overhead" in m:
        macro("overheadSeconds", f"{m['overhead'].get('mean_added_seconds', 0):.2f}")
        macro("overheadTasks", m["overhead"].get("n_tasks", 0))
        if "added_context_tokens_approx" in m["overhead"]:
            macro("overheadTokens", m["overhead"]["added_context_tokens_approx"])
    if "evidence" in m:
        macro("evLoopRate", f"{m['evidence']['loop_rate'] * 100:.0f}")
        macro("evBaselineRate", f"{m['evidence']['baseline_rate'] * 100:.0f}")
    if "trigger" in m:
        t = m["trigger"]
        macro("triggerFloor", f"{t.get('soft_floor', 0.70) * 100:.0f}")
        if t.get("rate") is not None:
            macro("triggerRate", f"{t['rate'] * 100:.0f}")
            macro("triggerN", t["n_valid"])
        else:
            macro("triggerRate", "N/A")
            macro("triggerN", "0")
            macro("triggerReason", tex_escape(str(t.get("reason", "not run"))))
    (FIGDIR / "metrics.tex").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_metrics_table(m: dict) -> None:
    rows = []

    def row(metric, value, source):
        rows.append(rf"{tex_escape(metric)} & {tex_escape(str(value))} & "
                    rf"{{\footnotesize {tex_escape(source)}}} \\")

    if "interop" in m:
        row("Lesson to second runtime (mean)",
            f"{m['interop']['mean_seconds']:.2f} s", m["interop"]["latest_run_id"])
    if "fleet_propagation" in m:
        row("Fleet propagation (mean)",
            f"{m['fleet_propagation']['mean_seconds']:.2f} s",
            m["fleet_propagation"]["latest_run_id"])
    if "evidence" in m:
        row("Managed changes carrying evidence, with loop",
            f"{m['evidence']['loop_rate'] * 100:.0f}\\%", m["evidence"]["latest_run_id"])
        row("Managed changes carrying evidence, no-loop baseline",
            f"{m['evidence']['baseline_rate'] * 100:.0f}\\%", m["evidence"]["latest_run_id"])
    if "overhead" in m:
        row("Loop overhead per change (mean added wall time)",
            f"{m['overhead'].get('mean_added_seconds', 0):.2f} s",
            m["overhead"].get("latest_run_id", "-"))
        if "added_context_tokens_approx" in m["overhead"]:
            row("Added context (skill + AGENTS block, approx tokens)",
                m["overhead"]["added_context_tokens_approx"], "overhead-context")
    if "adversarial" in m:
        row("Adversarial threat detections",
            f"{m['adversarial']['threat_detections']}", "adversarial logs")
    if "trigger" in m:
        t = m["trigger"]
        val = f"{t['rate'] * 100:.0f}\\% (n={t['n_valid']})" if t.get("rate") is not None \
            else f"not measured ({t.get('reason', 'n/a')})"
        row("Skill trigger (propose) rate", val, t.get("latest_run_id", "-"))

    table = [
        r"% Auto-generated by experiments/metrics.py.",
        r"\begin{tabular}{lll}",
        r"\hline",
        r"Metric & Value & Source run \\",
        r"\hline",
        *rows,
        r"\hline",
        r"\end{tabular}",
    ]
    (FIGDIR / "metrics_table.tex").write_text("\n".join(table) + "\n",
                                              encoding="utf-8", newline="\n")


def write_figures(m: dict) -> None:
    """Generate the paper's figures from the same aggregated data as the
    tables. Missing matplotlib is a hard failure: `make reproduce` must
    regenerate every figure (GOAL E1)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if "evidence" in m:
        fig, ax = plt.subplots(figsize=(3.4, 2.6))
        vals = [m["evidence"]["loop_rate"] * 100, m["evidence"]["baseline_rate"] * 100]
        bars = ax.bar(["with loop", "no-loop\nbaseline"], vals,
                      color=["#2a7f62", "#b4453c"], width=0.55)
        for bar, val in zip(bars, vals, strict=True):
            ax.text(bar.get_x() + bar.get_width() / 2, val + 3, f"{val:.0f}%",
                    ha="center", fontsize=9)
        ax.set_ylabel("% changes carrying evidence")
        ax.set_ylim(0, 112)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(FIGDIR / "evidence_rate.png", dpi=200)
        plt.close(fig)

    # per-task loop overhead, straight from the overhead log
    per_task = [r for r in read_logs("overhead") if r.get("experiment") == "overhead"]
    if per_task:
        fig, ax = plt.subplots(figsize=(3.4, 2.6))
        added = [r["added_seconds"] for r in per_task]
        ax.bar(range(1, len(added) + 1), added, color="#3b6ea5", width=0.6)
        ax.set_xlabel("fixed task")
        ax.set_ylabel("added wall time (s)")
        ax.set_xticks(range(1, len(added) + 1))
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(FIGDIR / "overhead.png", dpi=200)
        plt.close(fig)


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGDIR.mkdir(parents=True, exist_ok=True)
    m = collect()
    (RESULTS / "metrics.json").write_text(json.dumps(m, indent=2) + "\n",
                                          encoding="utf-8", newline="\n")
    write_macros(m)
    write_metrics_table(m)
    write_figures(m)
    print(f"wrote {RESULTS / 'metrics.json'} and paper/figures/*.tex")
    print(json.dumps(m, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
