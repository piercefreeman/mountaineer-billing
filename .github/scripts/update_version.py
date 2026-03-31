# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "packaging",
# ]
# ///

import re
import sys
from pathlib import Path
from sys import stdout

from packaging.version import Version


def normalize_python_version(new_version: str) -> str:
    return str(Version(new_version))


def update_section_version(
    file_contents: str,
    section_name: str,
    new_version: str,
) -> tuple[str, bool]:
    section_pattern = re.compile(
        rf"(?ms)^\[{re.escape(section_name)}\]\n(?P<body>.*?)(?=^\[|\Z)"
    )
    match = section_pattern.search(file_contents)
    if not match:
        return file_contents, False

    body = match.group("body")
    updated_body, count = re.subn(
        r'(?m)^(version\s*=\s*")[^"]+(")$',
        rf"\g<1>{new_version}\g<2>",
        body,
        count=1,
    )
    if count == 0:
        return file_contents, False

    return (
        file_contents[: match.start("body")]
        + updated_body
        + file_contents[match.end("body") :],
        True,
    )


def update_version_python(new_version: str) -> None:
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("pyproject.toml not found, skipping version update")  # noqa: T201
        return

    normalized_version = normalize_python_version(new_version)
    file_contents = pyproject_path.read_text()

    updated_contents = file_contents
    updated = False
    for section_name in ("tool.poetry", "project"):
        updated_contents, section_updated = update_section_version(
            updated_contents,
            section_name,
            normalized_version,
        )
        updated = updated or section_updated

    if not updated:
        print(  # noqa: T201
            "Warning: Neither [tool.poetry] nor [project] version was found in pyproject.toml"
        )
        return

    pyproject_path.write_text(updated_contents)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        stdout.write("Usage: python update_version.py <new_version>")
        sys.exit(1)

    new_version = sys.argv[1].lstrip("v")
    update_version_python(new_version)
    stdout.write(f"Updated version to: {new_version}")
