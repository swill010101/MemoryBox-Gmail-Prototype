# MBPRD-P2-I11A.0 — Narration Model and Context Benchmark

**Version:** 0.4  
**Date:** 2026-09-27  
**Status:** Founder-approved scope; Gate 1 accepted 2026-09-26; Gate 3 legacy-chunk series historical; I14 cleaned source Phase 1 frozen pending founder authorization of the remaining Qwen B ladder  
**Clerical correction:** section 10.5 says “all three exact model configurations,” per founder direction 2026-09-26.  
**Roadmap position:** Immediately after accepted P2-I14 and before P2-I15 and resumed P2-I11A narration work  
**Primary environment:** FlightSim, Windows 11, NVIDIA RTX 4090 24 GB, Ollama

**Source rule (v0.4):** The seven `CHUNK_00N_MODEL_PASTE.txt` files under `REVIEW_20260831T120929Z` established preliminary Qwen B behavior and hardware bounds. They remain historical evidence. The final production-representative operating point will be determined from a frozen accepted-I14 cleaned household-email Communications export. Do not continue the capacity ladder on the legacy seven chunks. Every benchmark result must record source identity, I14 generation/algo version, and file hashes.

## 1. Purpose

P2-I11A.0 establishes the local narration model, quantization, and production-safe evidence chunk size that MemoryBox will use when P2-I11A resumes.

The increment creates a repeatable benchmark job that runs narrative generation against progressively larger evidence chunks, captures performance and resource measurements, preserves every result, detects the point at which performance begins to degrade, and recommends a production operating point.

The increment must finish before returning to the Peggy narrative proof. Its output is a measured operating envelope and a founder-approved model configuration—not a completed Peggy narrative.

## 2. Product rationale

MemoryBox narration must be accurate, readable, emotionally appropriate, evidence-backed, and practical on the available 24 GB GPU. A model with stronger prose but excessive memory use, slow execution, CPU spill, or an impractically small evidence window is not the better production choice.

The selection principle is:

> Choose the model and configuration that deliver the highest acceptable narrative quality while remaining completely GPU-resident, operationally stable, and fast enough for the intended MemoryBox workflow.

The benchmark measures capacity and performance. A separate controlled comparison assesses narration quality. Neither result alone selects the production model.

## 3. Roadmap placement and dependencies

### 3.1 Sequence

1. P2-I14 Communications and Unified Gallery accepted.
2. P2-I11A.0 Narration Model and Context Benchmark completed and accepted.
3. P2-I11A resumes with the controlled Peggy narrative proof.
4. P2-I15 stabilization, UX consistency, and operations work remains postponed until after I11A Redux unless the founder changes the sequence.
5. Broader hierarchical/person narration proceeds only through later approved gates.
6. Words of a Life remains later work and is not authorized by this increment.

### 3.2 Required inputs

- The P2-I14 normalized communications representation is available.
- Immutable originals and provenance remain intact.
- Cleaned evidence preserves authored-versus-quoted, forwarded, copied, and boilerplate boundaries.
- Existing P2-I11A narration runner, prompts, telemetry, Peggy packet/chunks, and artifact code are inventoried for reuse.
- Ollama and NVIDIA telemetry are available on FlightSim.

## 4. Goals

1. Build a parameter-driven narration benchmark program.
2. Build one single-launch script/application that automatically executes the complete benchmark cycle at increasing token targets without operator action between runs.
3. Increase evidence input in 1,000-token steps during the primary sweep.
4. Measure model, runtime, token, GPU, memory, and output behavior for every run.
5. Stop before deliberate failure or material CPU spill.
6. Detect the performance knee using repeated, measurable deterioration rather than raw elapsed time alone.
7. Refine the stable boundary using 250-token steps.
8. Screen three founder-approved model configurations using identical Peggy evidence and prompts, then refine quantization only for finalists when it answers a documented quality-versus-context question.
9. Recommend a production model, quantization, context allocation, input chunk size, and output reserve.
10. Save run statistics and review results in a downloadable Excel workbook and machine-readable files while preserving full narration artifacts separately.

## 5. Non-goals

This increment does not:

- Complete the Peggy narrative.
- Run the entire Peggy corpus.
- Implement multi-stage or hierarchical summarization.
- Generate a Words of a Life poster or language profile.
- Replace or rewrite immutable source evidence.
- Select a model from generic public benchmarks alone.
- Intentionally force an out-of-memory crash.
- Treat CPU spill or partial GPU residency as a successful 24 GB GPU result.
- Add a user-facing MemoryBox screen unless required later by a separately approved operations increment.

## 6. Initial candidate configurations

### 6.1 Configuration A — larger Qwen MoE

The first benchmark candidate is:

- **Model:** Qwen3-30B-A3B-Instruct-2507
- **Ollama tag:** `qwen3:30b-a3b-instruct-2507-q4_K_M` when available; otherwise the installed `qwen3:30b` alias is allowed only after its digest and metadata prove it resolves to the same model and quantization.
- **Initial quantization:** Q4_K_M
- **Mode:** Instruct
- **Reason for first position:** Strong instruction following and creative-writing potential, with mixture-of-experts execution that may provide useful narration quality within the 24 GB GPU constraint.

The exact model digest must be recorded so future runs are reproducible even if an Ollama tag changes.

### 6.2 Configuration B — medium Qwen dense model

The second benchmark candidate is:

- **Model:** Qwen3 14B dense instruction model
- **Ollama tag:** `qwen3:14b-q8_0`
- **Initial quantization:** Q8_0
- **Reason for inclusion:** It uses less model memory than the 30B-A3B Q4 configuration while retaining higher numerical precision, leaving more of the 24 GB GPU available for Peggy evidence and output context.

The exact installed digest must be recorded. The application may not substitute the Q4 version during the initial screen.

### 6.3 Configuration C — preserved Gemma baseline

The preserved comparison baseline is:

- **Model:** Gemma 4 26B
- **Ollama tag:** `gemma4:26b`
- **Digest:** Record and pin the exact installed digest at runtime before the benchmark begins.
- **Initial temperature:** 0.1, matching the earlier approved I11A benchmark unless a founder-approved comparison plan changes it.
- **Historical context:** The earlier unsafe test used approximately 180,000 input tokens with `num_ctx=262144`; that result is retained as historical evidence but is not repeated.

The builder must inventory the exact installed Gemma 4 26B quantization, digest, context settings, and prior prompt behavior used during the earlier I11A work. The benchmark may not silently substitute another Gemma version, quantization, or digest.

### 6.4 Candidate-control rule

The initial screen is limited to Configurations A, B, and C. Other model families, base sizes, or quantizations are not part of the initial benchmark.

After the initial screen, an alternate quantization may be tested only for a finalist and only when it answers a documented question, such as whether reduced model memory creates enough additional Peggy context to offset any loss in narrative quality. Every added finalist configuration must use the same benchmark method, Peggy evidence contract, stop rules, and acceptance criteria.

This increment is not an open-ended model tournament. A new model family or non-finalist configuration requires founder approval.

## 7. Benchmark architecture

### 7.1 Components

The implementation should contain separable components:

1. **Evidence builder** — constructs a target-sized evidence chunk without splitting a communication thread when avoidable.
2. **Narration runner** — submits the fixed narration prompt and evidence to Ollama.
3. **Telemetry sampler** — records GPU, VRAM, system memory, timing, and residency behavior.
4. **Sweep controller** — advances through configured token targets and applies stop rules.
5. **Artifact writer** — preserves prompts, inputs, outputs, errors, configuration, and hashes.
6. **Workbook writer** — appends normalized run and review data to the Excel workbook.
7. **Analyzer** — identifies the stable range, performance knee, and recommended operating point.
8. **Model lifecycle controller** — verifies installation and digest, unloads the prior model, confirms VRAM release, loads the next exact model, performs cold/warm preparation as configured, and verifies readiness before testing continues.

### 7.2 Reuse requirement

The builder must inventory P2-I11A before writing replacement code. Existing narration execution, prompt loading, timeout handling, Ollama response parsing, logging, evidence citation, and artifact naming should be reused or refactored when sound.

Any I11A code not reused must be identified with the reason it was unsuitable. This increment must not create a parallel narration system without justification.

## 8. Evidence construction

### 8.1 Token-based sizing

Evidence sizes must be controlled by tokens, not bytes or characters. The recorded value must include:

- Requested evidence-token target.
- Actual evidence tokens.
- System and narration prompt tokens.
- Total prompt tokens reported by Ollama.
- Reserved maximum output tokens.
- Configured total context window.

### 8.2 Evidence integrity

- Preserve chronological order.
- Preserve complete thread boundaries whenever possible.
- Do not split an individual message except when explicitly running a synthetic capacity test.
- Preserve evidence IDs and provenance.
- Preserve speaker/author distinctions.
- Mark partial first or last threads when exact target sizing requires a boundary compromise.
- Hash the exact input used for every run.

### 8.3 Benchmark evidence sets

Use two evidence tracks:

1. **Capacity set:** A deterministic, expandable evidence sequence used for the increasing-size sweep.
2. **Quality set:** One or more manually verified gold-standard chunks with expected facts, chronology, exclusions, uncertainties, and prohibited conclusions.

The same quality evidence and prompt must be used for every model comparison.

### 8.4 Peggy evidence baseline

I11A.0 is a model/configuration and effective-context benchmark. Narrative packets include both Peggy-authored and Tom-authored messages when both are part of the relevant exchange, with explicit author attribution on every message.

- **Historical source:** the founder-reviewed seven chunks (`REVIEW_20260831T120929Z` / `CHUNK_00N_MODEL_PASTE.txt`) remain the hardware/upper-bound series already run. They are noisy (quoted history, boilerplate, tracking links). Do not use them for the remaining Qwen B ladder or as the final operating-point recommendation.
- **Production-representative source:** a deterministic freeze of the accepted I14 Communications store: `comms_prepared_active_generations` / `i14-prepared-email-v3` / `cleaned_authored_text`. Gallery `left(cleaned_authored_text, N)` previews are not the source.
- **I11A.1 later:** “Words of a Life” will use only Peggy-authored spoken/cleaned words (Peggy-only inventory / `voice_corpus` subset). I11A.1 is not started by this increment.
- Preserve source identity, generation UUID, algo version, generation checksum, and export file hashes on every result. Old-source and cleaned-source runs must not be mixed into one regression series.
- Immutable originals remain in `evidence` (`payload_json`). The benchmark prompt uses cleaned authored text plus provenance pointers, not excluded original noise.
- Synthetic evidence may be used only for unit or failure-path tests, not for founder quality selection.

## 9. Run parameters

The runner must support configuration through command-line parameters or a versioned configuration file, including at minimum:

```text
model
model_digest
input_source
prompt_version
start_input_tokens
increment_tokens
refinement_increment_tokens
maximum_input_tokens
reserved_output_tokens
context_window
temperature
seed
thinking_mode
warm_runs_per_size
timeout_seconds
maximum_total_seconds
maximum_vram_gb
minimum_prompt_tokens_per_second
minimum_generation_tokens_per_second
regression_percentage
regression_run_count
output_directory
workbook_path
results_bundle_path
manage_model_lifecycle
```

Defaults must be explicit, recorded with every run, and overridable without code changes.

## 10. Execution method

### 10.1 Environment control

Before the sweep:

- Record Windows, NVIDIA driver, CUDA/runtime, Ollama, application, and benchmark versions.
- Record GPU model and total VRAM.
- Confirm no other GPU-heavy MemoryBox, Immich, transcription, face, voice, or unrelated job is active.
- Record baseline GPU and system-memory usage.
- Confirm the requested model is fully loaded as expected.

### 10.2 Primary sweep

Initial recommended defaults:

- Start at 8,000 evidence tokens.
- Increase by 1,000 evidence tokens.
- Reserve 2,000–3,000 tokens for narration output; final value is configurable.
- Perform one cold characterization run per model.
- Perform at least two warm runs at each tested size.
- Continue only while the VRAM and performance rules remain satisfied.

After founder authorization, one operator command must launch the complete benchmark cycle. The controller must perform preflight, finish each run, persist all artifacts, evaluate the stop rules, advance to the next token size, confirm suspicious results, execute boundary refinement, analyze the kneebend, and export the recommendation without operator action between token sizes, repetitions, refinement runs, or model suites.

Manual single-case execution must remain available for diagnostics, but it is not the normal benchmark workflow and must not be required to find the kneebend.

### 10.3 Suspicious-run confirmation

A suspicious result must be repeated once before it counts as a confirmed regression, unless continuing would violate the 22.5 GB ceiling or another hard safety rule.

The confirmation run must use the same model, prompt, input, seed, and generation parameters.

### 10.4 Boundary refinement

After the primary sweep stops:

1. Identify the last stable range below the stop point.
2. Retest that range using 250-token increments.
3. Repeat candidate boundary sizes sufficiently to demonstrate consistent behavior.
4. Identify the largest stable tested size.
5. Recommend a production input size below that boundary with an additional 1,000–2,000-token operating reserve, unless the measured data supports a different documented margin.

### 10.5 Automated model lifecycle and comparison sequence

The operator is responsible for approving and installing the exact model artifacts before the benchmark. The benchmark application must not automatically pull, update, or replace a model because doing so could change the weights or digest during a controlled comparison.

After all three exact model configurations pass preflight, the application must manage model switching automatically:

1. Verify the requested model tag and pinned digest.
2. Confirm no unrelated GPU-intensive job is active.
3. Unload the previously active benchmark model using the supported Ollama lifecycle action.
4. Wait for VRAM to return to the configured baseline range and record the result.
5. Load the next exact model and verify its tag, digest, quantization, processor placement, and readiness.
6. Run the configured cold characterization and warm benchmark sequence.
7. Preserve all lifecycle timings and errors.
8. Continue through the authorized model matrix without requiring the founder to reset Ollama or switch models manually.

If unload, VRAM release, digest verification, load, or readiness fails, the job must stop safely, preserve results, and provide an actionable error. It must not restart Windows, MemoryBox, or Ollama automatically unless separately authorized.

## 11. Measurements

Every execution must record, where available:

### 11.1 Identity and reproducibility

- Run ID and timestamp.
- Model name, tag, digest, architecture, and quantization.
- Prompt name, version, and hash.
- Input evidence source, range, and hash.
- Benchmark code commit SHA.
- Configuration-file hash.
- Cold or warm run designation.

### 11.2 Token measurements

- Requested evidence tokens.
- Actual evidence tokens.
- Prompt/instruction tokens.
- Ollama `prompt_eval_count`.
- Output tokens or `eval_count`.
- Total tokens.
- Reserved output tokens.
- Context utilization percentage.

### 11.3 Timing and throughput

- Wall-clock elapsed time.
- Ollama total duration.
- Load duration.
- Prompt-evaluation duration.
- Generation/evaluation duration.
- Prompt tokens per second.
- Output tokens per second.
- Time to first token when obtainable.

### 11.4 Resource measurements

- Starting, average, and peak VRAM.
- GPU utilization.
- GPU temperature.
- GPU power when obtainable.
- Starting and peak system RAM.
- CPU utilization when obtainable.
- GPU residency or CPU-offload/spill status.

### 11.5 Result measurements

- Completion status.
- Stop reason.
- Error category and error text.
- Output artifact path and hash.
- Output length.
- Truncation or malformed-output indicator.
- Citation/evidence-ID validation result.
- Repetition indicator when implemented.
- Founder quality scores and notes after review.

## 12. Performance-knee and stop rules

### 12.1 Hard ceiling

The sweep must not authorize another larger run after measured peak VRAM reaches **22.5 GB**. The 1.5 GB difference from the RTX 4090's nominal 24 GB is reserved for safe operation and variability.

The benchmark does not intentionally drive the model to failure.

### 12.2 Performance regressions

Raw elapsed time will naturally rise as the input grows. Therefore, elapsed time alone does not define regression.

A run may be classified as regressing when one or more of the following occurs relative to the preceding stable range:

- Prompt-processing throughput falls by more than 15% from the rolling stable median.
- Generation throughput falls by more than 15% from the rolling stable median.
- Elapsed time is more than 25% worse than the established input-size trend.
- The model begins material CPU offload or system-memory spill.
- Full GPU residency is lost.
- Output becomes truncated, incomplete, malformed, materially repetitive, or measurably less accurate.
- A configured timeout or processing error occurs.

The default automatic stop is **three confirmed consecutive regressing token sizes**. The regression percentage and count must remain configurable.

### 12.3 Immediate stops

Stop without proceeding to a larger size when:

- Peak VRAM reaches 22.5 GB.
- Continuing would exceed configured context after reserving output capacity.
- A GPU or Ollama condition threatens system stability.
- Required telemetry or artifact persistence fails.
- The operator requests cancellation.

### 12.4 Failure classification

Runs must be classified distinctly as:

- Successful/stable.
- Successful/regressing.
- Degraded due to CPU spill or partial GPU residency.
- Timed out.
- Context rejected.
- Out of memory.
- Infrastructure failure.
- Invalid or incomplete output.
- Operator cancelled.

A completed run with material CPU spill is not a successful GPU-resident result.

## 13. Narrative-quality comparison

### 13.1 Controlled comparison

After establishing safe ranges, compare the leading Qwen and Gemma configurations using:

- Identical gold-standard evidence.
- Identical narration instructions.
- Identical output-token allowance.
- Fixed, recorded sampling settings.
- Multiple representative evidence sizes, including a normal operating size and a near-boundary size.
- Blinded model identity during founder review.

The comparison has two required views:

1. **Equal-input comparison:** Every configuration receives the exact same Peggy chunk and prompt. This isolates narrative-model quality.
2. **Best-safe-setting comparison:** Each configuration receives the largest production-safe Peggy input supported by its measured operating envelope. This measures the practical tradeoff between model quality and usable evidence capacity.

Both views are required. The largest accepted input does not automatically win, and the most fluent same-input narrative does not automatically win if its usable evidence capacity is materially inadequate.

### 13.2 Two-stage selection

#### Stage 1 — Initial screen

Run Configurations A, B, and C through the same capacity and quality method. A configuration may be eliminated when founder review finds its narrative quality clearly inadequate, its evidence capacity impractical, or its operation unstable within the 22.5 GB ceiling.

#### Stage 2 — Finalist refinement

Advance no more than two configurations unless the founder explicitly authorizes otherwise. For those finalists:

- Repeat the equal-input and best-safe-setting comparisons.
- Refine the performance knee and production margin.
- Test one additional quantization only when Stage 1 data establishes a specific quality-versus-context question.
- Select the production configuration from the measured evidence and founder review.

### 13.3 Selection weighting

The default decision framework is:

- **Narrative and factual quality — 60%.**
- **Useful Peggy evidence capacity — 25%.**
- **Runtime and operational stability — 15%.**

The workbook must show the component scores, supporting measurements, weighted result, and founder override if the final selection differs from the calculated ranking. The weighting supports—not replaces—founder judgment.

### 13.4 Quality rubric

Founder review must score or classify:

- Factual accuracy.
- Chronological accuracy.
- Unsupported assertions or invented details.
- Material omissions.
- Correct handling of uncertainty.
- Correct attribution of speakers and quoted/forwarded content.
- Evidence citation/provenance quality.
- Narrative coherence and organization.
- Readability and concision.
- Natural storytelling quality.
- Emotional appropriateness without embellishment.
- Repetition.
- Overall usefulness as family history.

No automated prose score may substitute for founder review.

## 14. Artifacts and workbook

### 14.1 Immutable run artifacts

Each run must save:

- Exact configuration.
- Exact prompt.
- Exact evidence input.
- Raw Ollama response and metadata.
- Rendered narration.
- Telemetry samples.
- Error details, if any.
- Hashes connecting workbook rows to files.

Artifacts must use deterministic, collision-resistant names and must not overwrite earlier runs.

### 14.2 Excel workbook

The benchmark must create or append to an `.xlsx` workbook with at least these worksheets:

1. **Runs** — one normalized row per execution.
2. **Quality Review** — blinded narratives, rubric scores, decisions, and founder notes.
3. **Configuration** — hardware, software, prompts, thresholds, model digests, and run-set definitions.
4. **Summary** — stable range, performance knee, charts, comparison results, and recommended configuration.

The Summary worksheet must include both the equal-input and best-safe-setting comparisons, the 60/25/15 weighted decision table, Stage 1 eliminations, and any Stage 2 quantization refinement.

The workbook should contain the complete narration when it fits safely. Because spreadsheet cells have length limits, the authoritative complete narration remains the external artifact; the workbook must always include its path and hash.

Workbook writes must be incremental and durable so an interrupted sweep does not lose completed results.

### 14.3 Downloadable review bundle

At completion or safe stop, the application must create one portable results bundle that Tom can download and provide for independent review. It must contain:

- `benchmark_results.xlsx` as the primary human review surface.
- `benchmark_summary.md` with the automated kneebend finding and recommended production configuration.
- `runs.csv` and/or JSONL containing normalized machine-readable run measurements.
- Complete narration files for every comparable run.
- Raw Ollama responses and final usage metadata.
- Telemetry, console logs, validation reports, configuration, prompts, input manifests, and hashes.
- Relative links from the workbook that continue to work when the entire bundle is moved intact.

The spreadsheet is a review surface, not the only source of truth. JSON/JSONL and immutable per-run artifacts remain authoritative for later analysis.

## 15. Analysis and recommendation

The final analysis must identify:

- First observed performance regression.
- Confirmed performance-knee range.
- Largest stable tested input size.
- Peak stable VRAM.
- Stable prompt and generation throughput.
- Recommended production input chunk size.
- Recommended reserved output tokens.
- Recommended configured context window.
- Selected model, digest, and quantization.
- Quality comparison outcome.
- Equal-input comparison outcome.
- Best-safe-setting comparison outcome.
- Weighted 60/25/15 decision result and any founder override.
- Stage 1 elimination and Stage 2 finalist-refinement decisions.
- Reasons the selected configuration won.
- Known limitations and retest triggers.

The production recommendation must remain below 22.5 GB peak VRAM, remain completely GPU-resident, preserve output capacity, and include an operating margin below the measured knee.

## 16. Operational requirements

- The job must run the full authorized model-and-token matrix unattended after one explicit operator launch.
- No operator action may be required between token sizes, confirmation repetitions, refinement runs, or the Qwen/Gemma suites.
- The application must automatically unload/load and verify the preinstalled pinned models between suites.
- The application must not automatically download, update, or substitute model artifacts.
- Progress must be visible in console logs and saved artifacts.
- The current token target, repetition, elapsed time, VRAM, and last decision must be clear.
- Cancellation must be graceful and preserve completed results.
- A restart must resume without duplicating completed runs unless explicitly requested.
- The job must not restart MemoryBox, Windows, or Ollama automatically unless separately authorized.
- The job must fail closed if the configured model, prompt, input, telemetry, or workbook target is unavailable.
- Secrets and private evidence must not be written to console output unnecessarily.

## 17. Acceptance criteria

P2-I11A.0 is accepted only when:

1. Existing I11A code has been inventoried and appropriate code has been reused or refactored.
2. The parameter-driven single-run narration benchmark works on FlightSim.
3. The repeatable sweep controller works with configurable token increments and stop rules.
4. One command executes the authorized primary sweep, suspicious-run confirmations, refinement pass, model switching, analysis, and results export without per-run operator launches.
5. Evidence sizing is token-based and recorded against Ollama's actual prompt count.
6. Every run preserves reproducible inputs, outputs, configuration, telemetry, and hashes.
7. The Excel workbook is produced with Runs, Quality Review, Configuration, and Summary worksheets.
8. A portable bundle includes the workbook, summary Markdown, machine-readable runs, complete narrations, raw responses, telemetry, configuration, and hashes.
9. The 22.5 GB ceiling is enforced without deliberately driving the system to failure.
10. Two or three degrading runs can be confirmed and interpreted without mistaking normal linear elapsed-time growth for regression.
11. The 250-token boundary-refinement pass works automatically after the primary sweep.
12. Qwen3-30B-A3B-Instruct-2507 Q4_K_M, Qwen3 14B Q8_0, and Gemma 4 26B are screened through the same method with exact runtime digests recorded.
13. The application switches the preinstalled models and verifies VRAM release/readiness without a manual Ollama reset.
14. Prior reviewed Peggy evidence/chunks are used for founder quality comparison, and progressive capacity chunks remain traceable to the same canonical Peggy generation.
15. Founder review completes blinded equal-input and best-safe-setting comparisons.
16. The workbook applies the 60/25/15 weighting and records all Stage 1 eliminations, finalists, optional finalist-only quantization refinement, and any founder override.
17. No unapproved model family, base size, or open-ended configuration sweep is introduced.
18. A model, quantization, context window, output reserve, and production chunk size are explicitly approved.
19. The recommended setting is fully GPU-resident and includes documented operating margin.
20. No Peggy-wide, hierarchical, or Words of a Life run has occurred under this increment.

## 18. Founder review gates

### Gate 1 — Implementation plan

Review the I11A code inventory, reuse plan, benchmark configuration, candidate model identifiers, and proposed gold-standard evidence before production-scale execution.

### Gate 2 — Short smoke test

Review one small successful run, its narration, telemetry, artifacts, and workbook row before authorizing the automated sweep.

### Gate 3 — Capacity results

Review the primary sweep, stop decision, refinement results, and proposed safe operating ranges for each model.

### Gate 4 — Blinded narrative comparison

Review and score the three controlled configuration outputs without model identities displayed. Review both equal-input and best-safe-setting results, apply the 60/25/15 decision framework, eliminate noncompetitive configurations, and authorize no more than two finalists for any required refinement.

### Gate 5 — Configuration selection and closeout

Approve the selected model, quantization, chunk size, context window, output reserve, prompt version, and documented limitations. Only this gate authorizes P2-I11A to resume.

## 19. Retest triggers

The benchmark should be rerun when any material factor changes, including:

- GPU or available VRAM.
- Ollama version or inference backend.
- NVIDIA driver.
- Model weights, tag, digest, or quantization.
- Prompt structure or thinking mode.
- Context-cache implementation.
- Evidence serialization format.
- Output-token requirement.
- A materially different target workload.

## 20. Deferred decisions

The following remain for implementation planning or founder gates:

- Exact preserved Gemma baseline tag and quantization.
- Whether Stage 1 evidence justifies one alternate quantization for either finalist; no alternate is presumed.
- Final output-token reserve within the proposed 2,000–3,000 range.
- Exact temperature, seed, and thinking-mode settings for fair comparison.
- Final performance-regression thresholds after the smoke test validates telemetry behavior.
- Number and composition of gold-standard quality chunks.
- Maximum acceptable wall-clock time and minimum acceptable generation speed.
- Whether later production narration uses one universal chunk size or model/workload-specific profiles.

## 21. Closeout deliverables

- Benchmark source code and tests.
- Parameterized configuration examples.
- Single-command unattended benchmark launcher.
- Operator runbook.
- Excel results workbook.
- Portable results bundle with Markdown, CSV/JSONL, complete narrations, raw responses, telemetry, and hashes.
- Complete per-run artifact directory.
- Performance-knee analysis.
- Blinded narrative-quality review packet.
- Founder-approved production configuration.
- Roadmap and P2-I11A handoff update.

## 22. Locked founder decisions

As of 2026-09-26:

- P2-I11A.0 occurs immediately after accepted P2-I14; P2-I15 is postponed until after I11A Redux unless the founder changes the sequence.
- Model and chunk-size benchmarking precede the Peggy narrative proof.
- The initial screen contains exactly three configurations: Qwen3-30B-A3B-Instruct-2507 Q4_K_M, Qwen3 14B Q8_0, and Gemma 4 26B using its preserved installed baseline quantization; exact installed digests are recorded.
- Selection requires both equal-input and best-safe-setting Peggy comparisons.
- The default selection weighting is 60% narrative/factual quality, 25% useful Peggy evidence capacity, and 15% runtime/operational stability, with any founder override documented.
- No more than two finalists proceed to refinement by default; alternate quantization testing is permitted only for a finalist and only to answer a documented tradeoff.
- I11A.0 is not an open-ended model tournament; additional model families or non-finalist configurations require founder approval.
- The founder installs or approves the pinned model artifacts once; the application automatically unloads, loads, resets, and verifies models between suites without updating them.
- The prior reviewed Peggy evidence/chunks are the quality baseline; capacity chunks are progressively repacked from the same canonical Peggy evidence generation.
- One authorized launch executes the full ladder, confirmation runs, refinement, model comparison, kneebend analysis, and downloadable results export.
- The primary sweep increases evidence input by 1,000 tokens, not bytes.
- Boundary refinement uses 250-token steps.
- The production VRAM ceiling is 22.5 GB.
- Testing does not intentionally drive the model to failure.
- CPU spill and partial GPU residency are degraded outcomes, not successful capacity results.
- Testing stops at the VRAM ceiling or after three confirmed consecutive performance regressions by default.
- The production sweet spot remains below the measured performance knee and preserves narration-output capacity.
- Broader Peggy narration, hierarchical synthesis, and Words of a Life remain outside this increment.
