from pathlib import Path

import pytest

from claimcheck.config import Config


def test_load_reads_the_reviewer_and_defaults_the_root():
    config = Config.load()
    assert config.reviewer == "Neil Mathias"
    assert config.root == Path("~/claimcheck_data").expanduser()
    assert config.results_path.name == "manual_validation_results.jsonl"
    assert config.results_path.parent == config.root


def test_load_needs_a_name(tmp_path, monkeypatch):
    empty = tmp_path / "reviewer.txt"
    empty.write_text("# only a comment\n")
    monkeypatch.setattr(Config, "REVIEWER_FILE", empty)
    with pytest.raises(RuntimeError, match="No reviewer name"):
        Config.load()
