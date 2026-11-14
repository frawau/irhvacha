"""The CI workflows run a Python the tested Home Assistant accepts."""

from pathlib import Path
import re

from homeassistant.const import REQUIRED_PYTHON_VER

WORKFLOWS = Path(__file__).parent.parent / ".github" / "workflows"


def test_workflow_python_is_new_enough():  # Final review 1
    found = []
    for path in WORKFLOWS.glob("*.y*ml"):
        for major, minor in re.findall(
            r'python-version:\s*"(\d+)\.(\d+)"', path.read_text()
        ):
            found.append((path.name, (int(major), int(minor))))
    assert found
    for name, version in found:
        assert version >= REQUIRED_PYTHON_VER[:2], name
