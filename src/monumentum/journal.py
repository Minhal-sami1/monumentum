"""Append-only, hash-chained NDJSON journal (spec §8, invariant I2).

Entry seq numbers are consecutive from 0 across all files under
.monumentum/journal/. Every entry's `prev` is the sha256 of the exact previous
serialized line (bytes, without the trailing newline). Entry 0 is genesis.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path

from monumentum.hashing import canonical_json, sha256_bytes
from monumentum.schemas import validate_object


class JournalError(Exception):
    pass


@dataclass
class ChainBreak:
    seq: int
    reason: str


def _now_utc() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Journal:
    def __init__(self, journal_dir: Path):
        self.dir = journal_dir

    # -- reading ---------------------------------------------------------

    def files(self) -> list[Path]:
        if not self.dir.is_dir():
            return []
        return sorted(p for p in self.dir.iterdir() if p.suffixes[-1:] == [".ndjson"])

    def lines(self) -> list[bytes]:
        out: list[bytes] = []
        for path in self.files():
            data = path.read_bytes()
            for raw in data.split(b"\n"):
                if raw.strip():
                    out.append(raw)
        return out

    def entries(self) -> list[dict]:
        import json

        return [json.loads(line.decode("utf-8")) for line in self.lines()]

    def last_line(self) -> bytes | None:
        lines = self.lines()
        return lines[-1] if lines else None

    def next_seq(self) -> int:
        lines = self.lines()
        if not lines:
            return 0
        import json

        return json.loads(lines[-1].decode("utf-8"))["seq"] + 1

    # -- writing ---------------------------------------------------------

    def append(self, event: str, *, actor: str, ts: str | None = None, **fields) -> dict:
        """Build, validate, chain, and append one entry. Returns the entry."""
        seq = self.next_seq()
        last = self.last_line()
        prev = sha256_bytes(last) if last is not None else None
        if seq == 0 and event != "genesis":
            raise JournalError("entry 0 must be the genesis entry")
        entry: dict = {
            "seq": seq,
            "prev": prev,
            "ts": ts or _now_utc(),
            "event": event,
            "actor": actor,
        }
        for key, value in fields.items():
            if value is not None:
                entry[key] = value
        errors = validate_object("journal-entry", entry)
        if errors:
            raise JournalError(f"refusing to append invalid entry: {errors[0]}")
        line = canonical_json(entry).encode("utf-8")
        self.dir.mkdir(parents=True, exist_ok=True)
        month = entry["ts"][:7]  # YYYY-MM
        path = self.dir / f"{month}.ndjson"
        with open(path, "ab") as f:
            f.write(line + b"\n")
        return entry

    # -- verification (invariant I2) --------------------------------------

    def verify_chain(self) -> ChainBreak | None:
        """Walk the chain. Returns None when intact, else the first break."""
        import json

        lines = self.lines()
        if not lines:
            return ChainBreak(seq=0, reason="journal is empty: no genesis entry")
        prev_line: bytes | None = None
        for i, line in enumerate(lines):
            try:
                entry = json.loads(line.decode("utf-8"))
            except Exception:
                return ChainBreak(seq=i, reason=f"line {i} is not valid JSON")
            errors = validate_object("journal-entry", entry)
            if errors:
                return ChainBreak(seq=i, reason=f"entry invalid against schema: {errors[0]}")
            if entry["seq"] != i:
                return ChainBreak(
                    seq=i, reason=f"sequence break: expected seq {i}, found {entry['seq']}"
                )
            if line != canonical_json(entry).encode("utf-8"):
                return ChainBreak(seq=i, reason=f"entry {i} is not in canonical form")
            if i == 0:
                if entry["prev"] is not None:
                    return ChainBreak(seq=0, reason="genesis entry must have prev: null")
            else:
                expected = sha256_bytes(prev_line)  # type: ignore[arg-type]
                if entry["prev"] != expected:
                    return ChainBreak(
                        seq=i,
                        reason=f"hash chain broken at seq {i}: prev does not match entry {i - 1}",
                    )
            prev_line = line
        return None
