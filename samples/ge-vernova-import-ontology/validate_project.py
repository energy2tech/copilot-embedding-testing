"""Validate generated PBIP JSON against Microsoft's published schemas."""

import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from jsonschema import Draft7Validator
from referencing import Registry, Resource

from build_demo import ROOT


def retrieve(uri: str) -> Resource:
    parsed = urlparse(uri)
    if parsed.scheme != "https" or parsed.hostname != "developer.microsoft.com":
        raise ValueError(f"Unexpected schema source: {uri}")
    with urlopen(uri, timeout=60) as response:
        return Resource.from_contents(json.load(response))


def validate_project(project: Path) -> int:
    registry = Registry(retrieve=retrieve)
    count = 0
    for path in sorted(project.rglob("*")):
        if path.suffix not in {".json", ".pbip", ".pbir", ".pbism"}:
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        schema = document["$schema"]
        validator = Draft7Validator({"$ref": schema}, registry=registry)
        errors = sorted(validator.iter_errors(document), key=lambda error: str(error.path))
        if errors:
            messages = "\n".join(f"{list(error.path)}: {error.message}" for error in errors)
            raise ValueError(f"{path.relative_to(project)}\n{messages}")
        count += 1
    print(f"Validated {count} PBIP JSON files against official schemas")
    return count


if __name__ == "__main__":
    validate_project(ROOT / "project")
