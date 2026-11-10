"""Verify published file SHA-256 manifest. Python stdlib; no network or writes."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parent.parent
manifest = root / "RELEASE_MANIFEST.csv"
with manifest.open(encoding="utf-8-sig", newline="") as stream:
    rows = list(csv.DictReader(stream))

assert rows and set(rows[0]) == {"File", "SHA256"}, "Invalid manifest"
listed = set()
for row in rows:
    rel = Path(row["File"])
    assert not rel.is_absolute() and ".." not in rel.parts, "Unsafe path"
    assert row["File"] not in listed, "Duplicate manifest record"
    listed.add(row["File"])
    path = root / rel
    assert path.is_file(), f"File missing: {rel}"
    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    assert digest == row["SHA256"].upper(), f"Hash mismatch: {rel}"

actual = {str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*")
          if p.is_file() and ".git" not in p.relative_to(root).parts and
          "__pycache__" not in p.relative_to(root).parts and
          ".pytest_cache" not in p.relative_to(root).parts and
          p.name != "RELEASE_MANIFEST.csv"}
assert listed == actual, f"Manifest coverage mismatch; extra={actual-listed}, missing={listed-actual}"
print(f"PASS: {len(rows)} files and hashes verified")
