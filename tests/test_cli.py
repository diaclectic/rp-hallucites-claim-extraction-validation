import pytest

from claimcheck.cli import Cli
from claimcheck.config import Config


def test_missing_data_is_a_user_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Config, "DEFAULT_ROOT", tmp_path / "absent")
    assert Cli().run([]) == 1
    assert "claimcheck: " in capsys.readouterr().err


def test_takes_no_arguments():
    with pytest.raises(SystemExit) as error:
        Cli().run(["some/path"])
    assert error.value.code == 2
