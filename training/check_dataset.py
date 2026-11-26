"""Blocks training unless every image has documented adult consent.

Usage: python training/check_dataset.py training/dataset training/manifest.csv

manifest.csv columns:
  file, performer_id, date_of_birth (YYYY-MM-DD), capture_date (YYYY-MM-DD),
  id_document_ref, consent_form_path, ai_training_consent (yes/no)

Keep the ID documents and signed releases somewhere secure (not in git).
In the US, see the record-keeping rules in 18 U.S.C. 2257.
"""

import csv
import sys
from datetime import date
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def age_at(dob: date, when: date) -> int:
    return when.year - dob.year - ((when.month, when.day) < (dob.month, dob.day))


def main(dataset_dir: str, manifest_path: str) -> int:
    images = {p.name for p in Path(dataset_dir).iterdir() if p.suffix.lower() in IMAGE_EXTS}
    rows = {r["file"]: r for r in csv.DictReader(open(manifest_path, newline=""))}
    errors = []

    for name in sorted(images):
        r = rows.get(name)
        if r is None:
            errors.append(f"{name}: not in manifest")
            continue
        try:
            dob, captured = date.fromisoformat(r["date_of_birth"]), date.fromisoformat(r["capture_date"])
        except (KeyError, ValueError):
            errors.append(f"{name}: bad or missing dates")
            continue
        if age_at(dob, captured) < 18:
            errors.append(f"{name}: performer under 18 at capture. REMOVE IMMEDIATELY")
        if not r.get("id_document_ref"):
            errors.append(f"{name}: no ID document reference")
        if not r.get("consent_form_path") or not Path(r["consent_form_path"]).exists():
            errors.append(f"{name}: consent form missing")
        if r.get("ai_training_consent", "").lower() != "yes":
            errors.append(f"{name}: no consent for AI training")

    if errors:
        print("DATASET REJECTED:\n  " + "\n  ".join(errors))
        return 1
    print(f"OK: {len(images)} images, all with documented adult consent.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
