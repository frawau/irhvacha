"""scripts/bump_pyhvac.py: follow a pyhvac release."""

import json
import shutil
from pathlib import Path

import pytest

from scripts.bump_pyhvac import main

ROOT = Path(__file__).parent.parent
MANIFEST = "custom_components/irhvac/manifest.json"


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "custom_components/irhvac").mkdir(parents=True)
    shutil.copy(ROOT / MANIFEST, tmp_path / MANIFEST)
    manifest = json.loads((tmp_path / MANIFEST).read_text())
    manifest["requirements"] = ["pyhvac==0.2.0"]
    manifest["version"] = "0.1.0"
    (tmp_path / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
    (tmp_path / "requirements_test.txt").write_text(
        "pytest-homeassistant-custom-component\npyhvac==0.2.0\nblack\n"
    )
    return tmp_path


def read(repo):
    return (
        json.loads((repo / MANIFEST).read_text()),
        (repo / "requirements_test.txt").read_text(),
    )


def test_bumps_pin_and_patch(repo, capsys):
    assert main(["v0.2.1"], root=repo) == 0
    manifest, reqs = read(repo)
    assert manifest["requirements"] == ["pyhvac==0.2.1"]
    assert manifest["version"] == "0.1.1"
    assert "pyhvac==0.2.1\n" in reqs and "pyhvac==0.2.0" not in reqs
    assert capsys.readouterr().out.strip() == "0.1.1"
    assert (repo / MANIFEST).read_text().endswith("}\n")


def test_refuses_minor_release(repo):
    before = read(repo)
    assert main(["0.3.0"], root=repo) == 2
    assert read(repo) == before


@pytest.mark.parametrize("version", ["0.2.0", "v0.2.0", "0.1.9"])
def test_same_or_older_is_nothing_to_do(repo, version):
    before = read(repo)
    assert main([version], root=repo) == 3
    assert read(repo) == before
