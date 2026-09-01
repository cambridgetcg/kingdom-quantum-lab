from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from kingdom_quantum_lab.contracts import (
    ContractError,
    canonical_json_bytes,
    load_json,
    sha256_bytes,
    validate_experiment,
)
from kingdom_quantum_lab.cli import main
from kingdom_quantum_lab.simulator import (
    parse_openqasm_subset,
    run_reference_experiment,
    validate_reference_bundle,
    verify_reference_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "experiments" / "bell-conformance" / "experiment.json"


class ExperimentContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_json(MANIFEST_PATH)

    def test_reference_manifest_is_valid(self) -> None:
        validated = validate_experiment(self.manifest, MANIFEST_PATH)
        self.assertEqual(validated["program_path"].name, "program.qasm")

    def test_network_permission_fails_closed(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["execution_policy"]["network_allowed"] = True
        with self.assertRaisesRegex(ContractError, "network_allowed"):
            validate_experiment(changed, MANIFEST_PATH)

    def test_nonzero_cost_ceiling_fails_closed(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["execution_policy"]["max_cost_gbp"] = 1
        with self.assertRaisesRegex(ContractError, "max_cost_gbp"):
            validate_experiment(changed, MANIFEST_PATH)

    def test_schema_rejects_unknown_fields_and_missing_sidecars(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["unexpected"] = "not allowed"
        with self.assertRaisesRegex(ContractError, "schema violation"):
            validate_experiment(changed, MANIFEST_PATH)

        changed = copy.deepcopy(self.manifest)
        del changed["representation"]["native_sidecars"]
        with self.assertRaisesRegex(ContractError, "schema violation"):
            validate_experiment(changed, MANIFEST_PATH)

    def test_boolean_probability_is_rejected(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["classical_baseline"]["expected_distribution"] = {
            "00": True,
        }
        with self.assertRaisesRegex(ContractError, "schema violation"):
            validate_experiment(changed, MANIFEST_PATH)

    def test_artifact_cannot_escape_experiment_directory(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["representation"]["path"] = "../outside.qasm"
        with self.assertRaisesRegex(ContractError, "escapes"):
            validate_experiment(changed, MANIFEST_PATH)

    def test_reference_receipt_is_e0_offline_and_zero_cost(self) -> None:
        receipt = run_reference_experiment(
            self.manifest,
            MANIFEST_PATH,
            shots=4096,
            seed=1701,
            now=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(receipt["evidence_grade"], "E0")
        self.assertEqual(receipt["adapter"]["network_calls"], 0)
        self.assertEqual(receipt["accounting"]["qpu_time_seconds"], 0)
        self.assertEqual(receipt["accounting"]["cost_gbp"], 0)
        self.assertEqual(set(receipt["execution"]["counts"]), {"00", "11"})
        self.assertLess(receipt["baseline"]["total_variation_distance"], 0.03)
        self.assertRegex(receipt["receipt_id"], r"^qr-[a-f0-9]{24}$")

    def test_reference_receipt_binds_source_hashes(self) -> None:
        receipt = run_reference_experiment(
            self.manifest,
            MANIFEST_PATH,
            shots=32,
            seed=7,
            now=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
        )
        self.assertRegex(receipt["sources"]["manifest"]["sha256"], r"^[a-f0-9]{64}$")
        self.assertRegex(receipt["sources"]["program"]["sha256"], r"^[a-f0-9]{64}$")
        self.assertRegex(receipt["sources"]["runner"]["sha256"], r"^[a-f0-9]{64}$")
        self.assertRegex(receipt["sources"]["validator"]["sha256"], r"^[a-f0-9]{64}$")
        self.assertRegex(
            receipt["sources"]["experiment_schema"]["sha256"], r"^[a-f0-9]{64}$"
        )
        self.assertRegex(
            receipt["sources"]["receipt_schema"]["sha256"], r"^[a-f0-9]{64}$"
        )
        self.assertEqual(
            receipt["sources"]["schema_validator"]["distribution"],
            "jsonschema",
        )

    def test_draft_manifest_cannot_execute(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["status"] = "draft"
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            manifest_path = temp / "experiment.json"
            program_path = temp / "program.qasm"
            manifest_path.write_text(json.dumps(changed), encoding="utf-8")
            program_path.write_bytes(MANIFEST_PATH.with_name("program.qasm").read_bytes())
            with self.assertRaisesRegex(ContractError, "requires status"):
                run_reference_experiment(changed, manifest_path)

    def test_bundle_validation_parses_program(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            manifest_path = temp / "experiment.json"
            program_path = temp / "program.qasm"
            manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
            program_path.write_text("not OpenQASM", encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "must begin with OPENQASM"):
                validate_reference_bundle(self.manifest, manifest_path)

    def test_receipt_verification_detects_tampering(self) -> None:
        receipt = run_reference_experiment(
            self.manifest,
            MANIFEST_PATH,
            shots=64,
            seed=7,
            now=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
        )
        verify_reference_receipt(receipt, MANIFEST_PATH)
        changed = copy.deepcopy(receipt)
        changed["execution"]["counts"] = {"00": 1, "11": 63}
        with self.assertRaisesRegex(ContractError, "receipt_id"):
            verify_reference_receipt(changed, MANIFEST_PATH)

        changed = copy.deepcopy(receipt)
        changed["limitations"] = ["none"]
        body = {key: value for key, value in changed.items() if key != "receipt_id"}
        changed["receipt_id"] = (
            f"qr-{sha256_bytes(canonical_json_bytes(body))[:24]}"
        )
        with self.assertRaisesRegex(ContractError, "limitations"):
            verify_reference_receipt(changed, MANIFEST_PATH)

        changed = copy.deepcopy(receipt)
        changed["claim_boundary"] = "Production and quantum advantage established."
        body = {key: value for key, value in changed.items() if key != "receipt_id"}
        changed["receipt_id"] = (
            f"qr-{sha256_bytes(canonical_json_bytes(body))[:24]}"
        )
        with self.assertRaisesRegex(ContractError, "claim_boundary"):
            verify_reference_receipt(changed, MANIFEST_PATH)

    def test_cli_refuses_to_overwrite_manifest_or_existing_output(self) -> None:
        self.assertEqual(
            main(["run", str(MANIFEST_PATH), "--out", str(MANIFEST_PATH)]),
            2,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "receipt.json"
            output.write_text("preserve me", encoding="utf-8")
            self.assertEqual(
                main(["run", str(MANIFEST_PATH), "--out", str(output)]),
                2,
            )
            self.assertEqual(output.read_text(encoding="utf-8"), "preserve me")

    def test_unsupported_qasm_is_rejected(self) -> None:
        qasm = """
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[1] q;
        bit[1] c;
        rz(0.5) q[0];
        c = measure q;
        """
        with self.assertRaisesRegex(ContractError, "unsupported OpenQASM"):
            parse_openqasm_subset(qasm)

    def test_json_contract_must_be_object(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "array.json"
            path.write_text(json.dumps([]), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "root must be an object"):
                load_json(path)


if __name__ == "__main__":
    unittest.main()
