import bisect
import html
import re
import unicodedata
from collections.abc import Callable

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
    HYPHEN_BREAK = re.compile(r"(\w)-\s+([a-z])")
    NOTE_MARK = re.compile(r"^<sup>[^<]{0,12}</sup>\s*")  # a footnote's number must not stick to its first word
    PARAGRAPH = re.compile(r"\n\s*\n")
    MIN_ENTRY = 20

    def clean(self, markdown: str) -> str:
        """Strip markdown syntax (also italics, backslashes and hyphens at a line break) and collapse whitespace in each paragraph.

        Args:
            markdown: OCR markdown.

        Returns:
            Plain text with paragraphs separated by a blank line.
        """
        paragraphs = []
        for block in self.PARAGRAPH.split(markdown):
            block = self.LINK.sub(r"\1", block)
            block = self.TAG.sub("", self.BREAK.sub(" ", self.NOTE_MARK.sub("", block)))
            block = self.BOLD.sub("", self.ESCAPE.sub(r"\1", html.unescape(block)))
            block = block.replace("\\", "").replace("*", "")  # as the reference set's surfaces are normalized
            block = " ".join(self.HYPHEN_BREAK.sub(r"\1\2", unicodedata.normalize("NFC", block)).split())
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
        link_refs = [self._refs(self._clean_entry(link.get("entry")), references) for link in record["links"]]
        spans, unlocated = [], []
        keys = [tuple(link["key"]) for link in record["links"]]
        shared = {key for key in keys if keys.count(key) > 1}  # one key, several forms: "Levitan and Hirschberg" / "Levitan et al."
        for citation in record["citations"]:
            surface = self.clean(citation["surface"])
            found = [(m.start(), m.end()) for m in re.finditer(self._pattern(surface), text)]
            windows = self._citance_windows(citation.get("citances"), text) if found else []
            if not found:
                unlocated.append(surface)
                continue
            matched = [
                (link, refs)
                for link, refs in zip(record["links"], link_refs)
                if self._cites(surface, link, form=tuple(link["key"]) in shared)
            ]
            first_authors = [
                link["key"] for link, _ in matched if self._cites(surface, link, first_author=True, form=tuple(link["key"]) in shared)
            ]
            works = [
                {
                    "work": link["work"],
                    "status": link.get("status", ""),
                    "entry": link["entry"] if link.get("entry") not in (None, "AMBIGUOUS") else None,
                    "refs": refs,
                }
                for link, refs in matched
                if link["key"] in first_authors or all(key[1] != link["key"][1] for key in first_authors)
            ]
            spans += [
                {"start": start, "end": end, "surface": surface, "works": works, "citance": self._enclosing(windows, start, end)}
                for start, end in found
            ]
        spans = self._without_overlaps(spans)
        utf16 = self._utf16_offsets(text)
        for span in spans:
            span["start"], span["end"] = utf16(span["start"]), utf16(span["end"])
            if span["citance"]:
                span["citance"] = {key: utf16(value) for key, value in span["citance"].items()}
        return Paper(doc_id, split, text, spans, unlocated, references)

    @staticmethod
    def _pattern(surface: str) -> re.Pattern:
        """Match the surface, but not as part of a longer word.

        Whitespace in the surface matches any whitespace in the text, a paragraph break included: the OCR sometimes puts
        a page or column break inside a citation (`(Kendall` / blank line / `et al., 2018)`).
        """
        before = r"(?<!\w)" if surface[:1].isalnum() else ""
        after = r"(?!\w)" if surface[-1:].isalnum() else ""
        body = r"\s+".join(re.escape(word) for word in surface.split())
        return re.compile(before + body + after)

    def _citance_windows(self, citances: list[str] | None, text: str) -> list[tuple[int, int]]:
        """Return where each of a citation's citance sentences lies in the text.

        Args:
            citances: The sentences (markdown) that contain the citation, from the reference set; may be missing.
            text: The cleaned paper text.

        Returns:
            `(start, end)` offsets, one per place a sentence is found. A sentence is cleaned like the text and matches across
            any whitespace, a paragraph break included.
        """
        windows = []
        for citance in citances or []:
            words = self.clean(citance).split()
            if words:
                pattern = re.compile(r"\s+".join(re.escape(word) for word in words))
                windows += [(m.start(), m.end()) for m in pattern.finditer(text)]
        return windows

    @staticmethod
    def _enclosing(windows: list[tuple[int, int]], start: int, end: int) -> dict | None:
        """Return the shortest citance window that contains a citation, or None."""
        inside = [window for window in windows if window[0] <= start and end <= window[1]]
        if not inside:
            return None
        first, last = min(inside, key=lambda window: window[1] - window[0])
        return {"start": first, "end": last}

    @staticmethod
    def _utf16_offsets(text: str) -> Callable[[int], int]:
        """Return a function that turns an offset in `text` (counted in characters) into one the browser uses.

        JavaScript counts UTF-16 units, so every character outside the basic plane (an emoji, a math letter like 𝑥) before
        an offset adds one.
        """
        astral = [index for index, char in enumerate(text) if ord(char) > 0xFFFF]
        return lambda offset: offset + bisect.bisect_left(astral, offset)

    @staticmethod
    def _without_overlaps(spans: list[dict]) -> list[dict]:
        """Keep the longest span wherever two overlap, and return them in text order."""
        kept: list[dict] = []
        for span in sorted(spans, key=lambda s: (s["start"] - s["end"], s["start"])):
            if not any(span["start"] < k["end"] and k["start"] < span["end"] for k in kept):
                kept.append(span)
        return sorted(kept, key=lambda s: s["start"])

    @classmethod
    def _cites(cls, surface: str, link: dict, first_author: bool = False, form: bool = False) -> bool:
        """Return whether one item of a citation is the work of a link.

        A citation like `(A, 2015; B, 2016)` holds one item per `;`. The work's name and year must both sit in the
        same item.

        Args:
            surface: The citation text.
            link: A reference-set link with a `key` of `[last name, year]`.
            first_author: Whether the name must be the item's first author, not one after `and`.
            form: Whether the item must also be written the way the link's work is (`X et al.`, `X and Y`, or `X`). Used when
                several links share one key, so "Levitan et al., 2011" does not also cite "Levitan and Hirschberg, 2011".

        Returns:
            Whether any item of the citation cites the work.
        """
        return any(cls._item_cites(item, link, first_author, form) for item in cls._items(surface))

    @staticmethod
    def _items(surface: str) -> list[str]:
        """Split a citation on `;`, keeping a bare year such as `2019` with the author before it."""
        items: list[str] = []
        for item in surface.split(";"):
            if items and re.match(r"[\s(]*\d", item):
                items[-1] += ";" + item
            else:
                items.append(item)
        return items

    @classmethod
    def _item_cites(cls, item: str, link: dict, first_author: bool, form: bool = False) -> bool:
        """Return whether a single citation item contains the work of a link: its name and its year."""
        last_name, year = link["key"]
        digits = re.match(r"\d+", year)
        suffix = year[digits.end() :] if digits else ""
        words = item.split()
        wanted = cls._work_form(link) if form else None
        named = any(
            cls._fold(word).rstrip("0123456789") == last_name
            and not (first_author and i and words[i - 1].lower() in ("and", "&"))
            and (wanted is None or cls._form(words[i + 1 :]) == wanted)
            for i, word in enumerate(words)
        )
        if not digits or not named:
            return False
        if not suffix:
            return re.search(rf"{digits.group()}(?![0-9a-z])", item) is not None
        letters = re.search(rf"{digits.group()}([a-z](?:,\s*[a-z])*)", item)
        return letters is not None and suffix in letters.group(1)

    @classmethod
    def _work_form(cls, link: dict) -> tuple[bool, str]:
        """The form a link's work is written in, read from its `work` text ("Levitan et al., 2011")."""
        words = link["work"].split()
        for i, word in enumerate(words):
            if cls._fold(word).rstrip("0123456789") == link["key"][0]:
                return cls._form(words[i + 1 :])
        return False, ""

    @classmethod
    def _form(cls, after: list[str]) -> tuple[bool, str]:
        """How a name is continued: `(True, "")` for `et al.`, `(False, second author)` for `and Y`, `(False, "")` for none.

        Args:
            after: The words that follow the first author's last name.
        """
        if after and after[0].lower().startswith("et"):
            return True, ""
        if len(after) > 1 and after[0].lower().strip(",") in ("and", "&"):
            return False, cls._fold(after[1]).rstrip("0123456789")
        return False, ""

    def _clean_entry(self, entry: str | None) -> str | None:
        """Clean an entry the way the bibliography items are (tags and URLs in angle brackets removed), so they compare equal."""
        return self.clean(entry) if isinstance(entry, str) and entry != "AMBIGUOUS" else entry

    @classmethod
    def _refs(cls, entry: str | None, references: list[str]) -> list[int]:
        """Return the indexes of the bibliography items that match a link's entry text.

        An item that is the entry wins; then items that contain it or that it contains. Only when there are none does the
        start of the entry decide: an entry from an earlier parse can have lost its end, or hold two glued entries.
        """
        if entry in (None, "AMBIGUOUS"):
            return []
        folded = cls._fold(entry)
        items = [(index, cls._fold(reference)) for index, reference in enumerate(references)]
        items = [(index, item) for index, item in items if len(item) >= cls.MIN_ENTRY or item == folded]
        same = [index for index, item in items if item == folded]
        if same:
            return same
        contained = [index for index, item in items if item in folded or folded in item]
        return contained or [index for index, item in items if folded[:80] in item]

    @staticmethod
    def _fold(text: str) -> str:
        """Lowercase, drop accents and keep only letters and digits."""
        decomposed = unicodedata.normalize("NFKD", text.lower())
        return re.sub(r"[^a-z0-9]", "", decomposed)
