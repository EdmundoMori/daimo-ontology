## DAIMO ontology serializations

This folder contains the public ontology serializations used in the DAIMO publication repository.

- `daimo.ttl` is the canonical working serialization in Turtle.
- `daimo.owl` is the RDF/XML serialization generated from the same ontology.

Both files are expected to remain synchronized. The repository validation checks that:

- both serializations parse correctly, and
- both serializations are graph-equivalent.
