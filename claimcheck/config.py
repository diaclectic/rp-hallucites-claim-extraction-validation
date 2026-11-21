from pathlib import Path


class Config:
    """Settings for one run: where the data lives and who is reviewing.

    Attributes:
        root: The folder that holds `dev.jsonl`, `validation.jsonl`, `papers/` and `pdfs/`.
        reviewer: The name recorded in every saved result.
    """

    DEFAULT_ROOT = Path("~/claimcheck_data")
    REVIEWER_FILE = Path(__file__).with_name("reviewer.txt")
    RESULTS_NAME = "manual_validation_results.jsonl"

    def __init__(self, root: Path, reviewer: str) -> None:
        self.root = root
        self.reviewer = reviewer

    @classmethod
    def load(cls, root: Path | None = None) -> "Config":
        """Read the reviewer name from `reviewer.txt`.

        Args:
            root: Replaces the default data folder, for tests and dev runs.

        Returns:
            The settings.

        Raises:
            RuntimeError: If `reviewer.txt` has no name in it.
        """
        names = [
            line.strip()
            for line in cls.REVIEWER_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        if not names:
            raise RuntimeError(f"No reviewer name in {cls.REVIEWER_FILE}")
        return cls(root=(root or cls.DEFAULT_ROOT).expanduser(), reviewer=names[0])

    @property
    def results_path(self) -> Path:
        """The single file the reviewer emails back, next to the data."""
        return self.root / self.RESULTS_NAME
