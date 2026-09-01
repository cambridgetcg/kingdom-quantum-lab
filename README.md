# KINGDOM Quantum Lab

A local-first scaffold for building quantum capability without surrendering
the problem definition, evidence standard, budget, data boundary, or roadmap
to a single vendor.

## What exists now

- A canonical experiment manifest with a required classical baseline, rights
  boundary, cost ceiling, and stop conditions.
- A capability and ecosystem registry that separates adoption, contribution,
  experimentation, and watch-only postures.
- A schema-backed portfolio of twelve constitutional and quantum product
  candidates, with explicit pressure boundaries, conversion firewalls,
  structured non-conversion business models, digest-pinned but unwired
  counterweights, SHA-bound firewall semantics, content-verified implementation
  evidence, dependencies, MVP limits, and release gates.
- An offline OpenQASM 3 **subset** simulator supporting `h`, `x`, `cx`, and
  final whole-register measurement.
- A receipt generator that records source hashes, shots, seed, result counts,
  baseline distance, local execution, zero network calls, zero QPU time, zero
  cost, limitations, governing schema hashes, validator version, and evidence
  grade `E0`.
- Schema-backed runtime validation, content-bound receipt verification, and
  tests for fail-closed policy boundaries.

It does **not** connect to a cloud, use credentials, execute on quantum
hardware, validate arbitrary OpenQASM, establish quantum advantage, migrate
cryptography, write to Zerone, or authorize publication or spending.
The product portfolio does not deploy persuasion, consent, moderation,
governance, payments, reputation, resource allocation, or public-ledger effects.

## Why this shape

The durable KINGDOM asset is the constitutional layer around experiments:

```text
domain problem + rights + baseline + budget
                    |
          canonical experiment bundle
                    |
       capability gate + adapter contract
          /          |          \
     simulator   cloud broker   native QPU
          \          |          /
       comparable, evidence-graded receipts
```

SDKs, brokers, and QPUs can then be replaceable adapters. The question and its
evidence remain portable and contestable.

## Run the bounded reference experiment

Python 3.11 or newer is required. The sole direct runtime dependency is the
pinned JSON Schema validator; `uv sync` installs the locked environment.

```bash
uv sync

uv run --offline kingdom-quantum validate \
  experiments/bell-conformance/experiment.json

uv run --offline kingdom-quantum run \
  experiments/bell-conformance/experiment.json \
  --out /tmp/kingdom-quantum-bell-receipt.json

uv run --offline kingdom-quantum verify-receipt \
  /tmp/kingdom-quantum-bell-receipt.json \
  experiments/bell-conformance/experiment.json

uv run --offline kingdom-quantum ecosystems
uv run --offline kingdom-quantum products
uv run --offline kingdom-quantum products --json
uv run --offline python -m unittest discover -s tests -v
```

The Bell-state example is a contract and conformance demonstration. Its result
must remain labelled `E0: local simulator only`. Receipt output is atomic and
no-clobber: choose a new path for each run. Verification detects content or
source drift and deterministically reproduces the sample, but it is not a
signature and does not prove authorship or authority.

## Evidence grades

| Grade | Meaning |
|---|---|
| `E0` | Theory, resource estimate, or simulator only |
| `E1` | Reproducible hardware execution |
| `E2` | Hardware result compared with a naive classical method |
| `E3` | Fair comparison with strong classical baselines |
| `E4` | Statistically robust operational benefit on representative data |
| `E5` | Independently replicated production benefit |

Only `E4` or `E5` may support “practical advantage.” “Quantum advantage” also
requires an explicit accounting boundary for all classical and quantum work.

## Next build gates

1. Add schema-backed chemistry/materials and optimization problem bundles.
2. Add independent local adapters for Qiskit, Cirq/OpenFermion, PennyLane, and
   the Microsoft resource estimator, each optional and version-pinned.
3. Run the same fixtures through at least two simulator families.
4. Add a no-key-material post-quantum cryptographic inventory as a separate
   defensive module.
5. Only then consider one brokered hardware adapter behind explicit data,
   region, credential, cancellation, and cost gates.

See [the quantum strategy](docs/KINGDOM-QUANTUM-COMMONS.md),
[the persuasion and product architecture](docs/PERSUASION-CONSENT-AND-KINGDOM-PRODUCTS.md),
[the ecosystem registry](registry/ecosystems.json), and the
[machine-readable product portfolio](registry/products.json). The default JSON
view retains its boundary, principles, invariants, and firewalls; use the
explicit `--products-only` flag only when that loss of context is intended.
