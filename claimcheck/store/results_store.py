import json
import os
from pathlib import Path

from claimcheck.models.finding import Finding
from claimcheck.utils.clock import now_iso


class ResultsStore:
    """The single results file: one JSON line per reviewed paper, the latest save of a paper replacing its line.

    The file is rewritten through a temp file and a rename, so a crash can't leave half a file.
    """

    def __init__(self, path: Path, reviewer: str) -> None:
        self.path = path
        self.reviewer = reviewer
        self.results: dict[str, dict] = {}

    def load(self) -> None:
        """Read the results of earlier sessions, if the file exists.

        Raises:
            ValueError: If a line is not a result with a `doc_id`.
        """
        if not self.path.is_file():
            return
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                result = json.loads(line)
                self.results[result["doc_id"]] = result
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                raise ValueError(f"{self.path} line {number} is not a result with a doc_id") from error

    def get(self, doc_id: str) -> dict | None:
        """Return the saved result for a paper, or None if it has not been reviewed."""
        return self.results.get(doc_id)

    def save(self, doc_id: str, split: str, findings: list[Finding], note: str) -> dict:
        """Save the review of one paper and rewrite the file.

        Args:
            doc_id: The paper reviewed.
            split: `dev` or `validation`.
            findings: What the reviewer flagged. Empty means the paper is fine.
            note: A free-text note about the paper.

        Returns:
            The saved result. Its `status` is `issues` if there are findings and `ok` if not.
        """
        result = {
            "doc_id": doc_id,
            "split": split,
            "reviewer": self.reviewer,
            "reviewed_at": now_iso(),
            "status": "issues" if findings else "ok",
            "findings": [finding.to_json() for finding in findings],
            "note": note,
        }
        self.results[doc_id] = result
        temp = self.path.with_name(self.path.name + ".tmp")
        temp.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in self.results.values()), encoding="utf-8", newline="\n"
        )
        os.replace(temp, self.path)
        return result
