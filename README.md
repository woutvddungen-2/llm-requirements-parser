# Access Control Requirement Parser (Experiment)

## Overview

This project experiments with using an LLM to convert natural language specifications into structured access control requirements.

Input: plain text (client specification)
Output: validated JSON (based on a strict schema)



## How it works

```
Text → LLM → JSON → Pydantic validation
```

* The LLM extracts requirements
* Output is validated against a Pydantic schema
* Invalid output is rejected



## Workflow (Notebooks)

The main experimentation is done in notebooks.

Typical flow:

1. Open the notebook
2. Load example input text
3. Generate / load schema prompt
4. Run LLM extraction
5. Validate output using Pydantic




## Project Structure

```id="c4v2m1"
.
├── README.md                    # Project overview and usage
├── convert_schema.py           # Generates schema files for LLM + validation
├── example_diemen.txt          # Example input specification
├── main.py                     # Simple entry point (non-notebook usage)
├── requirements.txt            # Python dependencies
│
├── json/                       # Generated JSON schemas (validation/debugging)
│   └── schema_access_control.json
│
├── notebooks/                  # Main experimentation environment
│   └── 01_extraction_test.ipynb
│
├── prompts/                    # Modular LLM prompt components
│   ├── system_core.txt         # Base system prompt (role + instructions)
│   ├── formatting_rules.txt    # Output format constraints
│   ├── normalization_rules.txt # Text normalization rules
│   ├── conflict_rules.txt      # Conflict resolution logic
│   │
│   └── access_control/         # Domain-specific prompt components
│       ├── schema_access_control.txt
│       ├── terminology_access_control.txt
│       └── examples_access_control.txt
│
├── src/                        # Core logic
│   ├── __init__.py
│   ├── llm_client.py           # LLM interaction layer
│   ├── parser.py               # Prompt assembly + parsing pipeline
│   ├── schema.py               # Pydantic schema (source of truth)
│   └── schema_rules.json       # Rules for schema → prompt conversion
│
└── tests/                      # (Future) test cases and validation
```

## Notes on Structure

* **Notebooks-first workflow**
  Experiments and development are primarily done in `notebooks/`.

* **Separation of concerns**

  * `schema.py` → structure & validation
  * `schema_rules.json` → prompt behavior
  * `convert_schema.py` → schema generation
  * `parser.py` → runtime pipeline

* **Prompt modularity**
  Prompt is split into reusable layers:

    * core behavior
    * formatting
    * normalization
    * conflict handling
    * domain-specific logic

## Usage

### 1. Generate schema (when schema changes)

```bash
python convert_schema.py
```

### 2. Run experiments

Open the notebooks and execute cells step-by-step.



## Key files

* `schema.py` → structure & validation
* `schema_rules.json` → prompt behavior
* `convert_schema.py` → generates LLM schema
* `parser.py` → reusable parsing logic


## Notes

* Schema generation is manual
* Keep `schema_access_control.txt` in sync with schema changes
* This repo is experimental and will evolve
