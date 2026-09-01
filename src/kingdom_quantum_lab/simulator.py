from __future__ import annotations

import json
import math
import platform
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as distribution_version
from pathlib import Path
from typing import Any

from .contracts import (
    LOCAL_REFERENCE_ADAPTER,
    ContractError,
    canonical_json_bytes,
    packaged_schema_bytes,
    sha256_bytes,
    sha256_file,
    validate_experiment,
    validate_receipt,
)


_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
E0_CLAIM_BOUNDARY = (
    "Local reference simulation only; this is not quantum hardware "
    "execution or evidence of practical or quantum advantage."
)
REFERENCE_LIMITATIONS = (
    "Supports only h, x, cx, and final whole-register measurement.",
    "Noise, calibration, compilation, routing, and hardware effects are absent.",
    "Local elapsed time is diagnostic and not a performance benchmark.",
)


def _schema_validator_version() -> str:
    try:
        return distribution_version("jsonschema")
    except PackageNotFoundError as exc:  # Declared runtime dependency.
        raise ContractError("jsonschema distribution metadata is unavailable") from exc


@dataclass(frozen=True)
class Operation:
    name: str
    qubits: tuple[int, ...]


@dataclass(frozen=True)
class Program:
    qubit_count: int
    bit_count: int
    operations: tuple[Operation, ...]


def parse_openqasm_subset(text: str) -> Program:
    without_comments = re.sub(r"//[^\n]*", "", text)
    statements = [statement.strip() for statement in without_comments.split(";")]
    statements = [statement for statement in statements if statement]
    if not statements or not re.fullmatch(r"OPENQASM\s+3(?:\.0)?", statements[0]):
        raise ContractError("program must begin with OPENQASM 3")

    qubit_name: str | None = None
    bit_name: str | None = None
    qubit_count: int | None = None
    bit_count: int | None = None
    operations: list[Operation] = []
    measured = False
    standard_gates_loaded = False

    for statement in statements[1:]:
        if statement == 'include "stdgates.inc"':
            standard_gates_loaded = True
            continue

        qubit_match = re.fullmatch(rf"qubit\[(\d+)\]\s+({_IDENTIFIER})", statement)
        if qubit_match:
            if qubit_name is not None:
                raise ContractError("the reference subset accepts one qubit register")
            qubit_count = int(qubit_match.group(1))
            qubit_name = qubit_match.group(2)
            if not 1 <= qubit_count <= 10:
                raise ContractError("reference simulation supports 1 to 10 qubits")
            continue

        bit_match = re.fullmatch(rf"bit\[(\d+)\]\s+({_IDENTIFIER})", statement)
        if bit_match:
            if bit_name is not None:
                raise ContractError("the reference subset accepts one bit register")
            bit_count = int(bit_match.group(1))
            bit_name = bit_match.group(2)
            continue

        if qubit_name is None or qubit_count is None:
            raise ContractError("declare a qubit register before operations")
        if measured:
            raise ContractError("measurement must be the final instruction")

        one_qubit = re.fullmatch(
            rf"(h|x)\s+{re.escape(qubit_name)}\[(\d+)\]", statement
        )
        if one_qubit:
            if not standard_gates_loaded:
                raise ContractError("h and x require the OpenQASM standard-gate include")
            index = int(one_qubit.group(2))
            _check_qubit_index(index, qubit_count)
            operations.append(Operation(one_qubit.group(1), (index,)))
            continue

        controlled = re.fullmatch(
            rf"cx\s+{re.escape(qubit_name)}\[(\d+)\]\s*,\s*"
            rf"{re.escape(qubit_name)}\[(\d+)\]",
            statement,
        )
        if controlled:
            if not standard_gates_loaded:
                raise ContractError("cx requires the OpenQASM standard-gate include")
            control, target = int(controlled.group(1)), int(controlled.group(2))
            _check_qubit_index(control, qubit_count)
            _check_qubit_index(target, qubit_count)
            if control == target:
                raise ContractError("cx control and target must differ")
            operations.append(Operation("cx", (control, target)))
            continue

        measurement = re.fullmatch(
            rf"({_IDENTIFIER})\s*=\s*measure\s+{re.escape(qubit_name)}", statement
        )
        if measurement:
            if bit_name is None or measurement.group(1) != bit_name:
                raise ContractError("measurement target must be the declared bit register")
            if bit_count != qubit_count:
                raise ContractError("qubit and bit registers must have equal size")
            measured = True
            continue

        raise ContractError(f"unsupported OpenQASM subset statement: {statement}")

    if qubit_count is None or bit_count is None:
        raise ContractError("program must declare qubit and bit registers")
    if not measured:
        raise ContractError("program must end with whole-register measurement")
    return Program(qubit_count, bit_count, tuple(operations))


def _check_qubit_index(index: int, qubit_count: int) -> None:
    if not 0 <= index < qubit_count:
        raise ContractError(f"qubit index out of range: {index}")


def simulate_probabilities(program: Program) -> dict[str, float]:
    state = [0j] * (1 << program.qubit_count)
    state[0] = 1 + 0j
    for operation in program.operations:
        if operation.name == "h":
            _apply_h(state, operation.qubits[0])
        elif operation.name == "x":
            _apply_x(state, operation.qubits[0])
        elif operation.name == "cx":
            _apply_cx(state, operation.qubits[0], operation.qubits[1])
        else:  # Defensive: parser owns the allowed operation set.
            raise ContractError(f"unsupported operation: {operation.name}")

    probabilities: dict[str, float] = {}
    for index, amplitude in enumerate(state):
        probability = float(abs(amplitude) ** 2)
        if probability > 1e-15:
            bitstring = format(index, f"0{program.bit_count}b")
            probabilities[bitstring] = probability
    total = math.fsum(probabilities.values())
    if not math.isclose(total, 1.0, rel_tol=0, abs_tol=1e-10):
        raise ContractError(f"simulator probability mass is {total}, expected 1")
    return probabilities


def _apply_h(state: list[complex], qubit: int) -> None:
    mask = 1 << qubit
    scale = 1 / math.sqrt(2)
    for index in range(len(state)):
        if index & mask:
            continue
        paired = index | mask
        low, high = state[index], state[paired]
        state[index] = (low + high) * scale
        state[paired] = (low - high) * scale


def _apply_x(state: list[complex], qubit: int) -> None:
    mask = 1 << qubit
    for index in range(len(state)):
        if index & mask:
            continue
        paired = index | mask
        state[index], state[paired] = state[paired], state[index]


def _apply_cx(state: list[complex], control: int, target: int) -> None:
    control_mask, target_mask = 1 << control, 1 << target
    for index in range(len(state)):
        if not index & control_mask or index & target_mask:
            continue
        paired = index | target_mask
        state[index], state[paired] = state[paired], state[index]


def sample_counts(
    probabilities: dict[str, float], shots: int, seed: int
) -> dict[str, int]:
    outcomes = sorted(probabilities)
    weights = [probabilities[outcome] for outcome in outcomes]
    counts = {outcome: 0 for outcome in outcomes}
    for outcome in random.Random(seed).choices(outcomes, weights=weights, k=shots):
        counts[outcome] += 1
    return {outcome: count for outcome, count in counts.items() if count}


def total_variation_distance(
    observed: dict[str, float], expected: dict[str, float]
) -> float:
    outcomes = set(observed) | set(expected)
    return 0.5 * math.fsum(
        abs(float(observed.get(outcome, 0)) - float(expected.get(outcome, 0)))
        for outcome in outcomes
    )


def validate_reference_bundle(
    manifest: dict[str, Any],
    manifest_path: Path,
    *,
    require_approved: bool = False,
) -> dict[str, Any]:
    validated = validate_experiment(manifest, manifest_path)
    if require_approved and manifest["status"] != "approved-for-local-simulation":
        raise ContractError(
            "execution requires status approved-for-local-simulation"
        )

    program_path: Path = validated["program_path"]
    try:
        program_bytes = program_path.read_bytes()
        program_text = program_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError(f"cannot bind source program: {exc}") from exc
    program = parse_openqasm_subset(program_text)

    expected = manifest["classical_baseline"]["expected_distribution"]
    if any(len(outcome) != program.bit_count for outcome in expected):
        raise ContractError(
            "baseline bitstrings must match the measured register width"
        )
    return {
        **validated,
        "program": program,
        "program_bytes": program_bytes,
    }


def _receipt_sources(
    manifest_path: Path,
    manifest_bytes: bytes,
    program_path: Path,
    program_bytes: bytes,
) -> dict[str, Any]:
    return {
        "manifest": {
            "path": manifest_path.name,
            "sha256": sha256_bytes(manifest_bytes),
        },
        "program": {
            "path": str(program_path.relative_to(manifest_path.parent.resolve())),
            "sha256": sha256_bytes(program_bytes),
            "representation": "OpenQASM 3 subset",
        },
        "runner": {
            "path": "python:kingdom_quantum_lab/simulator.py",
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "validator": {
            "path": "python:kingdom_quantum_lab/contracts.py",
            "sha256": sha256_file(Path(__file__).with_name("contracts.py").resolve()),
        },
        "experiment_schema": {
            "path": (
                "package:kingdom_quantum_lab/data/schemas/"
                "experiment-plan.v1.schema.json"
            ),
            "sha256": sha256_bytes(
                packaged_schema_bytes("experiment-plan.v1.schema.json")
            ),
        },
        "receipt_schema": {
            "path": (
                "package:kingdom_quantum_lab/data/schemas/"
                "quantum-run-receipt.v1.schema.json"
            ),
            "sha256": sha256_bytes(
                packaged_schema_bytes("quantum-run-receipt.v1.schema.json")
            ),
        },
        "schema_validator": {
            "distribution": "jsonschema",
            "version": _schema_validator_version(),
        },
    }


def run_reference_experiment(
    manifest: dict[str, Any],
    manifest_path: Path,
    *,
    shots: int | None = None,
    seed: int = 1701,
    now: datetime | None = None,
) -> dict[str, Any]:
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest_on_disk = json.loads(manifest_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot bind source manifest: {exc}") from exc
    if manifest != manifest_on_disk:
        raise ContractError("in-memory manifest differs from the source file")
    validated = validate_reference_bundle(
        manifest,
        manifest_path,
        require_approved=True,
    )
    policy = manifest["execution_policy"]
    effective_shots = shots if shots is not None else int(policy["default_shots"])
    if (
        not isinstance(effective_shots, int)
        or isinstance(effective_shots, bool)
        or not 1 <= effective_shots <= int(policy["max_shots"])
    ):
        raise ContractError("shots exceed the bounded execution policy")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ContractError("seed must be a non-negative integer")

    program_path: Path = validated["program_path"]
    program_bytes: bytes = validated["program_bytes"]
    program: Program = validated["program"]
    start = time.perf_counter()
    exact_probabilities = simulate_probabilities(program)
    counts = sample_counts(exact_probabilities, effective_shots, seed)
    elapsed_ms = (time.perf_counter() - start) * 1000
    observed = {
        outcome: count / effective_shots for outcome, count in sorted(counts.items())
    }
    expected = {
        outcome: float(probability)
        for outcome, probability in manifest["classical_baseline"][
            "expected_distribution"
        ].items()
    }
    tvd = total_variation_distance(observed, expected)

    run_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run_at_text = run_at.isoformat().replace("+00:00", "Z")
    receipt_body = {
        "schema": "kingdom.quantum-receipt/v1",
        "experiment_id": manifest["experiment_id"],
        "run_at": run_at_text,
        "evidence_grade": "E0",
        "claim_boundary": E0_CLAIM_BOUNDARY,
        "adapter": {
            "id": LOCAL_REFERENCE_ADAPTER,
            "execution_kind": "local-statevector-subset-simulator",
            "network_calls": 0,
        },
        "sources": _receipt_sources(
            manifest_path,
            manifest_bytes,
            program_path,
            program_bytes,
        ),
        "execution": {
            "qubits": program.qubit_count,
            "operations": len(program.operations),
            "shots": effective_shots,
            "seed": seed,
            "counts": counts,
            "observed_distribution": observed,
            "exact_simulator_distribution": exact_probabilities,
            "local_elapsed_ms": round(elapsed_ms, 6),
            "runtime": {
                "implementation": platform.python_implementation(),
                "python_version": sys.version.split()[0],
            },
        },
        "baseline": {
            "method": manifest["classical_baseline"]["method"],
            "expected_distribution": expected,
            "total_variation_distance": tvd,
        },
        "accounting": {
            "queue_time_seconds": 0,
            "qpu_time_seconds": 0,
            "cost_gbp": 0,
            "energy_estimate": "not-measured",
        },
        "rights": manifest["rights"],
        "limitations": [*REFERENCE_LIMITATIONS, *manifest["limitations"]],
    }
    receipt_id = f"qr-{sha256_bytes(canonical_json_bytes(receipt_body))[:24]}"
    receipt = {
        "schema": receipt_body["schema"],
        "receipt_id": receipt_id,
        **{key: value for key, value in receipt_body.items() if key != "schema"},
    }
    validate_receipt(receipt)
    return receipt


def verify_reference_receipt(
    receipt: dict[str, Any], manifest_path: Path
) -> dict[str, Any]:
    """Verify integrity and deterministic E0 reproduction, not authorship."""

    validate_receipt(receipt)
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot bind source manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ContractError("source manifest root must be an object")
    bundle = validate_reference_bundle(
        manifest,
        manifest_path,
        require_approved=True,
    )
    program_path: Path = bundle["program_path"]
    program: Program = bundle["program"]
    program_bytes: bytes = bundle["program_bytes"]

    if receipt["experiment_id"] != manifest["experiment_id"]:
        raise ContractError("receipt experiment_id does not match the manifest")
    if receipt["claim_boundary"] != E0_CLAIM_BOUNDARY:
        raise ContractError("receipt claim boundary is not the fixed E0 boundary")
    expected_limitations = [*REFERENCE_LIMITATIONS, *manifest["limitations"]]
    if receipt["limitations"] != expected_limitations:
        raise ContractError("receipt limitations do not match runner and manifest limits")
    if receipt["rights"] != manifest["rights"]:
        raise ContractError("receipt rights do not match the manifest")
    if receipt["baseline"]["method"] != manifest["classical_baseline"]["method"]:
        raise ContractError("receipt baseline method does not match the manifest")
    expected_baseline = {
        outcome: float(probability)
        for outcome, probability in manifest["classical_baseline"][
            "expected_distribution"
        ].items()
    }
    if receipt["baseline"]["expected_distribution"] != expected_baseline:
        raise ContractError("receipt baseline distribution does not match the manifest")

    expected_sources = _receipt_sources(
        manifest_path,
        manifest_bytes,
        program_path,
        program_bytes,
    )
    if receipt["sources"] != expected_sources:
        raise ContractError("receipt source paths or hashes do not match local sources")

    execution = receipt["execution"]
    expected_runtime = {
        "implementation": platform.python_implementation(),
        "python_version": sys.version.split()[0],
    }
    if execution["runtime"] != expected_runtime:
        raise ContractError("receipt runtime does not match the verifier runtime")
    if execution["qubits"] != program.qubit_count:
        raise ContractError("receipt qubit count does not match the program")
    if execution["operations"] != len(program.operations):
        raise ContractError("receipt operation count does not match the program")
    exact = simulate_probabilities(program)
    if execution["exact_simulator_distribution"] != exact:
        raise ContractError("receipt exact distribution does not reproduce")
    reproduced_counts = sample_counts(exact, execution["shots"], execution["seed"])
    if execution["counts"] != reproduced_counts:
        raise ContractError("receipt counts do not reproduce from its seed and shots")
    return receipt
