from claimcheck.config import Config
from claimcheck.models.finding import Finding
from claimcheck.process.citation_locator import CitationLocator
from claimcheck.store.dataset_store import DatasetStore
from claimcheck.store.results_store import ResultsStore
from claimcheck.web.request_handler import Route
from claimcheck.web.web_server import WebServer


class ValidateCommand:
    """`claimcheck`: serve the review page and save what the reviewer flags.

    The page keeps a paper's flags in the browser until the reviewer saves it. Each save rewrites that paper's line
    in the results file, and the next run picks up where the last one stopped.
    """

    def __init__(self, config: Config, open_browser: bool = True) -> None:
        self.config = config
        self.dataset = DatasetStore(config.root)
        self.results = ResultsStore(config.results_path, config.reviewer)
        self.locator = CitationLocator()
        self.server = WebServer(self.routes(), "validate.html", open_browser=open_browser)

    def run(self) -> None:
        """Load the data and earlier results, serve the page until the reviewer finishes, and say what to send.

        Raises:
            FileNotFoundError: If the data folder or a file in it is missing.
            ValueError: If the reference sets or the results file are malformed.
        """
        self.dataset.load()
        self.results.load()
        self.server.start()
        self.server.wait()
        print(f"{len(self.results.results)} of {len(self.dataset.papers())} papers reviewed.")
        print(f"Email this file back: {self.config.results_path}")

    def routes(self) -> dict[str, Route]:
        """The API routes the page calls."""
        return {
            "GET /api/papers": self._papers,
            "GET /api/paper/*": self._paper,
            "GET /api/pdf/*": self._pdf,
            "POST /api/result": self._save,
            "POST /api/finish": self._finish,
        }

    def _papers(self, body: dict, arg: str) -> dict:
        papers = []
        for doc_id, split in self.dataset.papers():
            result = self.results.get(doc_id)
            papers.append({"doc_id": doc_id, "split": split, "status": result["status"] if result else "todo"})
        return {"reviewer": self.config.reviewer, "results_path": str(self.config.results_path), "papers": papers}

    def _paper(self, body: dict, arg: str) -> dict:
        paper = self.locator.locate(arg, self.dataset.split(arg), self.dataset.record(arg), self.dataset.source(arg))
        return {**paper.to_json(), "result": self.results.get(arg)}

    def _pdf(self, body: dict, arg: str) -> tuple[str, bytes]:
        return "application/pdf", self.dataset.pdf_path(arg).read_bytes()

    def _save(self, body: dict, arg: str) -> dict:
        doc_id = body.get("doc_id")
        if not isinstance(doc_id, str):
            raise ValueError("doc_id is required")
        findings = body.get("findings", [])
        note = body.get("note", "")
        if not isinstance(findings, list) or not isinstance(note, str):
            raise ValueError("findings must be a list and note a string")
        split = self.dataset.split(doc_id)
        return self.results.save(doc_id, split, [Finding.from_json(f) for f in findings], note)

    def _finish(self, body: dict, arg: str) -> dict:
        self.server.stop()
        return {}
