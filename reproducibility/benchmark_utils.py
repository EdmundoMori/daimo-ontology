from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path


REPRO_ROOT = Path(__file__).resolve().parent
CONTEXT_PATH = REPRO_ROOT / "context" / "climatebench_v1_demo_context.json"
EVAL_CONTEXT = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))

MODEL_SPECS = {
    "model1": {
        "display_name": "Model1",
        "expected_accuracy": Decimal("0.89"),
        "mistakes": set(range(90, 101)),
        "run_id": "run-2026-03-15-model1-001",
        "run_purpose": "Nightly benchmark inference on ClimateBench-v1 validation split",
        "run_status": "completed",
        "actor_name": "PIONERA MLOps operator",
        "started_at": "2026-03-15T10:00:00Z",
        "ended_at": "2026-03-15T10:12:34Z",
        "notebook_file": "model1-eval.ipynb",
        "results_file": "model1-results.csv",
        "audit_file": "model1-run-001.jsonl",
        "notebook_uri": "https://pionera.org/repro/model1-eval.ipynb",
        "results_uri": "https://pionera.org/repro/model1-results.csv",
        "audit_uri": "https://pionera.org/audit/model1-run-001.jsonl",
    },
    "model2": {
        "display_name": "Model2",
        "expected_accuracy": Decimal("0.82"),
        "mistakes": set(range(83, 101)),
        "run_id": "run-2026-03-15-model2-001",
        "run_purpose": "Candidate baseline benchmark on ClimateBench-v1 validation split",
        "run_status": "completed",
        "actor_name": "PIONERA MLOps operator",
        "started_at": "2026-03-15T11:00:00Z",
        "ended_at": "2026-03-15T11:06:12Z",
        "notebook_file": "model2-eval.ipynb",
        "results_file": "model2-results.csv",
        "audit_file": "model2-run-001.jsonl",
        "notebook_uri": "https://pionera.org/repro/model2-eval.ipynb",
        "results_uri": "https://pionera.org/repro/model2-results.csv",
        "audit_uri": "https://pionera.org/audit/model2-run-001.jsonl",
    },
}


def ensure_dirs(repro_root: Path) -> None:
    for folder in ("results", "audit", "executed"):
        (repro_root / folder).mkdir(parents=True, exist_ok=True)


def build_rows(mistakes: set[int]) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    for sample_id in range(1, EVAL_CONTEXT["sampleCount"] + 1):
        label = sample_id % 2
        prediction = 1 - label if sample_id in mistakes else label
        correct = int(prediction == label)
        rows.append(
            {
                "sample_id": sample_id,
                "label": label,
                "prediction": prediction,
                "correct": correct,
            }
        )
    return rows


def calculate_accuracy(rows: list[dict[str, int]]) -> Decimal:
    correct_predictions = sum(row["correct"] for row in rows)
    total_predictions = len(rows)
    return Decimal(correct_predictions) / Decimal(total_predictions)


def write_results_csv(results_path: Path, rows: list[dict[str, int]]) -> None:
    with results_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "label", "prediction", "correct"])
        writer.writeheader()
        writer.writerows(rows)


def write_audit_log(audit_path: Path, spec: dict[str, object], accuracy: Decimal) -> None:
    events = [
        {
            "event": "run_started",
            "runIdentifier": spec["run_id"],
            "status": "running",
            "actor": spec["actor_name"],
            "timestamp": spec["started_at"],
            "purpose": spec["run_purpose"],
        },
        {
            "event": "evaluation_completed",
            "runIdentifier": spec["run_id"],
            "status": spec["run_status"],
            "metric": EVAL_CONTEXT["metric"],
            "metricValue": format(accuracy, ".2f"),
            "dataset": EVAL_CONTEXT["evaluationDataset"],
            "datasetVersion": EVAL_CONTEXT["evaluationDatasetVersion"],
            "randomSeed": EVAL_CONTEXT["randomSeed"],
            "timestamp": spec["ended_at"],
        },
        {
            "event": "artifacts_materialized",
            "runIdentifier": spec["run_id"],
            "resultsFile": spec["results_file"],
            "notebookFile": spec["notebook_file"],
            "timestamp": spec["ended_at"],
        },
    ]

    with audit_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True))
            handle.write("\n")


def evaluate_model(repro_root: Path, model_key: str) -> dict[str, str]:
    ensure_dirs(repro_root)
    spec = MODEL_SPECS[model_key]
    rows = build_rows(spec["mistakes"])
    accuracy = calculate_accuracy(rows).quantize(Decimal("0.00"))
    expected_accuracy = spec["expected_accuracy"]

    if accuracy != expected_accuracy:
        raise ValueError(
            f"Unexpected accuracy for {model_key}: got {accuracy}, expected {expected_accuracy}"
        )

    results_path = repro_root / "results" / spec["results_file"]
    audit_path = repro_root / "audit" / spec["audit_file"]
    write_results_csv(results_path, rows)
    write_audit_log(audit_path, spec, accuracy)

    return {
        "model": str(spec["display_name"]),
        "accuracy": format(accuracy, ".2f"),
        "expected_accuracy": format(expected_accuracy, ".2f"),
        "results_path": str(results_path.relative_to(repro_root)),
        "audit_path": str(audit_path.relative_to(repro_root)),
        "run_id": str(spec["run_id"]),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def accuracy_from_results(results_path: Path) -> str:
    with results_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    correct_predictions = sum(int(row["correct"]) for row in rows)
    accuracy = Decimal(correct_predictions) / Decimal(len(rows))
    return format(accuracy.quantize(Decimal("0.00")), ".2f")


def build_package_manifest(repro_root: Path, executed_notebooks: list[str]) -> dict[str, object]:
    artifacts: list[dict[str, str]] = []
    models: list[dict[str, str]] = []

    for model_key, spec in MODEL_SPECS.items():
        notebook_path = repro_root / "notebooks" / str(spec["notebook_file"])
        results_path = repro_root / "results" / str(spec["results_file"])
        audit_path = repro_root / "audit" / str(spec["audit_file"])

        models.append(
            {
                "model": str(spec["display_name"]),
                "expected_accuracy": format(spec["expected_accuracy"], ".2f"),
                "observed_accuracy": accuracy_from_results(results_path),
                "run_id": str(spec["run_id"]),
            }
        )

        artifacts.extend(
            [
                {
                    "model": str(spec["display_name"]),
                    "artifact_type": "notebook",
                    "uri": str(spec["notebook_uri"]),
                    "local_path": str(notebook_path.relative_to(repro_root)),
                    "sha256": sha256_file(notebook_path),
                },
                {
                    "model": str(spec["display_name"]),
                    "artifact_type": "results",
                    "uri": str(spec["results_uri"]),
                    "local_path": str(results_path.relative_to(repro_root)),
                    "sha256": sha256_file(results_path),
                },
                {
                    "model": str(spec["display_name"]),
                    "artifact_type": "audit-log",
                    "uri": str(spec["audit_uri"]),
                    "local_path": str(audit_path.relative_to(repro_root)),
                    "sha256": sha256_file(audit_path),
                },
            ]
        )

    return {
        "evaluation_context": EVAL_CONTEXT,
        "executed_notebooks": executed_notebooks,
        "models": models,
        "artifacts": artifacts,
    }
