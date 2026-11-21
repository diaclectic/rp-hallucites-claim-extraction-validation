import json
from pathlib import Path


class DatasetStore:
    """The reference sets and the paper files they describe, read from the data folder.

    The folder holds `dev.jsonl`, `validation.jsonl`, `papers/<doc_id>.json` (OCR text and bibliography) and
    `pdfs/<doc_id>.pdf`.
    """

    SPLITS = ("dev", "validation")

    def __init__(self, root: Path) -> None:
        self.root = root
        self.splits: dict[str, str] = {}
        self.records: dict[str, dict] = {}

    def load(self) -> None:
        """Read both reference sets and check every paper has its text and PDF.

        Raises:
            FileNotFoundError: If the folder, a reference set, or a paper's text or PDF is missing.
            ValueError: If a reference set has a line that is not a record with a `doc_id`.
        """
        if not self.root.is_dir():
            raise FileNotFoundError(f"{self.root} does not exist. Extract claimcheck_data.zip into your home folder.")
        for split in self.SPLITS:
            path = self.root / f"{split}.jsonl"
            if not path.is_file():
                raise FileNotFoundError(f"{path} does not exist. Is the data extracted completely?")
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    doc_id = record["doc_id"]
                except (json.JSONDecodeError, KeyError, TypeError) as error:
                    raise ValueError(f"{path} line {number} is not a record with a doc_id") from error
                self.splits[doc_id] = split
                self.records[doc_id] = record
        missing = [
            path for doc_id in self.records for path in (self._text_path(doc_id), self.pdf_path(doc_id)) if not path.is_file()
        ]
        if missing:
            raise FileNotFoundError(f"{len(missing)} paper files are missing, such as {missing[0]}")

    def papers(self) -> list[tuple[str, str]]:
        """Return `(doc_id, split)` for every paper, in file order."""
        return list(self.splits.items())

    def split(self, doc_id: str) -> str:
        """Return `dev` or `validation` for a paper.

        Raises:
            LookupError: If the paper is not in either set.
        """
        if doc_id not in self.splits:
            raise LookupError(doc_id)
        return self.splits[doc_id]

    def record(self, doc_id: str) -> dict:
        """Return the reference-set record for a paper.

        Raises:
            LookupError: If the paper is not in either set.
        """
        if doc_id not in self.records:
            raise LookupError(doc_id)
        return self.records[doc_id]

    def source(self, doc_id: str) -> dict:
        """Return the OCR `sections` and `references` of a paper.

        Raises:
            LookupError: If the paper is not in either set.
        """
        self.record(doc_id)
        return json.loads(self._text_path(doc_id).read_text(encoding="utf-8"))

    def pdf_path(self, doc_id: str) -> Path:
        """Return where a paper's PDF is. Only ids from the reference sets are valid, so no path escapes the folder.

        Raises:
            LookupError: If the paper is not in either set.
        """
        self.record(doc_id)
        return self.root / "pdfs" / f"{doc_id}.pdf"

    def _text_path(self, doc_id: str) -> Path:
        return self.root / "papers" / f"{doc_id}.json"
