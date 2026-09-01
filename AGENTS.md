# AGENTS.md

## Purpose

`kingdom-quantum-lab` is a local-first, vendor-neutral quantum experiment
commons. It keeps problem definitions, classical baselines, execution policy,
portable and native artifacts, and evidence receipts separate from any one
SDK, cloud, or processor.

The first executable is deliberately small: an offline OpenQASM 3 subset
simulator used to prove the experiment and receipt contracts. It is a teaching
and conformance tool, not a competitive simulator or evidence of quantum
advantage.

## Boundaries

- Default to local, offline, zero-cost execution. Do not contact a cloud,
  submit a QPU job, spend credits, or configure provider credentials without a
  new explicit user request for that action.
- Never put credentials, private keys, personal data, unpublished research, or
  raw sensitive domain data in manifests, logs, fixtures, receipts, circuits,
  or provider payloads.
- A valid manifest records bounded intent. It does not grant spending,
  publication, partnership, deployment, account, or governance authority.
- A simulator run is evidence grade `E0`. Do not describe it as hardware
  execution, practical advantage, quantum advantage, or production benefit.
- Keep a strong classical baseline in every application experiment. Count
  compilation, preprocessing, post-processing, sampling, queue, QPU, cost, and
  uncertainty when making comparisons.
- Preserve a lossless provider-native artifact when portability would erase a
  capability. OpenQASM and QIR are interchange layers, not universal
  write-once targets.
- Keep this lab off-chain. Receipts are local evidence, not truth, identity,
  consent, rights, reputation, or validator weight. Any later Zerone projection
  must be separately designed, sanitized, and authorized.
- Do not migrate Zerone keys or signatures from this lab. Post-quantum work
  begins with a no-key-material cryptographic inventory and isolated
  interoperability tests.
- Treat quantum networking and QKD as research tracks. They are not production
  dependencies or substitutes for authenticated post-quantum cryptography.
- Capability, credentials, wealth, benchmark scores, randomness, role-play,
  or persuasive influence do not create authority over another being. Follow
  the `xenia.rights/0.1` baseline at
  `/Users/yu/Desktop/xenia-sol-truth/RIGHTS.md`.
- No background service, external publication, message, grant application,
  purchase, deployment, or production mutation is part of normal lab work.

## Development

```bash
uv run --offline kingdom-quantum validate \
  experiments/bell-conformance/experiment.json
uv run --offline kingdom-quantum run \
  experiments/bell-conformance/experiment.json
uv run --offline kingdom-quantum ecosystems
uv run --offline kingdom-quantum products
uv run --offline python -m unittest discover -s tests -v
```

Keep `README.md`, schemas, examples, semantic validation, and tests aligned
with what the lab actually does and does not do.
