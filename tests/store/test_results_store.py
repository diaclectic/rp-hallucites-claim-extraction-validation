import json

import pytest

from claimcheck.models.finding import Finding
from claimcheck.store.results_store import ResultsStore


def test_save_writes_one_line_per_paper_and_replaces_on_resave(tmp_path):
    path = tmp_path / "results.jsonl"
    store = ResultsStore(path, "Neil Mathias")
    store.save("a", "dev", [Finding("missed", "(X, 2020)")], "note")
    store.save("b", "validation", [], "")
    store.save("a", "dev", [], "fixed")
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert [(r["doc_id"], r["status"], r["reviewer"]) for r in lines] == [
        ("a", "ok", "Neil Mathias"),
        ("b", "ok", "Neil Mathias"),
    ]
    assert lines[0]["note"] == "fixed"
    assert not path.with_name("results.jsonl.tmp").exists()


def test_status_is_issues_when_there_are_findings(tmp_path):
    result = ResultsStore(tmp_path / "r.jsonl", "N").save("a", "dev", [Finding("wrong_citation", "(Y, 1)")], "")
    assert result["status"] == "issues"
    assert result["findings"][0]["kind"] == "wrong_citation"


def test_a_new_run_resumes_from_the_file(tmp_path):
    path = tmp_path / "r.jsonl"
    ResultsStore(path, "N").save("a", "dev", [], "")
    again = ResultsStore(path, "N")
    again.load()
    assert again.get("a")["status"] == "ok"
    assert again.get("b") is None


def test_load_without_a_file_is_empty(tmp_path):
    store = ResultsStore(tmp_path / "none.jsonl", "N")
    store.load()
    assert store.results == {}


def test_load_rejects_a_damaged_line(tmp_path):
    path = tmp_path / "r.jsonl"
    path.write_text('{"doc_id": "a"}\n{broken\n')
    with pytest.raises(ValueError, match="line 2"):
        ResultsStore(path, "N").load()
