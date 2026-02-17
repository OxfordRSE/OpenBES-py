import os
import tomllib
import json
import re
import sys
from urllib import request
from pathlib import Path

output = os.environ.get("GITHUB_OUTPUT")

p = Path("pyproject.toml")

doc = tomllib.loads(p.read_text())
name = doc.get("project", {}).get("name") or doc.get("tool", {}).get("poetry", {}).get(
    "name"
)
base_version = doc.get("project", {}).get("version") or doc.get("tool", {}).get(
    "poetry", {}
).get("version")

print(f"Current name: {name}", file=sys.stderr)
print(f"Current version: {base_version}", file=sys.stderr)

if not name or not base_version:
    print("ERROR: missing name/version", file=sys.stderr)
    sys.exit(1)

is_tag = sys.argv[1].startswith("refs/tags/")
new_version = base_version

if not is_tag:
    # query TestPyPI for existing releases
    try:
        j = json.loads(
            request.urlopen(f"https://test.pypi.org/pypi/{name}/json", timeout=10)
            .read()
            .decode()
        )
        releases = list(j.get("releases", {}).keys())
    except Exception:
        releases = []

    print(f"Existing releases on TestPyPI: {releases}", file=sys.stderr)

    prefix = base_version + ".dev"
    devs = [
        int(r[len(prefix) :])
        for r in releases
        if r.startswith(prefix) and r[len(prefix) :].isdigit()
    ]
    nextdev = max(devs) + 1 if devs else 1
    new_version = f"{base_version}.dev{nextdev}"
else:
    # Set the version to the tag version
    new_version = sys.argv[1][len("refs/tags/") :]

if new_version:
    txt = p.read_text()
    txt_new, n = re.subn(
        r"(?m)^(version\s*=\s*)\"[^\"]+\"", r'\1"' + new_version + '"', txt, count=1
    )
    if n == 0:
        print("ERROR: couldn't rewrite version", file=sys.stderr)
        sys.exit(1)
    print("Updating version to:", new_version, file=sys.stderr)
    p.write_text(txt_new)
else:
    print("No changes made to version", file=sys.stderr)

# output for later jobs
with open(output, "a") as f:
    f.write(f"name={name}\n")
    f.write(f"version={new_version}\n")
