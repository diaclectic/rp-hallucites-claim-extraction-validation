import json
from pathlib import Path

import pytest

from claimcheck.config import Config

PAPER_A = {
    "doc_id": "2020.acl-demos.1",
    "sections": [
        ["Intro", "# Intro\n\nBLEU (Papineni et al., 2002) and METEOR [(Banerjee and Lavie, 2005)](http://x) are **metrics**.\n\n"
                  "As Smith et al. (2019a) showed,   words\nwrap. Also (Doe, 2020)."],
    ],
    "references": "## References\n\nKishore Papineni, Salim Roukos. 2002. BLEU: a method for automatic evaluation of machine translation.\n\n"
    "Satanjeev Banerjee and Alon Lavie. 2005. Meteor: An automatic metric for mt evaluation with improved correlation.\n\n"
    "John Smith. 2019a. A paper about something. In *Proceedings*.\n\nJohn Smith. 2019b. Another paper about things.",
}
RECORD_A = {
    "doc_id": "2020.acl-demos.1",
    "citations": [
        {"surface": "(Papineni et al., 2002)", "count": 1},
        {"surface": "(Banerjee and Lavie, 2005)", "count": 1},
        {"surface": "Smith et al. (2019a)", "count": 1},
        {"surface": "(Doe, 2020)", "count": 1},
        {"surface": "(Never Appears, 1999)", "count": 1},
    ],
    "works": [],
    "links": [
        {"work": "Papineni et al., 2002", "key": ["papineni", "2002"], "entry": "Kishore Papineni, Salim Roukos. 2002. BLEU: a method for automatic evaluation of machine translation.", "status": "agree"},
        {"work": "Banerjee and Lavie, 2005", "key": ["banerjee", "2005"], "entry": "Satanjeev Banerjee and Alon Lavie. 2005. Meteor: An automatic metric for mt evaluation with improved correlation.", "status": "agree"},
        {"work": "Smith et al., 2019a", "key": ["smith", "2019a"], "entry": "John Smith. 2019a. A paper about something. In Proceedings.", "status": "agree"},
        {"work": "Doe, 2020", "key": ["doe", "2020"], "entry": None, "status": "agree"},
    ],
}
PAPER_B = {"doc_id": "2021.acl-long.2", "sections": [["T", "Nothing cited here."]], "references": "## References\n\nA. B. 2000. Title."}
RECORD_B = {"doc_id": "2021.acl-long.2", "citations": [], "works": [], "links": []}


@pytest.fixture
def paper_a() -> tuple[dict, dict]:
    return RECORD_A, PAPER_A


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    """A data folder with one paper in dev and one in validation."""
    root = tmp_path / "claimcheck_data"
    (root / "papers").mkdir(parents=True)
    (root / "pdfs").mkdir()
    for split, record, paper in (("dev", RECORD_A, PAPER_A), ("validation", RECORD_B, PAPER_B)):
        (root / f"{split}.jsonl").write_text(json.dumps(record) + "\n")
        (root / "papers" / f"{record['doc_id']}.json").write_text(json.dumps(paper))
        (root / "pdfs" / f"{record['doc_id']}.pdf").write_bytes(b"%PDF-1.4 " + record["doc_id"].encode())
    return root


@pytest.fixture
def config(data_root: Path) -> Config:
    return Config(root=data_root, reviewer="Test Reviewer")
