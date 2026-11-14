"""Pin a new pyhvac release and bump the integration's patch version.

    python scripts/bump_pyhvac.py v0.2.1

Prints the new integration version. Exit 2 (files untouched) when the
release is not newer than the current pin, or changes major.minor: a pyhvac
minor release is not taken automatically.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MANIFEST = Path("custom_components/irhvac/manifest.json")
REQUIREMENTS = Path("requirements_test.txt")
PIN = re.compile(r"^pyhvac==(\S+)$", re.MULTILINE)


def _version(text: str) -> tuple[int, int, int]:
    major, minor, patch = (int(p) for p in text.removeprefix("v").split("."))
    return major, minor, patch


def main(argv: list[str], root: Path = Path(".")) -> int:
    """Apply the bump under ``root``; return the exit code."""
    new = _version(argv[0])
    new_text = ".".join(map(str, new))
    manifest_path, reqs_path = root / MANIFEST, root / REQUIREMENTS
    manifest = json.loads(manifest_path.read_text())
    (pin,) = [r for r in manifest["requirements"] if r.startswith("pyhvac==")]
    current = _version(pin.removeprefix("pyhvac=="))
    if new <= current or new[:2] != current[:2]:
        print(
            f"pyhvac {new_text} is not a newer {current[0]}.{current[1]}.x release "
            f"than {'.'.join(map(str, current))}: update by hand",
            file=sys.stderr,
        )
        return 2
    manifest["requirements"] = [
        f"pyhvac=={new_text}" if r == pin else r for r in manifest["requirements"]
    ]
    major, minor, patch = _version(manifest["version"])
    manifest["version"] = f"{major}.{minor}.{patch + 1}"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    reqs_path.write_text(PIN.sub(f"pyhvac=={new_text}", reqs_path.read_text()))
    print(manifest["version"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
