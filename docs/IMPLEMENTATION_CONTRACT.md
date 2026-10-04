# Harness v1 implementation contract

Python 3.10+, standard library only. Run from repository root as `python3 -m tastex`.
The immutable source DB stays at `flavor-database/flavor.sqlite`; no module writes it.
Runtime generated outputs are in `runs/` and the separate experience store is in `local/experience.sqlite`.
No fabricated sensory observations are shipped as real experience.

## Brief v1 shape

```
schema_version: "1.0"
case_id: string; revision: string; request_text: string
product: {name, matrix, development_stage, intended_use, storage_requirement: null|string}
targets: [{dimension, intent, reference: null|string, acceptance: null|object}]
constraints: [{id, kind: "hard"|"preference", text, status: "confirmed"|"assumed"|"unresolved"}]
ingredients: [{key, label, query, requested_state, role,
  reference_id: null|string, identity_relation: "exact"|"different_state"|"unresolved"}]
assumptions: [{id, text, status: "assumed"|"unresolved"|"confirmed", consequence}]
routes: [{id, title, status: "selected_for_screening"|"alternative"|"deferred",
  rationale, advantages: [string], limitations: [string], evidence_refs: [string],
  parameters: [{name, value: null|number|string, unit, origin: "user"|"source"|"hypothesis", basis}]}]
design: {basis_g: number, base_key: string, sample_base_g: number,
  factors: [{key, levels_g: [number], origin: "hypothesis"|"source"|"user", rationale}],
  constants: [{key, grams_per_basis: number}], native_control: bool,
  planned_batches: integer, seed: integer, wait_minutes: number,
  dimensions: [string], preparation_notes: [string]}
```

The prototype stage is explicit; unknown product acceptance and shelf-life are unresolved, not automatically invented.
All quantities are g per basis_g of finished base, not raw meat. Ingredient key identifiers map factor, constant and base references.

## Module API

`tastex.retrieval.collect_evidence(brief, db_path, aliases_path) -> dict`:
Return deterministic JSON-compatible evidence bundle with keys `ingredients`, `queries`, `gaps`, `provenance`.
Each ingredient item: key, input_query, expanded_queries, candidate_ids, reference_id, requested_state, identity_relation,
full profiles and evidence/processing links for reference_id, page hits/full text with page provenance.
Query both structured processing and book_pages ALWAYS, not only when structured returns zero. Log all results and zero hits.
Do not union category vectors into one truth or treat related_context links as exact evidence. Pair probes must preserve source direction.
Reviewed search aliases are configuration, never a silent modification of source identity. The core API can be imported using sys.path.

`tastex.experiments.build_design(brief) -> dict`:
Full factorial of factors + optional unchanged native base control. Stable cell IDs, factor mass and total mass per sample,
batch labels, blinded code mapping and seeded order for each planned batch. Preserve both design-basis and actual sample quantities.
Return `cells`, `batches`, `metrics`, `warnings`, `template` (valid observation skeleton), `contrasts` and `analysis_limits`.
Template fields align below. All actual outcomes null. Validate finite/nonnegative quantities, mass balance and unique keys.
Cannot describe a factorial interaction or actual effect as measured before outcomes exist.

`tastex.experience.ExperienceStore(path)` with context manager:
- `record(observation, run_dir: Path) -> dict`: validates against persisted brief/design/manifest and appends immutable event.
- `search(scope: dict, include_near: bool=False) -> dict`: exact matching by default; relaxed matches explicitly labeled.
- `summarize(scope: dict) -> dict`: counts, missingness, within-cell variation, conflicts and observed ranges with scope; no automatic causal rules.
- `verify() -> dict`: event hash-chain integrity.
- `analyze(run_dir) -> dict`: current human records only; paired signed design contrasts within one batch and participant, preserving missingness and actual-mass/lot limits.

Observation v1: `{schema_version:"1.0", observation_id, case_id, revision, run_id,
 batch_id, cell_id, participant_id, observed_at, scope:{matrix,ingredient_state,process,serving_context},
 material_lots:{ingredient_key:nonempty_string}, actual_masses_g:{ingredient_key:number},
 ratings:{dimension:number|null}, scale:{min:0,max:10}, free_description,
 disposition:"acceptable"|"reject"|"mixed"|"not_evaluated", notes,
 origin:"human_observed"|"synthetic_test", supersedes:null|string}`.
Require human_observed for normal writes, source run hashes match, batch/cell and exact ingredient keys exist,
required identifiers/timestamps and complete 0..10 dimensions (null allowed explicitly), materials recorded for actual nonzero ingredients; zero-mass materials may omit lot or use null.
Synthetic data is test-only with an explicit allow_synthetic constructor option, isolated temporary DB.
Append corrections using supersedes, never UPDATE/DELETE past observations. Idempotent identical event is safe; duplicate ID with changed content errors.
Summaries use latest non-superseded entries, disclose exclusions and do not call one batch a validated rule.

## Root-owned integration

Root writes `tastex/__main__.py`, `tastex/validation.py`, `tastex/workflow.py`, reports, schemas/brief.schema.json,
configs, pyproject, repository docs, CI and publication. Run outputs names: `brief.json`, `evidence.json`, `design.json`,
`report.md`, `observation-template.json`, `manifest.json`, `events.jsonl`.
manifest has `schema_version`, `run_id`, `case_id`, `revision`, `database_sha256`, `config_sha256`, `brief_sha256`,
`artifacts` mapping filename to sha256, `workflow_version`, and `input_paths` with relative metadata only.
Run ID is content-derived from brief, database hash, alias config hash and workflow source fingerprint; output directory never overwritten.
`replay` verifies original artifact hashes and uses exact inputs; compares deterministic artifact hashes. Runtime time is kept out of deterministic content.
