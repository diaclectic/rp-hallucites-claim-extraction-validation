import pytest

from claimcheck.models.finding import Finding


def test_from_json_fills_defaults():
    finding = Finding.from_json({"kind": "missed", "text": "(A, 2020)"})
    assert finding.to_json() == {
        "kind": "missed", "text": "(A, 2020)", "context": "", "work": "", "correct_entry": "", "note": "",
    }


@pytest.mark.parametrize(
    "bad",
    [
        "text",
        {"kind": "other", "text": "x"},
        {"kind": "missed", "text": "  "},
        {"kind": "missed", "text": "x", "note": 5},
    ],
)
def test_from_json_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        Finding.from_json(bad)
