from __future__ import annotations

import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from importlib import resources
from pathlib import Path

from kingdom_quantum_lab.cli import main
from kingdom_quantum_lab.contracts import (
    ContractError,
    load_json,
    validate_power_module_snapshot,
    validate_product_portfolio,
    validate_registry,
)


ROOT = Path(__file__).resolve().parents[1]


class ProductPortfolioTests(unittest.TestCase):
    def setUp(self) -> None:
        ecosystem_registry = validate_registry(
            load_json(ROOT / "registry" / "ecosystems.json")
        )
        self.module_ids = {
            module["id"] for module in ecosystem_registry["modules"]
        }
        self.power_snapshot = validate_power_module_snapshot(
            load_json(ROOT / "registry" / "power-modules.snapshot.json")
        )
        self.portfolio = load_json(ROOT / "registry" / "products.json")

    def validate(self, portfolio: dict[str, object]) -> dict[str, object]:
        return validate_product_portfolio(
            portfolio,
            self.module_ids,
            self.power_snapshot,
        )

    def test_product_portfolio_is_semantically_valid(self) -> None:
        portfolio = self.validate(self.portfolio)
        self.assertEqual(len(portfolio["conversion_firewalls"]), 12)
        self.assertEqual(len(portfolio["products"]), 12)
        self.assertEqual(
            {product["family"] for product in portfolio["products"]},
            {"constitutional", "quantum"},
        )
        self.assertFalse(
            portfolio["implementation_truth"][
                "portfolio_validation_proves_runtime_enforcement"
            ]
        )

    def test_governance_and_resource_allocation_remain_separate(self) -> None:
        products = {product["id"]: product for product in self.portfolio["products"]}
        self.assertIn("KP-COMMON-TABLE", products)
        self.assertIn("KQ-FAIRQUEUE", products)
        self.assertIn(
            "KP-STEWARD",
            products["KP-COMMON-TABLE"]["product_dependencies"],
        )
        self.assertIn(
            "KP-COMMON-TABLE",
            products["KP-TREASURY-GATE"]["product_dependencies"],
        )
        self.assertIn(
            "KP-COMMON-TABLE",
            products["KQ-FAIRQUEUE"]["product_dependencies"],
        )
        self.assertIn(
            "KQ-FAIRQUEUE",
            products["KQ-NETWORK-SANDBOX"]["product_dependencies"],
        )

    def test_unknown_module_dependency_fails_closed(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        changed["products"][0]["module_dependencies"].append("QK-UNKNOWN")
        with self.assertRaisesRegex(ContractError, "unknown module dependencies"):
            self.validate(changed)

    def test_unknown_power_module_dependency_fails_closed(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        changed["products"][0]["power_dependencies"].append("KPM-D99")
        with self.assertRaisesRegex(ContractError, "unknown power module dependencies"):
            self.validate(changed)

    def test_product_dependency_cycle_is_rejected(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        changed["products"][0]["product_dependencies"] = ["KP-CREATOR-FORGE"]
        with self.assertRaisesRegex(ContractError, "dependency cycle"):
            self.validate(changed)

    def test_required_constitutional_dependency_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        fairqueue = next(
            product
            for product in changed["products"]
            if product["id"] == "KQ-FAIRQUEUE"
        )
        fairqueue["product_dependencies"] = ["KQ-COMMONS-STUDIO"]
        with self.assertRaisesRegex(ContractError, "required product dependencies"):
            self.validate(changed)

    def test_product_set_is_closed_for_v1(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        invented = copy.deepcopy(changed["products"][0])
        invented["id"] = "KQ-COERCION-ENGINE"
        invented["name"] = "Invented product"
        invented["family"] = "quantum"
        changed["products"].append(invented)
        with self.assertRaisesRegex(ContractError, "product set differs"):
            self.validate(changed)

    def test_required_module_dependency_cannot_be_replaced(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        consent = next(
            product
            for product in changed["products"]
            if product["id"] == "KP-CONSENT-GATE"
        )
        consent["module_dependencies"] = []
        with self.assertRaisesRegex(ContractError, "required module dependencies"):
            self.validate(changed)

    def test_required_power_counterweight_cannot_be_replaced(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        consent = next(
            product
            for product in changed["products"]
            if product["id"] == "KP-CONSENT-GATE"
        )
        consent["power_dependencies"] = ["KPM-O01"]
        with self.assertRaisesRegex(ContractError, "required power module dependencies"):
            self.validate(changed)

    def test_required_firewall_dependency_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        fairqueue = next(
            product
            for product in changed["products"]
            if product["id"] == "KQ-FAIRQUEUE"
        )
        fairqueue["firewall_dependencies"].remove("CF-09")
        with self.assertRaisesRegex(ContractError, "required firewall dependencies"):
            self.validate(changed)

    def test_conversion_cannot_be_automatic(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        changed["conversion_firewalls"][0]["automatic"] = True
        with self.assertRaisesRegex(ContractError, "schema violation"):
            self.validate(changed)

    def test_all_canonical_firewalls_are_required(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        changed["conversion_firewalls"] = changed["conversion_firewalls"][:1]
        with self.assertRaisesRegex(ContractError, "schema violation"):
            self.validate(changed)

    def test_canonical_firewall_semantics_cannot_be_replaced(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        changed["conversion_firewalls"][0]["gate"] = (
            "Maximize coercive conversion."
        )
        with self.assertRaisesRegex(ContractError, "firewall content differs"):
            self.validate(changed)

    def test_canonical_principles_cannot_be_replaced(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        changed["principles"] = ["Maximize conversion and lock-in"] * 8
        with self.assertRaisesRegex(ContractError, "principles differ"):
            self.validate(changed)

    def test_canonical_boundary_cannot_be_replaced(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        changed["boundary"] = "All listed products are live and universally safe."
        with self.assertRaisesRegex(ContractError, "boundary differs"):
            self.validate(changed)

    def test_whitespace_only_pressure_and_release_boundaries_fail(self) -> None:
        for field in ("pressure_boundary", "release_gate"):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.portfolio)
                changed["products"][0][field] = "   \n"
                with self.assertRaisesRegex(ContractError, "schema violation"):
                    self.validate(changed)

    def test_conversion_linked_revenue_fails_closed(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        changed["products"][0]["business_model"]["per_conversion_revenue"] = True
        with self.assertRaisesRegex(ContractError, "schema violation"):
            self.validate(changed)

    def test_conversion_linked_revenue_language_fails_closed(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        changed["products"][0]["business_model"]["description"] = (
            "Charge per conversion and maximize lock-in."
        )
        with self.assertRaisesRegex(ContractError, "prohibited revenue language"):
            self.validate(changed)

    def test_non_declared_implementation_requires_evidence(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        proof = next(
            product
            for product in changed["products"]
            if product["id"] == "KP-PROOF-COMMONS"
        )
        proof["implementation"]["evidence_refs"] = []
        with self.assertRaisesRegex(ContractError, "requires evidence_refs"):
            self.validate(changed)

    def test_implementation_evidence_path_must_exist(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        proof = next(
            product
            for product in changed["products"]
            if product["id"] == "KP-PROOF-COMMONS"
        )
        proof["implementation"]["evidence_refs"][0] = {
            "path": "src/kingdom_quantum_lab/not/a/real/file.py",
            "sha256": "0" * 64,
        }
        with self.assertRaisesRegex(ContractError, "cannot load implementation evidence"):
            self.validate(changed)

    def test_implementation_evidence_path_must_be_normalized(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        proof = next(
            product
            for product in changed["products"]
            if product["id"] == "KP-PROOF-COMMONS"
        )
        proof["implementation"]["evidence_refs"][0]["path"] = (
            "src/kingdom_quantum_lab/./simulator.py"
        )
        with self.assertRaisesRegex(ContractError, "path is not normalized"):
            self.validate(changed)

    def test_implementation_evidence_digest_must_match(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        proof = next(
            product
            for product in changed["products"]
            if product["id"] == "KP-PROOF-COMMONS"
        )
        proof["implementation"]["evidence_refs"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ContractError, "evidence digest mismatch"):
            self.validate(changed)

    def test_design_stage_and_implementation_state_must_agree(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        changed["products"][0]["design_stage"] = "prototype"
        with self.assertRaisesRegex(ContractError, "implementation state disagree"):
            self.validate(changed)

    def test_product_cannot_claim_live_effects(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        changed["products"][0]["implementation"]["live_effects"] = True
        with self.assertRaisesRegex(ContractError, "schema violation"):
            self.validate(changed)

    def test_power_snapshot_digest_must_match(self) -> None:
        changed = copy.deepcopy(self.portfolio)
        changed["power_architecture_ref"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ContractError, "source digest does not match"):
            self.validate(changed)

    def test_power_snapshot_cannot_invent_counterweight(self) -> None:
        changed = copy.deepcopy(self.power_snapshot)
        changed["modules"].append(
            {
                "id": "KPM-D99",
                "name": "invented_counterweight",
                "implementation_profile": "proposed_unwired",
                "activated": False,
            }
        )
        with self.assertRaisesRegex(ContractError, "differs from canonical"):
            validate_power_module_snapshot(changed)

    def test_default_json_cli_preserves_constitutional_envelope(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["products", "--json"]), 0)
        value = json.loads(output.getvalue())
        self.assertIn("boundary", value)
        self.assertIn("constitutional_invariants", value)
        self.assertIn("conversion_firewalls", value)
        self.assertIn("products", value)

    def test_products_only_json_requires_explicit_flag(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(
                main(["products", "--json", "--products-only"]),
                0,
            )
        self.assertEqual(len(json.loads(output.getvalue())), 12)

    def test_product_registry_and_schema_are_packaged(self) -> None:
        root = resources.files("kingdom_quantum_lab").joinpath("data")
        self.assertTrue(root.joinpath("registry").joinpath("products.json").is_file())
        self.assertTrue(
            root.joinpath("registry")
            .joinpath("power-modules.snapshot.json")
            .is_file()
        )
        self.assertTrue(
            root.joinpath("schemas")
            .joinpath("product-portfolio.v1.schema.json")
            .is_file()
        )
        self.assertTrue(
            root.joinpath("schemas")
            .joinpath("power-module-snapshot.v1.schema.json")
            .is_file()
        )


if __name__ == "__main__":
    unittest.main()
