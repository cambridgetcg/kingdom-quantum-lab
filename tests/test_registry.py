from __future__ import annotations

import unittest
from importlib import resources
from pathlib import Path

from kingdom_quantum_lab.contracts import load_json, validate_registry


ROOT = Path(__file__).resolve().parents[1]


class RegistryTests(unittest.TestCase):
    def test_registry_is_semantically_valid(self) -> None:
        path = ROOT / "registry" / "ecosystems.json"
        registry = validate_registry(load_json(path))
        self.assertGreaterEqual(len(registry["ecosystems"]), 10)
        self.assertGreaterEqual(len(registry["modules"]), 10)

    def test_registry_is_packaged_with_the_cli(self) -> None:
        resource = (
            resources.files("kingdom_quantum_lab")
            .joinpath("data")
            .joinpath("registry")
            .joinpath("ecosystems.json")
        )
        self.assertTrue(resource.is_file())


if __name__ == "__main__":
    unittest.main()
