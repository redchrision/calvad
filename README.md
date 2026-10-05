# Calvad — Evidence, distilled.

Calvad is an early-stage, open-source research prototype for traceable AI-assisted evidence extraction and synthesis from scientific PDFs.

The project explores a simple principle: an LLM should be treated as an **untrusted candidate generator**, rather than as the final authority on what a research paper says.

Calvad combines AI-assisted extraction with source provenance, deterministic validation, human review and an auditable workflow.

> **Prototype status:** Calvad is an early-stage research prototype. The current MVP demonstrates the core evidence-extraction and verification workflow. It is not intended for production use or clinical decision-making.

## What works

The current prototype supports:

- Local project creation and persistence with SQLite
- Multi-PDF upload
- Page-aware PDF text extraction
- Researcher-defined extraction fields
- AI-assisted extraction using a locally running Ollama model
- Field-specific retrieval of potentially relevant passages
- Structured candidate extraction as `{value, evidence}`
- Independent deterministic matching of model-supplied evidence against the parsed source
- Deterministic field/value validation after source matching
- Missing and dropped candidate handling
- Evidence tables across documents and extraction fields
- Source inspection with page-level provenance
- Accept / Correct / Reject researcher review
- Persistent audit logging
- Synthesis restricted to evidence that has passed source matching and deterministic validation and has been accepted or corrected by the researcher
- CSV and JSON/provenance exports
- Model name recorded with extracted evidence
- Local-first model inference when Ollama is used

## Trust model

Calvad deliberately separates AI generation from verification and researcher review.

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

The LLM proposes candidate values and supporting evidence. Calvad then independently checks whether the supplied evidence can actually be located in the parsed source document.

A source match establishes **provenance**, not semantic correctness.

Candidates that pass source matching are subjected to deterministic field/value validation. Depending on the field, this can include checks such as expected value type, required units, textual support and rejection of known misleading contexts.

These deterministic checks are intentionally conservative and do **not** establish general semantic entailment or scientific correctness.

Human review therefore remains a separate part of the workflow. Researchers can accept, correct or reject extracted evidence before it is eligible for synthesis.

See `docs/ARCHITECTURE.md` for more detail.

## Why Calvad?

Generative AI can substantially reduce the effort involved in extracting information from research literature, but plausible-looking output is not sufficient for evidence synthesis.

Researchers need to be able to answer:

- Where did this extracted value come from?
- Does the cited supporting passage actually exist in the source?
- Did the candidate pass the system's deterministic checks?
- Has a researcher reviewed it?
- Which evidence was ultimately allowed into the synthesis?

Calvad is an experiment in making these questions part of the architecture rather than relying on model confidence alone.

## Current limitations

This is an MVP and several aspects of the system remain intentionally limited.

Current limitations include:

- Extraction currently runs sequentially and can be slow when using local models.
- Deterministic validation uses field-specific and textual rules; it does not prove semantic correctness.
- Retrieval is currently based on relatively simple field-specific heuristics rather than a mature retrieval system.
- PDF support targets normal text-based academic PDFs.
- Scanned PDFs requiring OCR are not currently supported.
- Complex tables and figures are not reconstructed.
- The current interface is designed for individual local use rather than multi-user collaboration.
- Authentication and institutional access controls are not implemented.
- Reference-manager integrations are not yet implemented.
- Provider abstraction beyond the current Ollama-based workflow remains future work.
- The prototype has not yet undergone production-scale performance, security or usability testing.

These limitations are active areas for further development rather than guarantees provided by the current prototype.

## Development directions

Areas being explored for subsequent development include:

- Faster and parallel extraction
- Improved retrieval and passage ranking
- Stronger deterministic field-specific validation
- Better handling of tables and structured scientific content
- Improved visual provenance and source highlighting
- Reference-manager and research-workflow integrations
- Model-provider abstraction for local, institution-hosted and external models
- Multi-project evidence synthesis
- Institutional deployment and access controls
- Evaluation against manually curated research datasets
- Formal measurement of extraction accuracy, verification failure modes and researcher time saved

## Local setup

### Requirements

You need:

- Python 3
- Node.js
- Ollama

The prototype is currently developed and tested primarily on macOS.

### 1. Install Ollama

Install Ollama using its official macOS installer and make sure the Ollama service is running.

The current prototype has been tested with:

```bash
ollama pull qwen2.5:7b
```

Other locally installed Ollama models can also be selected by entering their model name in Calvad. Results may vary between models.

### 2. Set up Calvad

Clone or download the repository and enter the project directory:

```bash
cd calvad-catalyst
./setup.sh
```

The setup script creates the Python environment, installs backend dependencies and installs frontend dependencies.

### 3. Start Calvad

Make sure Ollama is running, then:

```bash
./start.sh
```

The frontend is normally available at:

```text
http://127.0.0.1:5173
```

The FastAPI backend documentation is available locally at:

```text
http://127.0.0.1:8000/docs
```

### 4. Stop Calvad

Return to the terminal running Calvad and press:

```text
Control-C
```

## Technical architecture

```text
React / Vite UI
      |
FastAPI backend
      |
      |-- SQLite project / evidence / audit store
      |-- pypdf page-aware parser
      |-- field-specific passage retrieval
      |-- Ollama model adapter
      |-- structured extraction pipeline
      |-- deterministic source verifier
      |-- deterministic candidate validator
      |-- human review workflow
      |-- reviewed-evidence synthesis
      `-- CSV / JSON export
```

More detail is available in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Privacy

When Calvad is used with Ollama, model inference occurs locally and research PDFs are not sent by Calvad to an external model provider.

Uploaded documents and project data are stored locally by the prototype.

This does not constitute a general security or compliance guarantee: operating-system configuration, other software running on the machine and future external model integrations are outside the guarantees of the current prototype.

## Research and grant context

Calvad is currently being developed as a proof of concept for trustworthy AI-assisted evidence synthesis.

The MVP is intended to demonstrate the core architectural idea:

**AI proposes → the system checks → the researcher decides → reviewed evidence is synthesised.**

Further development would focus on evaluating this approach systematically, improving extraction performance and validation, reducing inference time, expanding document support and testing the workflow with real research users.

## License

The project is intended to be released as open-source software.

The final open-source licence should be confirmed before public release. Until a licence file is added to this repository, no open-source licence should be assumed.