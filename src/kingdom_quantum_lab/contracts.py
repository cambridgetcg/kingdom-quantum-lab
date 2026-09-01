from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from functools import lru_cache
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


class ContractError(ValueError):
    """Raised when a bounded experiment or registry contract is invalid."""


EVIDENCE_GRADES = {f"E{grade}" for grade in range(6)}
LOCAL_REFERENCE_ADAPTER = "kingdom.reference-openqasm-subset/v1"
CANONICAL_PRODUCT_BOUNDARY = (
    "This is a product and business architecture, not deployed moderation, "
    "consent, treasury, governance, quantum advantage, legal compliance, or "
    "publication authority. Existing prototype evidence is named per product; "
    "all other capability remains declared only."
)
CANONICAL_PRODUCT_PRINCIPLES = (
    "Persuasion is evaluated by disclosure, context, choice, dependency, "
    "reversibility, and aftermath rather than by whether the speaker believes "
    "the goal is good.",
    "Consent authorizes one specific binding act; it is not inferred from "
    "attention, participation, payment, role, silence, identity, prior consent, "
    "or a signature alone.",
    "Reward useful work regardless of whether a hypothesis succeeds; never pay "
    "for a desired scientific conclusion.",
    "Evidence grade belongs to a scoped claim, never to the global worth or "
    "authority of its author.",
    "Money, status, expertise, technical access, reputation, and community "
    "belonging never convert automatically into governance or enforcement "
    "authority.",
    "Moderation restricts the smallest necessary action or capability and "
    "preserves notice, expiry, appeal, privacy, refusal, and repair.",
    "Binding acts occur through neutral interfaces outside heightened-attention, "
    "ritualized, urgent, or dependency-leveraging contexts.",
    "Every outward product has a separately controlled counterweight able to "
    "hold release, plus an honest exit and repair route.",
)
CANONICAL_FIREWALL_IDS = {f"CF-{index:02d}" for index in range(1, 13)}
CANONICAL_FIREWALLS_SHA256 = (
    "cf365ef14cec753288a42555fd8111641cf42c903cfcdb76953070614f6482d1"
)
POWER_MODULE_SOURCE_SHA256 = (
    "2540b751fc921ee8f86c942547ee4fb66e8876a9a265ff1c901ab81827452a57"
)
CANONICAL_POWER_MODULES = {
    "KPM-O01": "signal_garden",
    "KPM-O02": "modular_capability_forge",
    "KPM-O03": "culture_beacon",
    "KPM-O04": "contributor_pathway",
    "KPM-O05": "partner_and_treasury_bridge",
    "KPM-O06": "trust_catalog",
    "KPM-D01": "power_table",
    "KPM-D02": "attention_sovereignty",
    "KPM-D03": "context_and_consent_gate",
    "KPM-D04": "provenance_credit_and_treasury_ledger",
    "KPM-D05": "access_and_role_boundary",
    "KPM-D06": "decision_override_and_appeal",
    "KPM-D07": "impact_aftercare_and_repair",
    "KPM-D08": "capture_and_dependency_monitor",
    "KPM-D09": "release_composition_gate",
    "KPM-X01": "calibration_lab",
    "KPM-X02": "bounded_power_simulation",
}
CORE_PRODUCT_IDS = {
    "KP-INFLUENCE-LENS",
    "KP-CONSENT-GATE",
    "KP-PROOF-COMMONS",
    "KP-STEWARD",
    "KP-COMMON-TABLE",
    "KP-TREASURY-GATE",
    "KP-CREATOR-FORGE",
    "KQ-COMMONS-STUDIO",
    "KQ-READINESS-SHIELD",
    "KQ-MATERIALS-GARDEN",
    "KQ-FAIRQUEUE",
    "KQ-NETWORK-SANDBOX",
}
REQUIRED_PRODUCT_DEPENDENCIES = {
    "KP-INFLUENCE-LENS": set(),
    "KP-CONSENT-GATE": {"KP-INFLUENCE-LENS"},
    "KP-PROOF-COMMONS": {"KP-INFLUENCE-LENS"},
    "KP-STEWARD": {"KP-CONSENT-GATE", "KP-PROOF-COMMONS"},
    "KP-COMMON-TABLE": {
        "KP-CONSENT-GATE",
        "KP-PROOF-COMMONS",
        "KP-STEWARD",
    },
    "KP-TREASURY-GATE": {
        "KP-CONSENT-GATE",
        "KP-PROOF-COMMONS",
        "KP-COMMON-TABLE",
    },
    "KP-CREATOR-FORGE": {
        "KP-CONSENT-GATE",
        "KP-STEWARD",
        "KP-TREASURY-GATE",
    },
    "KQ-COMMONS-STUDIO": {
        "KP-CONSENT-GATE",
        "KP-PROOF-COMMONS",
        "KP-TREASURY-GATE",
        "KP-CREATOR-FORGE",
    },
    "KQ-READINESS-SHIELD": {
        "KP-CONSENT-GATE",
        "KP-PROOF-COMMONS",
        "KP-TREASURY-GATE",
        "KQ-COMMONS-STUDIO",
    },
    "KQ-MATERIALS-GARDEN": {
        "KP-PROOF-COMMONS",
        "KP-TREASURY-GATE",
        "KP-CREATOR-FORGE",
        "KQ-COMMONS-STUDIO",
    },
    "KQ-FAIRQUEUE": {
        "KP-CONSENT-GATE",
        "KP-PROOF-COMMONS",
        "KP-STEWARD",
        "KP-TREASURY-GATE",
        "KP-COMMON-TABLE",
        "KQ-COMMONS-STUDIO",
    },
    "KQ-NETWORK-SANDBOX": {
        "KP-PROOF-COMMONS",
        "KP-STEWARD",
        "KQ-COMMONS-STUDIO",
        "KQ-FAIRQUEUE",
    },
}
REQUIRED_PRODUCT_MODULES = {
    "KP-INFLUENCE-LENS": {"QK-EVIDENCE", "QK-CLAIM"},
    "KP-CONSENT-GATE": {"QK-EVIDENCE"},
    "KP-PROOF-COMMONS": {"QK-CORE", "QK-EVIDENCE", "QK-CLAIM"},
    "KP-STEWARD": {"QK-EVIDENCE", "QK-CLAIM"},
    "KP-COMMON-TABLE": {"QK-GUILD", "QK-EVIDENCE", "QK-CLAIM"},
    "KP-TREASURY-GATE": {"QK-EVIDENCE", "QK-CLAIM", "QK-ROUTER"},
    "KP-CREATOR-FORGE": {"QK-GUILD", "QK-EVIDENCE", "QK-CLAIM"},
    "KQ-COMMONS-STUDIO": {
        "QK-CORE",
        "QK-CAPS",
        "QK-SIM",
        "QK-IR",
        "QK-ROUTER",
        "QK-EVIDENCE",
        "QK-CLAIM",
        "QK-GUILD",
    },
    "KQ-READINESS-SHIELD": {
        "QS-01",
        "QS-02",
        "QS-03",
        "QS-04",
        "QS-05",
        "QK-EVIDENCE",
        "QK-CLAIM",
    },
    "KQ-MATERIALS-GARDEN": {
        "QK-CORE",
        "QK-SIM",
        "QK-IR",
        "QK-EVIDENCE",
        "QK-CLAIM",
        "QK-CHEM",
        "QK-EST",
    },
    "KQ-FAIRQUEUE": {
        "QK-CAPS",
        "QK-SIM",
        "QK-ROUTER",
        "QK-EVIDENCE",
        "QK-CLAIM",
        "QK-EST",
    },
    "KQ-NETWORK-SANDBOX": {
        "QK-CORE",
        "QK-SIM",
        "QK-EVIDENCE",
        "QK-CLAIM",
        "QN-01",
        "QN-02",
    },
}
REQUIRED_PRODUCT_POWER_MODULES = {
    "KP-INFLUENCE-LENS": {"KPM-D01", "KPM-D02", "KPM-D03", "KPM-D04"},
    "KP-CONSENT-GATE": {"KPM-D03", "KPM-D05", "KPM-D07", "KPM-D09"},
    "KP-PROOF-COMMONS": {
        "KPM-O06",
        "KPM-D01",
        "KPM-D04",
        "KPM-D06",
        "KPM-D07",
        "KPM-D08",
        "KPM-D09",
    },
    "KP-STEWARD": {
        "KPM-D01",
        "KPM-D05",
        "KPM-D06",
        "KPM-D07",
        "KPM-D08",
    },
    "KP-COMMON-TABLE": {
        "KPM-D01",
        "KPM-D03",
        "KPM-D04",
        "KPM-D06",
        "KPM-D07",
        "KPM-D08",
        "KPM-D09",
    },
    "KP-TREASURY-GATE": {
        "KPM-O05",
        "KPM-D01",
        "KPM-D04",
        "KPM-D08",
        "KPM-D09",
    },
    "KP-CREATOR-FORGE": {
        "KPM-O02",
        "KPM-O04",
        "KPM-D03",
        "KPM-D04",
        "KPM-D06",
        "KPM-D09",
    },
    "KQ-COMMONS-STUDIO": {
        "KPM-O02",
        "KPM-O04",
        "KPM-D01",
        "KPM-D05",
        "KPM-D08",
        "KPM-D09",
    },
    "KQ-READINESS-SHIELD": {
        "KPM-O02",
        "KPM-D01",
        "KPM-D04",
        "KPM-D05",
        "KPM-D08",
        "KPM-D09",
    },
    "KQ-MATERIALS-GARDEN": {
        "KPM-O02",
        "KPM-O04",
        "KPM-O05",
        "KPM-D04",
        "KPM-D08",
        "KPM-D09",
    },
    "KQ-FAIRQUEUE": {
        "KPM-D01",
        "KPM-D05",
        "KPM-D06",
        "KPM-D08",
        "KPM-D09",
    },
    "KQ-NETWORK-SANDBOX": {
        "KPM-O02",
        "KPM-O04",
        "KPM-D01",
        "KPM-D06",
        "KPM-D08",
    },
}
REQUIRED_PRODUCT_FIREWALLS = {
    "KP-INFLUENCE-LENS": {"CF-01", "CF-04", "CF-05", "CF-06"},
    "KP-CONSENT-GATE": {"CF-01", "CF-02", "CF-03", "CF-04", "CF-12"},
    "KP-PROOF-COMMONS": {"CF-05", "CF-06", "CF-07", "CF-08", "CF-12"},
    "KP-STEWARD": {"CF-08", "CF-10", "CF-12"},
    "KP-COMMON-TABLE": {"CF-02", "CF-03", "CF-09", "CF-10", "CF-12"},
    "KP-TREASURY-GATE": {
        "CF-04",
        "CF-07",
        "CF-08",
        "CF-09",
        "CF-11",
        "CF-12",
    },
    "KP-CREATOR-FORGE": {
        "CF-01",
        "CF-02",
        "CF-07",
        "CF-08",
        "CF-09",
        "CF-11",
        "CF-12",
    },
    "KQ-COMMONS-STUDIO": {
        "CF-03",
        "CF-04",
        "CF-05",
        "CF-06",
        "CF-07",
        "CF-09",
        "CF-11",
        "CF-12",
    },
    "KQ-READINESS-SHIELD": {"CF-03", "CF-05", "CF-06", "CF-09", "CF-12"},
    "KQ-MATERIALS-GARDEN": {
        "CF-05",
        "CF-06",
        "CF-07",
        "CF-08",
        "CF-09",
        "CF-11",
        "CF-12",
    },
    "KQ-FAIRQUEUE": {"CF-04", "CF-07", "CF-08", "CF-09", "CF-10", "CF-12"},
    "KQ-NETWORK-SANDBOX": {"CF-05", "CF-09", "CF-10", "CF-12"},
}
PROHIBITED_REVENUE_PATTERNS = (
    r"\bper[- ]conversion\b",
    r"\bper[- ]consent\b",
    r"\bper[- ]sanction\b",
    r"\bpercentage of (findings|rewards|treasury|transactions)\b",
    r"\btoken appreciation\b",
    r"\bsale of (personal|consent|moderation) data\b",
)


@lru_cache(maxsize=None)
def packaged_schema_bytes(schema_name: str) -> bytes:
    try:
        resource = (
            resources.files("kingdom_quantum_lab")
            .joinpath("data")
            .joinpath("schemas")
            .joinpath(schema_name)
        )
        return resource.read_bytes()
    except OSError as exc:
        raise ContractError(f"cannot load packaged schema {schema_name}: {exc}") from exc


@lru_cache(maxsize=None)
def _schema_validator(schema_name: str) -> Draft202012Validator:
    try:
        schema = json.loads(packaged_schema_bytes(schema_name))
        Draft202012Validator.check_schema(schema)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load packaged schema {schema_name}: {exc}") from exc
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_against_schema(value: Any, schema_name: str) -> None:
    errors = sorted(
        _schema_validator(schema_name).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if not errors:
        return
    error = errors[0]
    location = ".".join(str(part) for part in error.absolute_path) or "<root>"
    raise ContractError(f"schema violation at {location}: {error.message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read JSON contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"contract root must be an object: {path}")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise ContractError(f"cannot hash artifact {path}: {exc}") from exc


def _require_object(parent: dict[str, Any], name: str) -> dict[str, Any]:
    value = parent.get(name)
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be an object")
    return value


def _require_nonempty_string(parent: dict[str, Any], name: str) -> str:
    value = parent.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a non-empty string")
    return value


def _require_nonempty_list(parent: dict[str, Any], name: str) -> list[Any]:
    value = parent.get(name)
    if not isinstance(value, list) or not value:
        raise ContractError(f"{name} must be a non-empty array")
    return value


def resolve_bounded_artifact(manifest_path: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ContractError("artifact path must be non-empty and relative")
    base = manifest_path.parent.resolve()
    artifact = (base / relative_path).resolve()
    if artifact != base and base not in artifact.parents:
        raise ContractError("artifact path escapes the experiment directory")
    if not artifact.is_file():
        raise ContractError(f"artifact does not exist: {relative_path}")
    return artifact


def validate_experiment(
    manifest: dict[str, Any], manifest_path: Path
) -> dict[str, Any]:
    validate_against_schema(manifest, "experiment-plan.v1.schema.json")
    if manifest.get("schema") != "kingdom.quantum-experiment/v1":
        raise ContractError("unsupported experiment schema")

    for name in ("experiment_id", "title", "purpose", "hypothesis"):
        _require_nonempty_string(manifest, name)
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,127}", manifest["experiment_id"]):
        raise ContractError("experiment_id has an invalid form")

    if manifest.get("status") not in {
        "draft",
        "reviewed",
        "approved-for-local-simulation",
        "deprecated",
    }:
        raise ContractError("unsupported experiment status")

    if manifest.get("domain") not in {
        "conformance",
        "chemistry-materials",
        "optimization",
        "security",
        "networking",
        "education",
    }:
        raise ContractError("unsupported experiment domain")

    representation = _require_object(manifest, "representation")
    if representation.get("kind") != "openqasm3":
        raise ContractError("the reference runner only accepts openqasm3")
    program_path = resolve_bounded_artifact(
        manifest_path, _require_nonempty_string(representation, "path")
    )
    if representation.get("native_sidecars") != []:
        raise ContractError("the reference runner does not accept native sidecars")

    baseline = _require_object(manifest, "classical_baseline")
    if baseline.get("required") is not True:
        raise ContractError("a classical baseline is required")
    _require_nonempty_string(baseline, "method")
    expected = _require_object(baseline, "expected_distribution")
    if not expected:
        raise ContractError("expected_distribution cannot be empty")
    probability_sum = 0.0
    for bitstring, probability in expected.items():
        if not isinstance(bitstring, str) or not re.fullmatch(r"[01]+", bitstring):
            raise ContractError("baseline keys must be binary bitstrings")
        if (
            isinstance(probability, bool)
            or not isinstance(probability, (int, float))
            or not 0 <= probability <= 1
        ):
            raise ContractError("baseline probabilities must be between 0 and 1")
        probability_sum += float(probability)
    if abs(probability_sum - 1.0) > 1e-9:
        raise ContractError("baseline probabilities must sum to 1")

    policy = _require_object(manifest, "execution_policy")
    if policy.get("mode") != "local-simulator-only":
        raise ContractError("reference execution must be local-simulator-only")
    if policy.get("network_allowed") is not False:
        raise ContractError("reference execution must prohibit network access")
    if policy.get("max_cost_gbp") != 0:
        raise ContractError("reference execution must have a zero cost ceiling")
    if policy.get("data_classification") != "public-synthetic":
        raise ContractError("reference execution accepts public-synthetic data only")
    allowed_adapters = _require_nonempty_list(policy, "allowed_adapters")
    if allowed_adapters != [LOCAL_REFERENCE_ADAPTER]:
        raise ContractError("reference adapter must be the sole allowed adapter")
    max_shots = policy.get("max_shots")
    if not isinstance(max_shots, int) or isinstance(max_shots, bool):
        raise ContractError("max_shots must be an integer")
    if not 1 <= max_shots <= 100_000:
        raise ContractError("max_shots must be between 1 and 100000")
    default_shots = policy.get("default_shots")
    if not isinstance(default_shots, int) or isinstance(default_shots, bool):
        raise ContractError("default_shots must be an integer")
    if not 1 <= default_shots <= max_shots:
        raise ContractError("default_shots must be within the max_shots boundary")

    rights = _require_object(manifest, "rights")
    if rights.get("human_data") is not False:
        raise ContractError("reference experiments must not contain human data")
    if rights.get("personal_data") != "none":
        raise ContractError("reference experiments must declare no personal data")
    _require_nonempty_string(rights, "license")
    _require_nonempty_string(rights, "attribution")

    evidence_target = manifest.get("evidence_target")
    if evidence_target not in EVIDENCE_GRADES:
        raise ContractError("unknown evidence target")
    if evidence_target != "E0":
        raise ContractError("the local reference runner can target only E0")

    _require_nonempty_list(manifest, "metrics")
    _require_nonempty_list(manifest, "stop_conditions")
    _require_nonempty_list(manifest, "limitations")

    return {
        "manifest": manifest,
        "manifest_path": manifest_path.resolve(),
        "program_path": program_path,
    }


def validate_registry(registry: dict[str, Any]) -> dict[str, Any]:
    validate_against_schema(registry, "ecosystem-registry.v1.schema.json")
    if registry.get("schema") != "kingdom.quantum-ecosystems/v1":
        raise ContractError("unsupported ecosystem registry schema")
    as_of = _require_nonempty_string(registry, "as_of")
    try:
        date.fromisoformat(as_of)
    except ValueError as exc:
        raise ContractError("as_of must be an ISO calendar date") from exc
    _require_nonempty_string(registry, "boundary")
    ecosystems = _require_nonempty_list(registry, "ecosystems")
    modules = _require_nonempty_list(registry, "modules")
    _require_nonempty_list(registry, "power_centers")

    for collection_name, collection in (
        ("ecosystem", ecosystems),
        ("module", modules),
    ):
        seen: set[str] = set()
        for entry in collection:
            if not isinstance(entry, dict):
                raise ContractError(f"{collection_name} entries must be objects")
            entry_id = _require_nonempty_string(entry, "id")
            if entry_id in seen:
                raise ContractError(f"duplicate {collection_name} id: {entry_id}")
            seen.add(entry_id)

    for ecosystem in ecosystems:
        for name in (
            "name",
            "category",
            "valuable_capability",
            "power_boundary",
            "kingdom_move",
            "does_not_prove",
        ):
            _require_nonempty_string(ecosystem, name)
        if ecosystem.get("posture") not in {
            "adopt",
            "contribute",
            "experiment",
            "engage",
            "watch",
            "avoid-dependency",
        }:
            raise ContractError(f"invalid posture for {ecosystem['id']}")
        for score_name in ("value_now", "openness", "lock_in_risk"):
            score = ecosystem.get(score_name)
            if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 5:
                raise ContractError(
                    f"{score_name} for {ecosystem['id']} must be an integer from 0 to 5"
                )
        urls = _require_nonempty_list(ecosystem, "source_urls")
        if any(not isinstance(url, str) or not url.startswith("https://") for url in urls):
            raise ContractError(f"source URLs for {ecosystem['id']} must use HTTPS")

    module_ids = {entry["id"] for entry in modules}
    dependency_graph: dict[str, list[str]] = {}
    for module in modules:
        for name in ("name", "does", "does_not"):
            _require_nonempty_string(module, name)
        if module.get("kind") not in {"creation", "defense", "bridge", "research"}:
            raise ContractError(f"invalid module kind for {module['id']}")
        if module.get("status") not in {"seeded", "proposed", "gated", "watch"}:
            raise ContractError(f"invalid module status for {module['id']}")
        dependencies = module.get("depends_on")
        if not isinstance(dependencies, list) or any(
            not isinstance(item, str) or not item for item in dependencies
        ):
            raise ContractError(f"depends_on for {module['id']} must be a string array")
        unknown = sorted(set(dependencies) - module_ids)
        if unknown:
            raise ContractError(
                f"unknown dependencies for {module['id']}: {', '.join(unknown)}"
            )
        if module["id"] in dependencies:
            raise ContractError(f"module {module['id']} cannot depend on itself")
        dependency_graph[module["id"]] = dependencies
    _reject_dependency_cycles(dependency_graph, "module")

    power_centers = registry["power_centers"]
    seen_power_ids: set[str] = set()
    for power_center in power_centers:
        if not isinstance(power_center, dict):
            raise ContractError("power center entries must be objects")
        power_id = _require_nonempty_string(power_center, "id")
        if power_id in seen_power_ids:
            raise ContractError(f"duplicate power center id: {power_id}")
        seen_power_ids.add(power_id)
        for name in ("controller", "leverage", "risk", "counterweight", "hold_authority"):
            _require_nonempty_string(power_center, name)

    return registry


def validate_power_module_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    validate_against_schema(snapshot, "power-module-snapshot.v1.schema.json")
    if snapshot.get("schema") != "kingdom.power-module-snapshot/v1":
        raise ContractError("unsupported power module snapshot schema")
    try:
        date.fromisoformat(_require_nonempty_string(snapshot, "snapshot_date"))
    except ValueError as exc:
        raise ContractError("power snapshot_date must be an ISO calendar date") from exc

    modules: dict[str, str] = {}
    for module in _require_nonempty_list(snapshot, "modules"):
        if not isinstance(module, dict):
            raise ContractError("power module snapshot entries must be objects")
        module_id = _require_nonempty_string(module, "id")
        if module_id in modules:
            raise ContractError(f"duplicate power module id: {module_id}")
        modules[module_id] = _require_nonempty_string(module, "name")
    if modules != CANONICAL_POWER_MODULES:
        missing = sorted(set(CANONICAL_POWER_MODULES) - set(modules))
        extra = sorted(set(modules) - set(CANONICAL_POWER_MODULES))
        renamed = sorted(
            module_id
            for module_id in set(modules) & set(CANONICAL_POWER_MODULES)
            if modules[module_id] != CANONICAL_POWER_MODULES[module_id]
        )
        raise ContractError(
            "power module snapshot differs from canonical v1 "
            f"(missing={missing}, extra={extra}, renamed={renamed})"
        )
    if snapshot["source"]["sha256"] != POWER_MODULE_SOURCE_SHA256:
        raise ContractError("power module source digest differs from canonical v1")
    return snapshot


def validate_product_portfolio(
    portfolio: dict[str, Any],
    known_module_ids: set[str],
    power_module_snapshot: dict[str, Any],
) -> dict[str, Any]:
    validate_against_schema(portfolio, "product-portfolio.v1.schema.json")
    if portfolio.get("schema") != "kingdom.product-portfolio/v1":
        raise ContractError("unsupported product portfolio schema")
    try:
        date.fromisoformat(_require_nonempty_string(portfolio, "as_of"))
    except ValueError as exc:
        raise ContractError("product portfolio as_of must be an ISO calendar date") from exc
    if portfolio["boundary"] != CANONICAL_PRODUCT_BOUNDARY:
        raise ContractError("product portfolio boundary differs from canonical v1")
    if portfolio["principles"] != list(CANONICAL_PRODUCT_PRINCIPLES):
        raise ContractError("product portfolio principles differ from canonical v1")

    snapshot = validate_power_module_snapshot(power_module_snapshot)
    power_ref = portfolio["power_architecture_ref"]
    if power_ref["snapshot_schema"] != snapshot["schema"]:
        raise ContractError("power architecture snapshot schema does not match")
    if power_ref["registry_schema"] != snapshot["source"]["registry_schema"]:
        raise ContractError("power architecture registry schema does not match")
    if power_ref["snapshot_date"] != snapshot["snapshot_date"]:
        raise ContractError("power architecture snapshot date does not match")
    if power_ref["source_sha256"] != snapshot["source"]["sha256"]:
        raise ContractError("power architecture source digest does not match")
    known_power_module_ids = {module["id"] for module in snapshot["modules"]}

    conversions = _require_nonempty_list(portfolio, "conversion_firewalls")
    conversion_ids: set[str] = set()
    for conversion in conversions:
        if not isinstance(conversion, dict):
            raise ContractError("conversion firewall entries must be objects")
        conversion_id = _require_nonempty_string(conversion, "id")
        if conversion_id in conversion_ids:
            raise ContractError(f"duplicate conversion firewall id: {conversion_id}")
        conversion_ids.add(conversion_id)
    if conversion_ids != CANONICAL_FIREWALL_IDS:
        missing = sorted(CANONICAL_FIREWALL_IDS - conversion_ids)
        extra = sorted(conversion_ids - CANONICAL_FIREWALL_IDS)
        raise ContractError(
            "conversion firewalls differ from canonical v1 "
            f"(missing={missing}, extra={extra})"
        )
    firewall_digest = sha256_bytes(canonical_json_bytes(conversions))
    if (
        firewall_digest != CANONICAL_FIREWALLS_SHA256
        or portfolio["conversion_firewalls_sha256"] != firewall_digest
    ):
        raise ContractError("conversion firewall content differs from canonical v1")

    products = _require_nonempty_list(portfolio, "products")
    product_ids: set[str] = set()
    for product in products:
        if not isinstance(product, dict):
            raise ContractError("product entries must be objects")
        product_id = _require_nonempty_string(product, "id")
        if product_id in product_ids:
            raise ContractError(f"duplicate product id: {product_id}")
        product_ids.add(product_id)
        expected_prefix = "KP-" if product["family"] == "constitutional" else "KQ-"
        if not product_id.startswith(expected_prefix):
            raise ContractError(
                f"product {product_id} does not match its {product['family']} family"
            )
    if product_ids != CORE_PRODUCT_IDS:
        missing_core_products = sorted(CORE_PRODUCT_IDS - product_ids)
        extra_products = sorted(product_ids - CORE_PRODUCT_IDS)
        raise ContractError(
            "product set differs from canonical v1 "
            f"(missing={missing_core_products}, extra={extra_products})"
        )

    dependency_graph: dict[str, list[str]] = {}
    for product in products:
        product_id = product["id"]
        module_dependencies = product["module_dependencies"]
        unknown_modules = sorted(set(module_dependencies) - known_module_ids)
        if unknown_modules:
            raise ContractError(
                f"unknown module dependencies for {product_id}: "
                f"{', '.join(unknown_modules)}"
            )
        missing_required_modules = sorted(
            REQUIRED_PRODUCT_MODULES[product_id] - set(module_dependencies)
        )
        if missing_required_modules:
            raise ContractError(
                f"missing required module dependencies for {product_id}: "
                f"{', '.join(missing_required_modules)}"
            )
        power_dependencies = product["power_dependencies"]
        unknown_power_modules = sorted(
            set(power_dependencies) - known_power_module_ids
        )
        if unknown_power_modules:
            raise ContractError(
                f"unknown power module dependencies for {product_id}: "
                f"{', '.join(unknown_power_modules)}"
            )
        missing_required_power_modules = sorted(
            REQUIRED_PRODUCT_POWER_MODULES[product_id] - set(power_dependencies)
        )
        if missing_required_power_modules:
            raise ContractError(
                f"missing required power module dependencies for {product_id}: "
                f"{', '.join(missing_required_power_modules)}"
            )
        firewall_dependencies = product["firewall_dependencies"]
        unknown_firewalls = sorted(set(firewall_dependencies) - conversion_ids)
        if unknown_firewalls:
            raise ContractError(
                f"unknown firewall dependencies for {product_id}: "
                f"{', '.join(unknown_firewalls)}"
            )
        product_dependencies = product["product_dependencies"]
        unknown_products = sorted(set(product_dependencies) - product_ids)
        if unknown_products:
            raise ContractError(
                f"unknown product dependencies for {product_id}: "
                f"{', '.join(unknown_products)}"
            )
        if product_id in product_dependencies:
            raise ContractError(f"product {product_id} cannot depend on itself")
        missing_required_products = sorted(
            REQUIRED_PRODUCT_DEPENDENCIES.get(product_id, set())
            - set(product_dependencies)
        )
        if missing_required_products:
            raise ContractError(
                f"missing required product dependencies for {product_id}: "
                f"{', '.join(missing_required_products)}"
            )
        missing_required_firewalls = sorted(
            REQUIRED_PRODUCT_FIREWALLS.get(product_id, set())
            - set(firewall_dependencies)
        )
        if missing_required_firewalls:
            raise ContractError(
                f"missing required firewall dependencies for {product_id}: "
                f"{', '.join(missing_required_firewalls)}"
            )
        implementation = product["implementation"]
        if (
            implementation["state"] != "declared-only"
            and not implementation["evidence_refs"]
        ):
            raise ContractError(
                f"implemented product {product_id} requires evidence_refs"
            )
        if (
            implementation["state"] == "declared-only"
            and implementation["evidence_refs"]
        ):
            raise ContractError(
                f"declared-only product {product_id} cannot claim implementation evidence"
            )
        if (
            product["design_stage"] == "prototype"
        ) != (
            implementation["state"] != "declared-only"
        ):
            raise ContractError(
                f"design stage and implementation state disagree for {product_id}"
            )
        for evidence_ref in implementation["evidence_refs"]:
            evidence_bytes = _packaged_implementation_evidence_bytes(
                evidence_ref["path"]
            )
            actual_digest = sha256_bytes(evidence_bytes)
            if actual_digest != evidence_ref["sha256"]:
                raise ContractError(
                    f"implementation evidence digest mismatch for {product_id}: "
                    f"{evidence_ref['path']}"
                )
        business_description = product["business_model"]["description"].lower()
        for pattern in PROHIBITED_REVENUE_PATTERNS:
            if re.search(pattern, business_description):
                raise ContractError(
                    f"prohibited revenue language for {product_id}: {pattern}"
                )
        for dependency_name in (
            "firewall_dependencies",
            "module_dependencies",
            "power_dependencies",
            "product_dependencies",
        ):
            dependencies = product[dependency_name]
            if len(dependencies) != len(set(dependencies)):
                raise ContractError(
                    f"duplicate {dependency_name} for product {product_id}"
                )
        dependency_graph[product_id] = product_dependencies
    _reject_dependency_cycles(dependency_graph, "product")
    return portfolio


def _packaged_implementation_evidence_bytes(path_value: str) -> bytes:
    prefix = "src/kingdom_quantum_lab/"
    if not path_value.startswith(prefix):
        raise ContractError("implementation evidence path must be package-relative")
    raw_relative_path = path_value.removeprefix(prefix)
    relative_path = PurePosixPath(raw_relative_path)
    if (
        raw_relative_path != relative_path.as_posix()
        or relative_path.is_absolute()
        or not relative_path.parts
        or any(part in {"", ".", ".."} for part in relative_path.parts)
    ):
        raise ContractError("implementation evidence path is not normalized")
    resource = resources.files("kingdom_quantum_lab")
    for part in relative_path.parts:
        resource = resource.joinpath(part)
    try:
        return resource.read_bytes()
    except OSError as exc:
        raise ContractError(
            f"cannot load implementation evidence {path_value}: {exc}"
        ) from exc


def validate_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    validate_against_schema(receipt, "quantum-run-receipt.v1.schema.json")

    body = {key: value for key, value in receipt.items() if key != "receipt_id"}
    expected_id = f"qr-{sha256_bytes(canonical_json_bytes(body))[:24]}"
    if receipt["receipt_id"] != expected_id:
        raise ContractError("receipt_id does not match the canonical receipt content")

    execution = receipt["execution"]
    qubits = execution["qubits"]
    shots = execution["shots"]
    counts = execution["counts"]
    if any(len(outcome) != qubits for outcome in counts):
        raise ContractError("receipt count keys must match the declared qubit width")
    if sum(counts.values()) != shots:
        raise ContractError("receipt counts must sum to shots")

    observed = execution["observed_distribution"]
    exact = execution["exact_simulator_distribution"]
    baseline = receipt["baseline"]["expected_distribution"]
    for label, distribution in (
        ("observed", observed),
        ("exact simulator", exact),
        ("baseline", baseline),
    ):
        if any(len(outcome) != qubits for outcome in distribution):
            raise ContractError(f"{label} keys must match the declared qubit width")
        if abs(sum(distribution.values()) - 1.0) > 1e-9:
            raise ContractError(f"{label} probabilities must sum to 1")

    expected_observed = {
        outcome: count / shots for outcome, count in sorted(counts.items())
    }
    if observed != expected_observed:
        raise ContractError("observed_distribution does not match counts and shots")

    outcomes = set(observed) | set(baseline)
    expected_tvd = 0.5 * sum(
        abs(observed.get(outcome, 0.0) - baseline.get(outcome, 0.0))
        for outcome in outcomes
    )
    if abs(receipt["baseline"]["total_variation_distance"] - expected_tvd) > 1e-12:
        raise ContractError("baseline total_variation_distance is inconsistent")
    return receipt


def _reject_dependency_cycles(graph: dict[str, list[str]], dependency_kind: str) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ContractError(
                f"{dependency_kind} dependency cycle includes {node}"
            )
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
