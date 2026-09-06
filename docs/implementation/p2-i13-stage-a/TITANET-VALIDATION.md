# TitaNet-Large development validation

Tom approved TitaNet-Large as the pilot encoder. This replaces the provisional TorchScript ECAPA adapter; it does not authorize private-media processing or a production installation. No ECAPA comparison is being run.

## Artifact

- Official public endpoint: https://api.ngc.nvidia.com/v2/models/nvidia/nemo/titanet_large/versions/v1/files/titanet-l.nemo
- Publisher/model: NVIDIA TitaNet-Large, NGC version v1.
- Downloaded size: 101621760 bytes.
- SHA256: `e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3`.
- Read-only checkpoint configuration inspection confirmed 16000 Hz preprocessing and 192-dimensional speaker embeddings.
- Model card and license: https://huggingface.co/nvidia/speakerverification_en_titanet_large (CC-BY-4.0). Preserve NVIDIA attribution in deployment materials.
- Adapter API reference: https://github.com/NVIDIA/NeMo/blob/v2.7.0/nemo/collections/asr/models/label_models.py

## Code contract

Admission and local restoration require the pinned public artifact hash. The encoder restores a local `.nemo` file on CPU through `EncDecSpeakerLabelModel.restore_from`, calls `eval`, and performs inference on exact mono PCM16/16000Hz excerpts. Forward receives sample counts, not the old relative-length argument. No `from_pretrained`, runtime download, training or legacy Learn call is used. The subprocess retains offline network guards, one model load and timeout handling.

The explicit `titanet_smoke` command generates its own tone waveform, runs it twice through one model process and reports finite dimensions and repeatability without printing embeddings. It does not access private media or the database. Passing this smoke test establishes execution only, not speech-recognition accuracy.

The old 0.55/0.40 ECAPA defaults are removed from CLI preparation. Both TitaNet thresholds must now be explicit and become part of the reviewed plan hash. Determine thresholds on separate public/development evidence before the three private probes; never tune on those probes while calling them acceptance evidence. The existing four-span plan must be regenerated for the model format/hash and reviewed thresholds. Do not edit a registered plan.

Migration 032 is unchanged by model selection. No additional runtime schema migration is introduced. Existing source/annotation pinning, one-attempt limits, retirement and separate result storage remain in place. Full I13 acceptance still requires broader speaker and uncertain/overlapping-speech evidence.

## Environment

Development uses an isolated Python 3.13 virtual environment under the desktop temporary directory, leaving system Python and FlightSim untouched. `titanet-requirements.in` records candidate direct pins, not a deployment-tested lock. FlightSim's Python 3.12 environment has not been validated for this stack. Do not execute installation or processing on FlightSim until the consolidated readiness report is complete and approved.


## Completed validation

The isolated NeMo 2.7.0 / Torch 2.8.0 / Torchaudio 2.8.0 install completed successfully. `pip check` reported no broken requirements. The actual pinned NVIDIA checkpoint loaded on Windows CPU through the offline child process. Generated audio produced 192 finite dimensions; two passes through one loaded model had maximum absolute difference 0.0. See `titanet-smoke-proof.json`; `titanet-dev-resolved.txt` records the complete development resolution, not a verified Python 3.12 production lock.

53 targeted tests passed: five TitaNet contract tests, 15 pilot tests (including five synthetic PostgreSQL tests), and 33 Stage A admission regressions. No private audio, database, or runtime model cache was used by the model smoke test. Public model weights and the temporary environment are outside Git. PostgreSQL 16 clone rehearsal, FlightSim environment smoke, threshold selection/calibration and private recognition remain outstanding.

The model installation initially encountered Hugging Face connection resets. NVIDIA's official versioned endpoint succeeded without disabling TLS verification. This does not require any FlightSim network/security change.
