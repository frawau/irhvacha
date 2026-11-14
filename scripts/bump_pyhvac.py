"""Pin a new pyhvac release and bump the integration's patch version.

    python scripts/bump_pyhvac.py v0.2.1

Prints the new integration version. Files are untouched and the exit code
is 3 when the release is a pre-release or not newer than the current pin
(nothing to do), or
2 when it changes major.minor (a pyhvac minor release is not taken
automatically: update by hand).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MANIFEST = Path("custom_components/irhvac/manifest.json")
REQUIREMENTS = Path("requirements_test.txt")
PIN = re.compile(r"^pyhvac==(\S+)$", re.MULTILINE)


FINAL = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def _version(text: str) -> tuple[int, int, int] | None:
    """(major, minor, patch), or None for a pre-release such as 0.2.1rc1."""
    if (match := FINAL.match(text)) is None:
        return None
    major, minor, patch = (int(p) for p in match.groups())
    return major, minor, patch


def main(argv: list[str], root: Path = Path(".")) -> int:
    """Apply the bump under ``root``; return the exit code."""
    new = _version(argv[0])
    if new is None:
        print(f"pyhvac {argv[0]} is a pre-release: nothing to do", file=sys.stderr)
        return 3
    new_text = ".".join(map(str, new))
    manifest_path, reqs_path = root / MANIFEST, root / REQUIREMENTS
    manifest = json.loads(manifest_path.read_text())
    (pin,) = [r for r in manifest["requirements"] if r.startswith("pyhvac==")]
    current = _version(pin.removeprefix("pyhvac=="))
    if new <= current:
        print(
            f"pyhvac {new_text} is already pinned or older than "
            f"{'.'.join(map(str, current))}: nothing to do",
            file=sys.stderr,
        )
        return 3
    if new[:2] != current[:2]:
        print(
            f"pyhvac {new_text} is a new minor release: update by hand",
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
