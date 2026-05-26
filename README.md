# LLM Requirements Parser

## Overview

This repository benchmarks LLMs on Dutch access-control requirement extraction.

The pipeline is:

`input.json` with requirement text + floorplan context -> prompt assembly -> LLM call -> JSON validation -> benchmark comparison

The repo is intentionally experimental. It is used to compare model quality, prompt variants, and few-shot retrieval strategies.

## What Changed This Month

The repository moved from a simple text-only parser to a floorplan-aware benchmark harness.

- `input.json` is now the main input format for cases and knowledge-base examples.
- Floorplan context is included in both benchmark cases and few-shot examples:
  - `requirement_text`
  - `available_spaces`
  - `available_doors`
- Prompt assembly was split into reusable pieces:
  - `src/prompt_builder.py` builds the user prompt
  - `src/parser.py` builds the system prompt and wires the extraction call
- Few-shot examples are now dynamic:
  - they come from `tests/knowledge_base/`
  - they are retrieved by similarity on `requirement_text`
  - they are injected into the system prompt, not the user prompt
- The access-control prompt was tightened to better handle:
  - `buitendeuren` vs `binnendeuren`
  - `door_id` resolution
  - fallback when no matching door is found
- The knowledge base was expanded with more examples, including fallback cases where the door list is incomplete.
- Benchmark output now records separate timings:
  - LLM time
  - few-shot setup time
  - total wall-clock time
- Few-shot embeddings are cached locally so xdist workers can reuse the cache instead of rebuilding it every run.
- Hugging Face auth is supported through `HF_TOKEN` in `.env`.

## Project Structure

```text
.
├── prompts/                     # System prompt fragments and domain-specific instructions
│   ├── system_core.txt
│   ├── logic_rules.txt
│   └── access_control/
│       ├── schema_access_control.txt
│       ├── terminology_access_control.txt
│       └── examples_access_control.txt
│
├── src/                         # Runtime code
│   ├── llm_client.py            # Vendor routing and LLM call orchestration
│   ├── parser.py                # Prompt assembly and extraction entrypoints
│   ├── prompt_builder.py        # User prompt construction
│   ├── few_shot.py              # Knowledge base loading, retrieval, and embedding cache
│   ├── schema_access_control.py # Access-control schema
│   └── llm_types.py             # Shared result types
│
├── tests/                       # Benchmark cases and pytest harness
│   ├── cases/                   # Main benchmark cases
│   ├── knowledge_base/          # Few-shot examples
│   ├── conftest.py              # Pytest options and fixtures
│   ├── helpers.py               # Input loading, validation, normalization
│   ├── test_expected_output.py  # Main benchmark comparison test
│   └── test_prompt_builder.py   # Prompt assembly unit tests
│
└── README.md
```

## Input Format

Benchmark cases and knowledge-base examples use `input.json` with this shape:

```json
{
  "requirement_text": "De serverruimte krijgt een kaartlezer.",
  "language": "Dutch",
  "available_spaces": ["Serverruimte", "Hal", "Entree"],
  "available_doors": [
    {
      "door_id": "door_01",
      "space_a": "Hal",
      "space_b": "Serverruimte",
      "is_external": false
    }
  ]
}
```

The benchmark uses `input.json` cases only.

When `input.json` contains:

- `requirement_text`: the benchmark uses that text directly
- `pdf_path` without `requirement_text`: the benchmark first runs PDF page selection and text extraction

## Few-Shot Retrieval

Few-shot examples are dynamic.

- Similarity matching uses only `requirement_text`
- The examples shown to the model include the full floorplan context
- The examples are added to the system prompt
- The benchmark keeps the production-style user prompt separate from retrieval examples

The cached embeddings are written locally to:

`.cache/few_shot_embeddings.json`

That cache is reused across pytest-xdist workers.

## Environment

Create a `.env` file with the vendor keys you need.

For few-shot embeddings, you can also set:

```bash
HF_TOKEN=your_huggingface_token
```

The code maps `HF_TOKEN` to the Hugging Face auth environment expected by `sentence-transformers`.

## Running Tests

The main benchmark test is `tests/test_expected_output.py`.

Run a single model:

```bash
pytest tests/test_expected_output.py --models openai:gpt-5.2 --use-few-shot standard -n auto
```

Run with few-shot examples:

```bash
pytest tests/test_expected_output.py --models openai:gpt-5.2 --use-few-shot few-shot -n auto
```

Run both modes:

```bash
pytest tests/test_expected_output.py --models openai:gpt-5.2 --use-few-shot both -n auto
```

Run one case:

```bash
pytest tests/test_expected_output.py -k 004_group_with_addition --models openai:gpt-5.2 --use-few-shot standard -n auto
```

Run a PDF-backed case with an explicit page-finder strategy:

```bash
pytest tests/test_expected_output.py -k 051_real_test_1 --models openai:gpt-5.4 --pdf-strategy keyword -n 1 -v
pytest tests/test_expected_output.py -k 051_real_test_1 --models openai:gpt-5.4 --pdf-strategy hybrid -n 1 -v
```

Useful pytest options:

- `-q` for quieter output
- `-v` for verbose case names
- `-n auto` for parallel execution
- `--count 5` to repeat a case multiple times
- `--pdf-strategy toc|keyword|regex|hybrid|category|llm` for PDF-backed page selection experiments

## Timing Fields

Benchmark logs now record:

- `pdf_extraction_ms`: PDF loading, page selection, and selected-page text assembly
- `duration_ms`: LLM call time only
- `few_shot_setup_ms`: retrieval and context assembly time
- `total_duration_ms`: full wall-clock time for the case

That separation makes it easier to tell whether a slowdown comes from prompt prep, embedding/cache work, or the model call itself.

## Prompt Design

The prompt is modular and built from layered files in `prompts/`.

Current behavior:

- the system prompt contains the core instructions and, when enabled, the dynamic few-shot examples
- the user prompt contains the requirement text and floorplan context
- validation feedback is appended only when a retry is needed

## Notes

- This repo is optimized for comparison runs, not for production deployment.
- The knowledge base is intentionally broader than the benchmark cases so few-shot retrieval stays useful without mirroring the tests too closely.
- The few-shot cache is local only; it is not meant to be committed.
