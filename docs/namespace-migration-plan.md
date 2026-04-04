# DAIMO Namespace Migration Plan

This document describes how to migrate DAIMO from the current PURL namespace to a different persistent namespace after the first successful Ontoology publication.

## Why the migration should happen after the first public release

The first public Ontoology release should validate that:

- the curated repository structure is correct
- the ontology metadata is sufficient for publication
- Ontoology can generate documentation and evaluation artifacts from the repository
- the GitHub publication workflow is stable

Only after these points are confirmed should the namespace be changed. Otherwise, publication errors and namespace errors become mixed together.

## Recommended target

If the namespace is moved away from PURL, the recommended target is a persistent identifier such as:

`https://w3id.org/def/daimo#`

This is only a recommended pattern. The final target should be confirmed before migration and reserved through the appropriate persistent identifier process.

## Important principle

The future namespace should be a persistent ontology identifier.

It should not be an Ontoology documentation URL such as `https://ontoology.linkeddata.es/...`, because those URLs identify generated documentation pages rather than the canonical ontology namespace itself.

## Migration scope

The namespace migration affects more than the ontology file. At minimum, the following repository components must be updated in one coordinated release:

- `ontology/daimo.ttl`
- `shapes/daimo.shacl.ttl`
- `examples/daimo-example.ttl`
- `queries/`
- `scripts/validate.py`
- `README.md`
- `docs/`
- `CITATION.cff`
- diagrams and screenshots if they display the namespace
- article PDFs and LaTeX sources if the namespace is explicitly cited there

## Safe migration sequence

1. Freeze the current public PURL-based release as version `1.x`.
2. Create a dedicated migration branch.
3. Replace the namespace consistently across ontology, shapes, examples, queries, documentation, and article sources.
4. Update ontology metadata:
   - ontology IRI
   - `vann:preferredNamespaceUri`
   - `owl:versionIRI`
   - `dcterms:modified`
   - version number
5. Re-run the repository validation.
6. Review all generated SPARQL queries and example data for stale namespace strings.
7. Publish the migrated repository as a new major release, e.g. `2.0.0`.
8. Re-run Ontoology on the migrated repository and review the new pull request.

## Backward-compatibility recommendation

Changing the namespace changes ontology term IRIs, so it should be treated as a breaking change.

For that reason, the migration should keep a clear bridge between the old and new releases:

- keep the old PURL-based release available
- document the namespace change explicitly in the changelog and README
- publish the migrated ontology as a new major version
- if necessary, provide an auxiliary alignment or transition file that maps the old and new terms

## Practical release policy

The cleanest publication policy is:

- `1.x`: first public Ontoology release with the current PURL namespace
- `2.0.0`: first release with the new persistent namespace

This makes the change explicit for reviewers, users, and future citations.
