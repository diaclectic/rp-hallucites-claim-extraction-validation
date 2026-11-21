import html
import re
import unicodedata

from claimcheck.models.paper import Paper


class CitationLocator:
    """Cleans a paper's OCR markdown and finds the reference set's citations in it.

    The reference set stores each citation as normalized text with no markdown link syntax, escapes, bold or HTML,
    and whitespace collapsed. The text is cleaned the same way, so a citation is a plain substring search.
    """

    LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
    BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
    TAG = re.compile(r"</?[A-Za-z][^>]*>")
    ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!&|<>~$%])")
    BOLD = re.compile(r"\*\*|__")
    PARAGRAPH = re.compile(r"\n\s*\n")
    MIN_ENTRY = 20

    def clean(self, markdown: str) -> str:
        """Strip markdown syntax and collapse whitespace inside each paragraph.

        Args:
            markdown: OCR markdown.

        Returns:
            Plain text with paragraphs separated by a blank line.
        """
        paragraphs = []
        for block in self.PARAGRAPH.split(markdown):
            block = self.LINK.sub(r"\1", block)
            block = self.TAG.sub("", self.BREAK.sub(" ", block))
            block = self.BOLD.sub("", self.ESCAPE.sub(r"\1", html.unescape(block)))
            block = " ".join(unicodedata.normalize("NFC", block).split())
            if block:
                paragraphs.append(block)
        return "\n\n".join(paragraphs)

    def locate(self, doc_id: str, split: str, record: dict, source: dict) -> Paper:
        """Find every citation of a paper's reference-set record in its text.

        Args:
            doc_id: The paper id.
            split: `dev` or `validation`.
            record: The reference-set record: `citations` and `links`.
            source: The paper file: `sections` (title and markdown pairs) and `references` (markdown).

        Returns:
            The paper, with the citations located and each linked to its bibliography entries.
        """
        text = self.clean("\n\n".join(section[1] for section in source["sections"]))
        references = [p for p in self.clean(source["references"]).split("\n\n") if not p.startswith("#")]
        link_refs = [self._refs(link.get("entry"), references) for link in record["links"]]
        spans, unlocated = [], []
        for citation in record["citations"]:
            surface = self.clean(citation["surface"])
            starts = [m.start() for m in re.finditer(self._pattern(surface), text)]
            if not starts:
                unlocated.append(surface)
                continue
            works = [
                {
                    "work": link["work"],
                    "status": link.get("status", ""),
                    "entry": link["entry"] if link.get("entry") not in (None, "AMBIGUOUS") else None,
                    "refs": refs,
                }
                for link, refs in zip(record["links"], link_refs)
                if self._cites(surface, link)
            ]
            spans += [{"start": s, "end": s + len(surface), "surface": surface, "works": works} for s in starts]
        return Paper(doc_id, split, text, self._without_overlaps(spans), unlocated, references)

    @staticmethod
    def _pattern(surface: str) -> re.Pattern:
        """Match the surface exactly, but not as part of a longer word."""
        before = r"(?<!\w)" if surface[:1].isalnum() else ""
        after = r"(?!\w)" if surface[-1:].isalnum() else ""
        return re.compile(before + re.escape(surface) + after)

    @staticmethod
    def _without_overlaps(spans: list[dict]) -> list[dict]:
        """Keep the longest span wherever two overlap, and return them in text order."""
        kept: list[dict] = []
        for span in sorted(spans, key=lambda s: (s["start"] - s["end"], s["start"])):
            if not any(span["start"] < k["end"] and k["start"] < span["end"] for k in kept):
                kept.append(span)
        return sorted(kept, key=lambda s: s["start"])

    @classmethod
    def _cites(cls, surface: str, link: dict) -> bool:
        """Return whether a citation contains the work of a link: its first-author name as a whole word, and its year."""
        last_name, year = link["key"]
        digits = re.match(r"\d+", year)
        suffix = year[digits.end() :] if digits else ""
        if not digits or last_name not in {cls._fold(word).rstrip("0123456789") for word in surface.split()}:
            return False
        if not suffix:
            return re.search(rf"{digits.group()}(?![0-9a-z])", surface) is not None
        letters = re.search(rf"{digits.group()}([a-z](?:,\s*[a-z])*)", surface)
        return letters is not None and suffix in letters.group(1)

    @classmethod
    def _refs(cls, entry: str | None, references: list[str]) -> list[int]:
        """Return the indexes of the bibliography items that overlap a link's entry text.

        The entry comes from an earlier parse and can hold two glued entries, so either containing the other counts.
        """
        if entry in (None, "AMBIGUOUS"):
            return []
        folded = cls._fold(entry)
        return [
            index
            for index, reference in enumerate(references)
            if len(cls._fold(reference)) >= cls.MIN_ENTRY
            and (cls._fold(reference) in folded or folded[:80] in cls._fold(reference))
        ]

    @staticmethod
    def _fold(text: str) -> str:
        """Lowercase, drop accents and keep only letters and digits."""
        decomposed = unicodedata.normalize("NFKD", text.lower())
        return re.sub(r"[^a-z0-9]", "", decomposed)
