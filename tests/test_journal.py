"""Journal hash chain tests (invariant I2, story A6)."""

import pytest

from agentloop.journal import Journal, JournalError


@pytest.fixture
def journal(tmp_path):
    return Journal(tmp_path / "journal")


def _seed(journal: Journal) -> None:
    journal.append("genesis", actor="executor/agentloop@0.1.0")
    journal.append("proposed", actor="producer/test", cs="cs-20260830-a1b2")
    journal.append(
        "gated",
        actor="executor/agentloop@0.1.0",
        cs="cs-20260830-a1b2",
        decision={"gate": "L2-auto"},
    )


def test_chain_intact_after_appends(journal):
    _seed(journal)
    assert journal.verify_chain() is None
    assert journal.next_seq() == 3


def test_first_entry_must_be_genesis(journal):
    with pytest.raises(JournalError, match="genesis"):
        journal.append("proposed", actor="producer/test")


def test_empty_journal_fails_verification(journal):
    break_ = journal.verify_chain()
    assert break_ is not None and "empty" in break_.reason


def test_tampered_line_detected_at_exact_seq(journal):
    _seed(journal)
    path = journal.files()[0]
    lines = path.read_bytes().split(b"\n")
    lines[1] = lines[1].replace(b"producer/test", b"producer/evil")
    path.write_bytes(b"\n".join(lines))
    break_ = journal.verify_chain()
    assert break_ is not None
    # entry 1 re-serializes canonically, so the break surfaces at entry 2's prev
    assert break_.seq == 2
    assert "hash chain broken" in break_.reason


def test_deleted_line_detected(journal):
    _seed(journal)
    path = journal.files()[0]
    lines = [ln for ln in path.read_bytes().split(b"\n") if ln.strip()]
    del lines[1]
    path.write_bytes(b"\n".join(lines) + b"\n")
    break_ = journal.verify_chain()
    assert break_ is not None
    assert break_.seq == 1


def test_invalid_entry_refused(journal):
    journal.append("genesis", actor="executor/agentloop@0.1.0")
    with pytest.raises(JournalError, match="invalid entry"):
        journal.append("not-an-event", actor="executor/agentloop@0.1.0")


def test_noncanonical_line_detected(journal):
    _seed(journal)
    path = journal.files()[0]
    data = path.read_bytes().replace(b'"seq":1,', b'"seq":1, ', 1)
    path.write_bytes(data)
    break_ = journal.verify_chain()
    assert break_ is not None
    assert break_.seq in (1, 2)
