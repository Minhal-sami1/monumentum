"""SDK five-verb tests (story B3).

The SDK is installed by `make setup`, so an import failure here is a real
failure, never a reason to skip: the final gate requires zero skipped tests.
"""

import pytest
from loop import Loop, LoopError

PROMPT = "# prompt\n\n## Lessons\n"

POLICY = """\
spec: loop/v0.1
envelope:
  context:
    level: L2
    gates: [evidence_required]
    targets_allow: ["prompts/**"]
  capability:
    level: L1
    gates: [evidence_required, human_review]
    targets_allow: ["tools/**"]
  architecture:
    level: L1
    gates: [evidence_required, human_review]
    targets_allow: ["agent.yaml"]
protected: [".loop/**"]
"""

DIFF = """\
--- a/prompts/system.md
+++ b/prompts/system.md
@@ -1,3 +1,4 @@
 # prompt

 ## Lessons
+- always pin versions
"""


@pytest.fixture
def lp(tmp_path):
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "system.md").write_text(PROMPT, encoding="utf-8", newline="\n")
    return Loop.init(tmp_path, POLICY)


def _evidence() -> dict:
    return {
        "id": "ev-001", "kind": "human", "grader": "independent",
        "format": "human-feedback", "summary": {"metric": "works"},
    }


def test_full_cycle(lp):
    cs = lp.propose(
        layer="context", targets=["prompts/system.md"], diff=DIFF,
        rationale="pin versions", origin="run-1",
    )
    cs.attach_evidence(_evidence())
    decision = lp.gate(cs)
    assert decision.approved and not decision.queued
    lp.apply(cs)
    prompt = (lp.workspace.root / "prompts" / "system.md").read_text(encoding="utf-8")
    assert "always pin versions" in prompt
    assert [e["event"] for e in lp.log(cs)] == ["proposed", "gated", "applied"]
    assert lp.verify() == []


def test_rollback(lp):
    cs = lp.propose(layer="context", targets=["prompts/system.md"], diff=DIFF,
                    rationale="pin versions")
    cs.attach_evidence(_evidence())
    lp.gate(cs)
    lp.apply(cs)
    lp.rollback(cs)
    prompt = (lp.workspace.root / "prompts" / "system.md").read_text(encoding="utf-8")
    assert "always pin versions" not in prompt


def test_propose_out_of_allowlist_raises(lp):
    with pytest.raises(LoopError, match="rejected"):
        lp.propose(layer="context", targets=["secrets.txt"],
                   diff=DIFF.replace("prompts/system.md", "secrets.txt"),
                   rationale="nope")


def test_queue_path(lp, tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "t.py").write_text("print(1)\n", encoding="utf-8", newline="\n")
    cap_diff = (
        "--- a/tools/t.py\n+++ b/tools/t.py\n@@ -1 +1 @@\n-print(1)\n+print(2)\n"
    )
    cs = lp.propose(layer="capability", targets=["tools/t.py"], diff=cap_diff,
                    rationale="fix tool", producer="toy")
    cs.attach_evidence(_evidence())
    decision = lp.gate(cs)
    assert decision.queued and not decision.approved
    assert lp.queue_for_review(cs) == cs.id
    lp.approve(cs, "reviewer/rev1")
    assert "print(2)" in (tmp_path / "tools" / "t.py").read_text(encoding="utf-8")


def test_sync_without_registry_raises(lp):
    from agentloop.registry import RegistryError

    with pytest.raises(RegistryError, match="no registry configured"):
        lp.sync()
