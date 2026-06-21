"""Turn logging + replay store (PLAN §16, PRD_gui_and_logs)."""

from __future__ import annotations

import json
from pathlib import Path

from cop_thief.domain.records import TurnRecord


class ReplayStore:
    """Append-only JSONL log of turn records, replayable later."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: TurnRecord) -> None:
        """Append one turn record as a JSON line."""
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.as_dict()) + "\n")

    def load(self) -> list[dict]:
        """Load all turn records (empty if the file does not exist)."""
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]
