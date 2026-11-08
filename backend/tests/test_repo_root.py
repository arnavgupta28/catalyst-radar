"""The package must find config/ even when installed outside the repo (Databricks: %pip install ../../backend)."""

import pytest

from catalyst import config


def test_finds_root_from_cwd_when_package_is_elsewhere(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "config" / "markets").mkdir(parents=True)
    notebooks = repo / "databricks" / "notebooks"
    notebooks.mkdir(parents=True)
    site_packages = tmp_path / "site-packages" / "catalyst" / "config.py"
    site_packages.parent.mkdir(parents=True)
    site_packages.touch()
    monkeypatch.delenv("CATALYST_REPO_ROOT", raising=False)
    monkeypatch.setattr(config, "__file__", str(site_packages))
    monkeypatch.chdir(notebooks)
    assert config.find_repo_root() == repo.resolve()


def test_clear_error_when_no_repo(tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.delenv("CATALYST_REPO_ROOT", raising=False)
    monkeypatch.setattr(config, "__file__", str(tmp_path / "pkg" / "config.py"))
    monkeypatch.chdir(elsewhere)
    with pytest.raises(FileNotFoundError, match="CATALYST_REPO_ROOT"):
        config.find_repo_root()


def test_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("CATALYST_REPO_ROOT", str(tmp_path))
    assert config.find_repo_root() == tmp_path
