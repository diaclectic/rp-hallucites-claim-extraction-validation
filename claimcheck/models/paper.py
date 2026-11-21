from dataclasses import asdict, dataclass


@dataclass
class Paper:
    """One paper ready for the page: its cleaned text with the reference set's citations located in it.

    Attributes:
        doc_id: The paper id, such as `2020.acl-demos.18`.
        split: `dev` or `validation`.
        text: The cleaned OCR text. Paragraphs are separated by a blank line.
        spans: One per highlighted citation: `start` and `end` offsets into `text`, the `surface`, and its `works`.
            Each work has `work`, `status`, `entry` (the bibliography text, or None) and `refs` (indexes into
            `references`).
        unlocated: Citation surfaces from the reference set that were not found in `text`.
        references: The bibliography entries, one per item.
    """

    doc_id: str
    split: str
    text: str
    spans: list[dict]
    unlocated: list[str]
    references: list[str]

    def to_json(self) -> dict:
        """Return the paper as a JSON-ready dict."""
        return asdict(self)
