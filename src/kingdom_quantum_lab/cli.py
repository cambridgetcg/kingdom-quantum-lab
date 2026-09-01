from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from importlib import resources
from pathlib import Path
from typing import Sequence

from .contracts import (
    ContractError,
    load_json,
    validate_power_module_snapshot,
    validate_product_portfolio,
    validate_registry,
)
from .simulator import (
    run_reference_experiment,
    validate_reference_bundle,
    verify_reference_receipt,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kingdom-quantum",
        description="Validate and run bounded local KINGDOM quantum experiments.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate an experiment")
    validate.add_argument("manifest", type=Path)

    run = subparsers.add_parser("run", help="run the offline reference simulator")
    run.add_argument("manifest", type=Path)
    run.add_argument("--shots", type=int)
    run.add_argument("--seed", type=int, default=1701)
    run.add_argument("--out", type=Path)

    verify = subparsers.add_parser(
        "verify-receipt",
        help="verify an E0 receipt against its manifest and local runner",
    )
    verify.add_argument("receipt", type=Path)
    verify.add_argument("manifest", type=Path)

    ecosystems = subparsers.add_parser("ecosystems", help="show ecosystem postures")
    ecosystems.add_argument("--registry", type=Path)
    ecosystems.add_argument("--json", action="store_true")

    modules = subparsers.add_parser("modules", help="show proposed module map")
    modules.add_argument("--registry", type=Path)
    modules.add_argument("--json", action="store_true")

    products = subparsers.add_parser(
        "products", help="show rights-bounded KINGDOM product candidates"
    )
    products.add_argument("--registry", type=Path)
    products.add_argument("--ecosystems", type=Path)
    products.add_argument("--power-modules", type=Path)
    products.add_argument("--json", action="store_true")
    products.add_argument(
        "--products-only",
        action="store_true",
        help="with --json, omit the constitutional envelope intentionally",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            manifest_path = args.manifest.resolve()
            manifest = load_json(manifest_path)
            validate_reference_bundle(manifest, manifest_path)
            status = manifest["status"]
            runnable = status == "approved-for-local-simulation"
            print(
                f"valid E0 local experiment bundle: {manifest_path} "
                f"(status={status}, runnable={'yes' if runnable else 'no'})"
            )
            return 0

        if args.command == "run":
            manifest_path = args.manifest.resolve()
            manifest = load_json(manifest_path)
            if args.out:
                _guard_output_path(args.out, manifest, manifest_path)
            receipt = run_reference_experiment(
                manifest,
                manifest_path,
                shots=args.shots,
                seed=args.seed,
            )
            rendered = json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
            if args.out:
                output_path = args.out.resolve()
                _write_new_atomic(output_path, rendered)
                print(f"wrote E0 local receipt: {output_path}")
            else:
                print(rendered, end="")
            return 0

        if args.command == "verify-receipt":
            receipt_path = args.receipt.resolve()
            manifest_path = args.manifest.resolve()
            receipt = verify_reference_receipt(
                load_json(receipt_path),
                manifest_path,
            )
            print(
                "valid content-bound E0 receipt "
                f"{receipt['receipt_id']} (integrity and reproduction; not authorship)"
            )
            return 0

        if args.command == "products":
            ecosystem_registry = validate_registry(
                _load_registry(args.ecosystems, "ecosystems.json")
            )
            known_modules = {
                module["id"] for module in ecosystem_registry["modules"]
            }
            power_module_snapshot = validate_power_module_snapshot(
                _load_registry(args.power_modules, "power-modules.snapshot.json")
            )
            portfolio = validate_product_portfolio(
                _load_registry(args.registry, "products.json"),
                known_modules,
                power_module_snapshot,
            )
            if args.products_only and not args.json:
                raise ContractError("--products-only requires --json")
            if args.json:
                value = portfolio["products"] if args.products_only else portfolio
                print(json.dumps(value, indent=2, ensure_ascii=False))
            else:
                print(f"boundary: {portfolio['boundary']}")
                print(
                    "runtime: product validation is static; social, financial, "
                    "governance, and power-counterweight effects are unwired"
                )
                for product in portfolio["products"]:
                    print(
                        f"{product['id']:<24} {product['family']:<14} "
                        f"{product['design_stage']:<13} "
                        f"{product['implementation']['state']:<23} "
                        f"{product['name']}"
                    )
            return 0

        registry = validate_registry(_load_registry(args.registry, "ecosystems.json"))
        key = "ecosystems" if args.command == "ecosystems" else "modules"
        entries = registry[key]
        if args.json:
            print(json.dumps(entries, indent=2, ensure_ascii=False))
        elif key == "ecosystems":
            for entry in entries:
                print(
                    f"{entry['id']:<34} {entry['posture']:<16} "
                    f"value={entry['value_now']} openness={entry['openness']} "
                    f"lock-in={entry['lock_in_risk']}"
                )
        else:
            for entry in entries:
                print(
                    f"{entry['id']:<14} {entry['kind']:<10} "
                    f"{entry['status']:<10} {entry['name']}"
                )
        return 0
    except ContractError as exc:
        print(f"contract error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 3


def _load_registry(path: Path | None, default_name: str) -> dict[str, object]:
    if path is not None:
        return load_json(path.resolve())
    try:
        resource = (
            resources.files("kingdom_quantum_lab")
            .joinpath("data")
            .joinpath("registry")
            .joinpath(default_name)
        )
        value = json.loads(resource.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(
            f"cannot read packaged registry {default_name}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ContractError(f"packaged registry {default_name} root must be an object")
    return value


def _guard_output_path(
    output: Path,
    manifest: dict[str, object],
    manifest_path: Path,
) -> None:
    bundle = validate_reference_bundle(
        manifest,
        manifest_path,
        require_approved=True,
    )
    output_path = output.resolve(strict=False)
    protected = {
        manifest_path.resolve(),
        bundle["program_path"].resolve(),
        Path(__file__).resolve(),
        Path(__file__).with_name("contracts.py").resolve(),
        Path(__file__).with_name("simulator.py").resolve(),
    }
    if output_path in protected:
        raise ContractError("receipt output collides with an experiment or runner source")
    if os.path.lexists(output):
        raise ContractError("receipt output already exists; refusing to overwrite it")


def _write_new_atomic(output_path: Path, rendered: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, output_path, follow_symlinks=False)
        except FileExistsError as exc:
            raise ContractError(
                "receipt output already exists; refusing to overwrite it"
            ) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
