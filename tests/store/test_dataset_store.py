import pytest

from claimcheck.store.dataset_store import DatasetStore


def test_loads_both_splits_in_order(data_root):
    store = DatasetStore(data_root)
    store.load()
    assert store.papers() == [("2020.acl-demos.1", "dev"), ("2021.acl-long.2", "validation")]
    assert store.source("2020.acl-demos.1")["sections"]
    assert store.pdf_path("2021.acl-long.2").read_bytes().startswith(b"%PDF")


def test_missing_folder_says_how_to_fix_it(tmp_path):
    with pytest.raises(FileNotFoundError, match="Extract claimcheck_data.zip"):
        DatasetStore(tmp_path / "nope").load()


def test_missing_split_file(data_root):
    (data_root / "validation.jsonl").unlink()
    with pytest.raises(FileNotFoundError, match="validation.jsonl"):
        DatasetStore(data_root).load()


def test_missing_pdf(data_root):
    (data_root / "pdfs" / "2021.acl-long.2.pdf").unlink()
    with pytest.raises(FileNotFoundError, match="1 paper files are missing"):
        DatasetStore(data_root).load()


def test_malformed_record(data_root):
    (data_root / "dev.jsonl").write_text("not json\n")
    with pytest.raises(ValueError, match="dev.jsonl line 1"):
        DatasetStore(data_root).load()


def test_unknown_ids_cannot_reach_other_files(data_root):
    store = DatasetStore(data_root)
    store.load()
    with pytest.raises(LookupError):
        store.pdf_path("../dev")
