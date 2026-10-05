# Architecture

## Core trust boundary

The LLM is treated as an untrusted candidate generator.

```text
PDF
 |
 v
page-aware parse
 |
 v
field-specific retrieval
 |
 v
LLM candidate {value, evidence}
 |
 v
independent source verifier
 |                     \
 | source matched       \ source absent
 v                       v
deterministic           DROPPED / LOGGED
candidate validation
 |              \
 | valid         \ invalid
 v                v
VALIDATED       DROPPED / LOGGED
 |
 v
human review
(Accept / Correct / Reject)
 |
 v
reviewed evidence dataset
 |
 v
synthesis
```

The first deterministic gate asks a deliberately narrow question: can the evidence string supplied by the model be located in the parsed source, with a conservative prefix fallback for whitespace and extraction differences? A source match establishes provenance; it does not claim that the model's interpretation of the passage is semantically correct.

Candidates that pass source verification are then subjected to deterministic field and value validation. These checks depend on the extraction field and can include constraints such as expected value type, required units, textual support for the extracted value, and rejection of known misleading contexts. These rules are intentionally conservative and do not claim general semantic entailment.

Human review remains a separate gate. Researchers can accept, correct or reject extracted evidence. Synthesis is restricted to evidence that has passed source verification and deterministic validation and has subsequently been accepted or corrected by the researcher.

## Model abstraction

The MVP uses Ollama's local HTTP API. The model name is user-selectable and recorded with each evidence record. The architecture is intended to remain model-independent: future provider interfaces can add OpenAI, Anthropic or institution-hosted endpoints without changing the provenance, validation, human-review or audit layers.

## Storage

SQLite stores project metadata, extraction fields, evidence records, validation results, researcher reviews, synthesis and audit events. Uploaded PDFs are stored in `data/uploads/`. These runtime artifacts are gitignored.