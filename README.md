# Pairwise Lab

A local workspace for evaluating AI responses through blind pairwise comparisons, structured scores, and written reasoning.

**Status: working first version, built with AI assistance.** Demo responses are synthetic examples, not outputs from real models or evidence of model performance. This project does not generate responses or call an AI provider yet.

## Why this project

AI response evaluation involves more than choosing which answer sounds nicer. A useful judgment should identify specific errors, check whether instructions were followed, and leave a record that another reviewer can understand. Pairwise Lab makes that process visible and repeatable.

## Run locally

Requires Python 3.11 or newer. No external packages, API keys, or paid services are required.

```bash
git clone https://github.com/ptrckdeja/Pairwise-lab.git
cd Pairwise-lab
python server.py --seed examples/comparisons.json
python server.py
```

Open **http://127.0.0.1:8000**. On Windows, use `py` in place of `python` if needed. Run the seed command once per database; repeated imports intentionally create new comparisons.

1. Select a comparison in the queue.
2. Read both responses without model names.
3. Score correctness, clarity, and instruction following from 1 to 5.
4. Choose A, B, tie, or neither, and explain your reasoning.
5. Save to reveal model identities and update the summary.
6. Export reviewed comparisons as JSON.

You can also start with an empty database and import the example JSON through the interface. Use `--db other.sqlite3` for an isolated dataset and `--port 8080` for a different local port.

## Features

- Persisted random assignment to A/B positions on import
- Model names withheld by the pending-comparison API, not just hidden in CSS
- Required rubric scores and written explanations
- Immutable saved reviews, with model reveal after saving
- Queue filters and descriptive model statistics
- Atomic, validated JSON imports and versioned review exports
- SQLite persistence, local-only server, responsive interface
- Automated persistence and HTTP integration tests

## Rubric

| Criterion | 1 · Poor | 3 · Adequate | 5 · Excellent |
| --- | --- | --- | --- |
| Correctness | Major factual or functional errors | Mostly correct; meaningful gaps | Correct, with relevant edge cases handled |
| Clarity | Confusing or difficult to follow | Understandable with some friction | Clear, direct, and well organized |
| Instruction following | Misses core requirements | Meets most requirements | Meets all explicit requirements |

Use 2 and 4 for judgments between these anchors. Overall preference is a separate human judgment; the app does not automatically infer it from the numeric scores.

## Import format

Upload a JSON array of 1–100 objects. Imports are capped at 2 MB. Every object requires these strings:

```json
[
  {
    "prompt": "Explain a cloud concept in two sentences.",
    "category": "Cloud explanations",
    "model_a": "model-name/version-1",
    "response_a": "First candidate answer.",
    "model_b": "model-name/version-2",
    "response_b": "Second candidate answer."
  }
]
```

Model names must be distinct. Names and categories are limited to 200 characters; prompts and responses to 20,000 each. The importer may swap candidates; never assume imported `model_a` remains display A. All rows are validated before any are written. Invalid batches leave the database unchanged. Exports contain completed reviews only and are a different schema; export re-import is not supported in this version.

## Architecture and engineering decisions

`static/app.js` → JSON HTTP API (`server.py`) → evaluation rules (`store.py`) → SQLite.

- **Standard library backend:** easy to run and audit without a dependency installation step. Python's built-in HTTP server suits a local prototype; replace it with a production server before internet hosting.
- **Separate persistence rules:** validation and blinding can be tested without HTTP or browser automation.
- **Immutable reviews:** once model identities are revealed, silently editing the original judgment would compromise the blind-review record. A future revision feature should append a new record with its own provenance.
- **Stored random ordering:** the response-to-model mapping survives page reloads. This reduces position bias but does not guarantee anonymity if response text identifies the model.
- **Plain-text response rendering:** untrusted responses are rendered with `textContent`; HTML and Markdown are not executed.
- **Explicit ties and neither:** reviewers can distinguish equal quality from two unacceptable responses.

This is a single-reviewer local tool. The person operating it has access to the original import and database; blinding is a workflow aid, not a security boundary against that person. Aggregate scores depend on sample selection, opponent mix, and rubric consistency. Small or unbalanced samples cannot establish a reliable model ranking.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/comparisons` | Queue without model identities |
| GET | `/api/comparisons/{id}` | Blind content; saved review and identities after review |
| POST | `/api/import` | Import comparison array atomically |
| POST | `/api/reviews/{id}` | Save one immutable review |
| GET | `/api/summary` | Reviewed sample statistics |
| GET | `/api/export` | Completed reviews; `schema_version: 1` |

POST requests require `Content-Type: application/json`. Invalid inputs return 400, missing comparisons 404, duplicate reviews 409, oversize bodies 413, and unsupported content types 415. Cross-origin writes and unexpected Host headers are blocked. The server binds to loopback only. It has no accounts, authentication, or multi-user access control.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests cover identity hiding, response/model mapping, atomic imports, score validation, immutable reviews, aggregate outcomes, HTTP save/reveal/export, invalid JSON, origin checks, and static file access restrictions. GitHub Actions runs the suite on Python 3.11 and 3.12.

## Data and privacy

Data stays in the SQLite file you choose. Database files and exports are excluded from Git. Do not import confidential work or personal information into a repository; use synthetic or authorized public samples. There is no telemetry or external network call in the app.

## Next development work

- [ ] Add prompt tags and category-level analysis
- [ ] Import JSONL datasets with duplicate detection and source provenance
- [ ] Add reviewer calibration examples with documented expected judgments
- [ ] Add append-only review revisions and disagreement analysis
- [ ] Add provider adapters for generating real response pairs, with explicit cost controls
- [ ] Add browser automation and accessibility checks
- [ ] Explore a production backend and authenticated multi-reviewer workflow

## AI assistance and ownership

This initial implementation was created with an AI coding assistant. Commit history should reflect actual work, without backdating or claiming a longer development history. Before using the project in an application, run it yourself, review the implementation, and make changes you can explain. Describe its current capabilities accurately; planned features are not completed features.
