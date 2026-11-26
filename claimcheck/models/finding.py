from dataclasses import asdict, dataclass


@dataclass
class Finding:
    """One thing the reviewer flagged in a paper.

    Attributes:
        kind: `missed` (a citation the reference set lacks), `wrong_citation` (highlighted text that is not a
            citation) `bad_link` (a citation linked to the wrong bibliography entry) or `bad_citance` (a citation whose
            citance is cut off or incomplete).
        text: The missed text, or the surface of the highlighted citation.
        context: The paragraph around the text, to find it again.
        work: For `bad_link`, the cited work the link is wrong for.
        correct_entry: For `bad_link`, the bibliography entry the reviewer picked as correct.
        note: Anything else the reviewer wants to say.
    """

    KINDS = ("missed", "wrong_citation", "bad_link", "bad_citance")

    kind: str
    text: str
    context: str = ""
    work: str = ""
    correct_entry: str = ""
    note: str = ""

    @classmethod
    def from_json(cls, data: object) -> "Finding":
        """Build a finding from a request body.

        Args:
            data: The parsed JSON of one finding.

        Returns:
            The finding.

        Raises:
            ValueError: If it is not an object, has an unknown kind, has no text, or has a non-string field.
        """
        if not isinstance(data, dict):
            raise ValueError("A finding must be an object")
        fields = {name: data.get(name, "") for name in ("kind", "text", "context", "work", "correct_entry", "note")}
        if not all(isinstance(value, str) for value in fields.values()):
            raise ValueError("Every finding field must be a string")
        if fields["kind"] not in cls.KINDS:
            raise ValueError(f"Unknown finding kind: {fields['kind']!r}")
        if not fields["text"].strip():
            raise ValueError("A finding needs text")
        return cls(**fields)

    def to_json(self) -> dict:
        """Return the finding as a JSON-ready dict."""
        return asdict(self)
