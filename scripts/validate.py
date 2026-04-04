#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pyshacl import validate
from rdflib.compare import to_isomorphic
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF


REPO_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_TTL = REPO_ROOT / "ontology" / "daimo.ttl"
ONTOLOGY_OWL = REPO_ROOT / "ontology" / "daimo.owl"
SHAPES_TTL = REPO_ROOT / "shapes" / "daimo.shacl.ttl"
EXAMPLE_TTL = REPO_ROOT / "examples" / "daimo-example.ttl"
SPARQL_DIR = REPO_ROOT / "queries"
SPARQL_MANIFEST = SPARQL_DIR / "manifest.json"
EXPECTED_NAMESPACE = "http://purl.org/pionera/daimo#"
EXPECTED_PREFIX = "daimo"
ONTOLOGY_IRI = URIRef(EXPECTED_NAMESPACE)
VANN = Namespace("http://purl.org/vocab/vann/")


def parse_graph(path: Path, fmt: str) -> Graph:
    graph = Graph()
    graph.parse(path, format=fmt)
    return graph


def load_sparql_manifest(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, list):
        raise ValueError("SPARQL manifest must be a JSON array")
    return manifest


def run_meta_shacl(shapes_graph: Graph) -> tuple[bool, str]:
    conforms, _, report_text = validate(
        data_graph=shapes_graph,
        shacl_graph=None,
        meta_shacl=True,
        inference="none",
        abort_on_first=False,
    )
    return bool(conforms), str(report_text)


def run_data_validation(data_graph: Graph, shacl_graph: Graph, ont_graph: Graph) -> tuple[bool, str]:
    conforms, _, report_text = validate(
        data_graph=data_graph,
        shacl_graph=shacl_graph,
        ont_graph=ont_graph,
        inference="rdfs",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
        advanced=True,
    )
    return bool(conforms), str(report_text)


def run_sparql_suite(data_graph: Graph, manifest: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    failures: list[str] = []

    for entry in manifest:
        query_id = str(entry.get("id", "unknown"))
        query_file = SPARQL_DIR / str(entry.get("file", ""))
        min_rows = int(entry.get("min_rows", 0))

        if not query_file.is_file():
            failures.append(f"{query_id}: query file not found: {query_file}")
            continue

        try:
            query_text = query_file.read_text(encoding="utf-8")
            rows = list(data_graph.query(query_text))
            row_count = len(rows)
            if row_count >= min_rows:
                print(f"[OK] SPARQL {query_id} returned {row_count} rows (expected >= {min_rows})")
            else:
                failure = (
                    f"{query_id}: returned {row_count} rows, expected at least {min_rows}"
                )
                failures.append(failure)
                print(f"[FAIL] SPARQL {failure}")
        except Exception as exc:  # pragma: no cover
            failures.append(f"{query_id}: execution failed: {exc}")

    return not failures, failures


def run_ontology_metadata_checks(ontology_graph: Graph) -> tuple[bool, list[str]]:
    failures: list[str] = []

    if (ONTOLOGY_IRI, RDF.type, OWL.Ontology) not in ontology_graph:
        failures.append(f"Ontology IRI {ONTOLOGY_IRI} is not declared as owl:Ontology")
        return False, failures

    required_properties = {
        DCTERMS.title: "dcterms:title",
        DCTERMS.description: "dcterms:description",
        DCTERMS.creator: "dcterms:creator",
        DCTERMS.issued: "dcterms:issued",
        DCTERMS.modified: "dcterms:modified",
        OWL.versionInfo: "owl:versionInfo",
        OWL.versionIRI: "owl:versionIRI",
        VANN.preferredNamespacePrefix: "vann:preferredNamespacePrefix",
        VANN.preferredNamespaceUri: "vann:preferredNamespaceUri",
    }

    for predicate, label in required_properties.items():
        if not list(ontology_graph.objects(ONTOLOGY_IRI, predicate)):
            failures.append(f"Ontology metadata missing {label}")

    prefixes = {str(value) for value in ontology_graph.objects(ONTOLOGY_IRI, VANN.preferredNamespacePrefix)}
    if EXPECTED_PREFIX not in prefixes:
        failures.append(
            f"Expected preferred namespace prefix '{EXPECTED_PREFIX}' not found in ontology metadata"
        )

    namespaces = {str(value) for value in ontology_graph.objects(ONTOLOGY_IRI, VANN.preferredNamespaceUri)}
    if EXPECTED_NAMESPACE not in namespaces:
        failures.append(
            f"Expected preferred namespace URI '{EXPECTED_NAMESPACE}' not found in ontology metadata"
        )

    return not failures, failures


def run_namespace_consistency_checks() -> tuple[bool, list[str]]:
    failures: list[str] = []
    files_to_check = [ONTOLOGY_TTL, SHAPES_TTL, EXAMPLE_TTL, *sorted(SPARQL_DIR.glob("*.rq"))]

    for path in files_to_check:
        text = path.read_text(encoding="utf-8")
        if EXPECTED_NAMESPACE not in text:
            failures.append(f"Expected namespace not found in {path.relative_to(REPO_ROOT)}")

    return not failures, failures


def run_serialization_consistency_checks(ontology_ttl_graph: Graph, ontology_owl_graph: Graph) -> tuple[bool, list[str]]:
    failures: list[str] = []

    if not to_isomorphic(ontology_ttl_graph) == to_isomorphic(ontology_owl_graph):
        failures.append("Ontology Turtle and RDF/XML serializations are not graph-equivalent")

    return not failures, failures


def main() -> int:
    failures: list[str] = []

    print("Validating DAIMO ontology repository")
    print(f"Root: {REPO_ROOT}")

    try:
        ontology_graph = parse_graph(ONTOLOGY_TTL, "turtle")
        print(f"[OK] Parsed ontology: {ONTOLOGY_TTL}")
    except Exception as exc:  # pragma: no cover
        failures.append(f"Failed to parse ontology TTL: {exc}")
        ontology_graph = None

    try:
        ontology_owl_graph = parse_graph(ONTOLOGY_OWL, "xml")
        print(f"[OK] Parsed ontology RDF/XML: {ONTOLOGY_OWL}")
    except Exception as exc:  # pragma: no cover
        failures.append(f"Failed to parse ontology RDF/XML: {exc}")
        ontology_owl_graph = None

    try:
        shapes_graph = parse_graph(SHAPES_TTL, "turtle")
        print(f"[OK] Parsed SHACL shapes: {SHAPES_TTL}")
    except Exception as exc:  # pragma: no cover
        failures.append(f"Failed to parse SHACL shapes: {exc}")
        shapes_graph = None

    try:
        example_ttl_graph = parse_graph(EXAMPLE_TTL, "turtle")
        print(f"[OK] Parsed example TTL: {EXAMPLE_TTL}")
    except Exception as exc:  # pragma: no cover
        failures.append(f"Failed to parse example TTL: {exc}")
        example_ttl_graph = None

    try:
        load_sparql_manifest(SPARQL_MANIFEST)
        print(f"[OK] Parsed SPARQL manifest: {SPARQL_MANIFEST}")
    except Exception as exc:  # pragma: no cover
        failures.append(f"Failed to parse SPARQL manifest: {exc}")

    if shapes_graph is not None:
        try:
            meta_conforms, meta_report = run_meta_shacl(shapes_graph)
            if meta_conforms:
                print("[OK] Meta-SHACL validation passed")
            else:
                failures.append("Meta-SHACL validation failed")
                print("[FAIL] Meta-SHACL validation failed")
                print(meta_report)
        except Exception as exc:  # pragma: no cover
            failures.append(f"Meta-SHACL execution failed: {exc}")

    if ontology_graph is not None:
        metadata_conforms, metadata_failures = run_ontology_metadata_checks(ontology_graph)
        if metadata_conforms:
            print("[OK] Ontology metadata checks passed")
        else:
            failures.extend(metadata_failures)
            print("[FAIL] Ontology metadata checks failed")

    if ontology_graph is not None and ontology_owl_graph is not None:
        serialization_conforms, serialization_failures = run_serialization_consistency_checks(
            ontology_graph, ontology_owl_graph
        )
        if serialization_conforms:
            print("[OK] Turtle and RDF/XML ontology serializations are graph-equivalent")
        else:
            failures.extend(serialization_failures)
            print("[FAIL] Ontology serialization consistency checks failed")

    try:
        namespace_conforms, namespace_failures = run_namespace_consistency_checks()
        if namespace_conforms:
            print("[OK] Namespace is used consistently across ontology, shapes, example, and SPARQL queries")
        else:
            failures.extend(namespace_failures)
            print("[FAIL] Namespace consistency checks failed")
    except Exception as exc:  # pragma: no cover
        failures.append(f"Namespace consistency checks failed to execute: {exc}")

    if ontology_graph is not None and shapes_graph is not None and example_ttl_graph is not None:
        try:
            data_conforms, data_report = run_data_validation(example_ttl_graph, shapes_graph, ontology_graph)
            if data_conforms:
                print("[OK] Example graph conforms to SHACL shapes")
            else:
                failures.append("Example graph does not conform to SHACL shapes")
                print("[FAIL] Example graph does not conform to SHACL shapes")
                print(data_report)
        except Exception as exc:  # pragma: no cover
            failures.append(f"SHACL validation execution failed: {exc}")

    if example_ttl_graph is not None:
        try:
            manifest = load_sparql_manifest(SPARQL_MANIFEST)
            sparql_conforms, sparql_failures = run_sparql_suite(example_ttl_graph, manifest)
            if not sparql_conforms:
                failures.extend(sparql_failures)
        except Exception as exc:  # pragma: no cover
            failures.append(f"SPARQL suite execution failed: {exc}")

    if failures:
        print("\nValidation summary: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nValidation summary: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
