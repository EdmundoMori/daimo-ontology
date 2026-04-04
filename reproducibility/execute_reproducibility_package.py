#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

from benchmark_utils import MODEL_SPECS, REPRO_ROOT, build_package_manifest, ensure_dirs


NOTEBOOK_DIR = REPRO_ROOT / "notebooks"
MANIFEST_PATH = REPRO_ROOT / "package_manifest.json"


def execute_notebook(notebook_path: Path) -> Path:
    notebook = nbformat.read(notebook_path, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=120,
        kernel_name="python3",
        resources={"metadata": {"path": str(notebook_path.parent)}},
    )
    executed = client.execute()

    executed_path = REPRO_ROOT / "executed" / f"{notebook_path.stem}.executed.ipynb"
    nbformat.write(executed, executed_path)
    return executed_path


def main() -> int:
    ensure_dirs(REPRO_ROOT)

    executed_notebooks: list[str] = []
    print("Executing reproducibility notebooks")

    for spec in MODEL_SPECS.values():
        notebook_path = NOTEBOOK_DIR / str(spec["notebook_file"])
        executed_path = execute_notebook(notebook_path)
        executed_notebooks.append(str(executed_path.relative_to(REPRO_ROOT)))
        print(f"[OK] Executed notebook: {notebook_path.name}")

    manifest = build_package_manifest(REPRO_ROOT, executed_notebooks)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[OK] Wrote package manifest: {MANIFEST_PATH}")

    for model in manifest["models"]:
        expected = model["expected_accuracy"]
        observed = model["observed_accuracy"]
        if observed != expected:
            print(
                f"[FAIL] Accuracy mismatch for {model['model']}: "
                f"observed {observed}, expected {expected}"
            )
            return 1
        print(
            f"[OK] {model['model']} observed accuracy {observed} "
            f"matches expected accuracy {expected}"
        )

    print("Reproducibility package: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
