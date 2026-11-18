"""Generate reproducible Latin Hypercube inputs and stochastic ABM run manifests."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import scipy
from scipy.stats import qmc

DEFAULT_PARAMETERS = Path(__file__).resolve().parent / "data" / "parameters.csv"
PARAMETER_FIELDS = ("var", "range", "kind", "lower", "upper", "categories", "notes")
RESERVED_NAMES = {"sample_id", "run_id", "replicate", "model_seed"}


@dataclass(frozen=True)
class Parameter:
    """One input definition; numeric bounds are inclusive for integer inputs."""

    name: str
    kind: str
    lower: float | None = None
    upper: float | None = None
    categories: tuple[str, ...] = ()
    source_range: str = ""
    notes: str = ""


def _validate_parameters(parameters: Sequence[Parameter]) -> None:
    names = set()
    for p in parameters:
        if not p.name.strip() or p.name in RESERVED_NAMES or p.name in names:
            raise ValueError(f"Empty, reserved, or duplicate parameter name: {p.name!r}")
        names.add(p.name)
        if p.kind in {"continuous", "integer"}:
            if (p.lower is None or p.upper is None
                    or not np.isfinite([p.lower, p.upper]).all()
                    or p.lower >= p.upper or not np.isfinite(p.upper - p.lower)):
                raise ValueError(f"{p.name}: need finite lower < upper bounds")
            if p.categories:
                raise ValueError(f"{p.name}: numeric parameters cannot have categories")
            if p.kind == "integer":
                if not float(p.lower).is_integer() or not float(p.upper).is_integer():
                    raise ValueError(f"{p.name}: integer bounds must be whole numbers")
                # Mapping uses float64; keep all integer bin edges exactly representable.
                if max(abs(p.lower), abs(p.upper), p.upper - p.lower + 1) > 2**53 - 1:
                    raise ValueError(f"{p.name}: integer bounds exceed float64 precision")
        elif p.kind == "categorical":
            if (not p.categories or any(not c.strip() for c in p.categories)
                    or len(set(p.categories)) != len(p.categories)):
                raise ValueError(f"{p.name}: categories must be nonempty and unique")
            if p.lower is not None or p.upper is not None:
                raise ValueError(f"{p.name}: categorical parameters cannot have bounds")
        elif p.kind == "excluded":
            if p.lower is not None or p.upper is not None or p.categories:
                raise ValueError(f"{p.name}: excluded parameters cannot have bounds or categories")
        else:
            raise ValueError(f"{p.name}: unknown kind {p.kind!r}")
    if not any(p.kind != "excluded" for p in parameters):
        raise ValueError("At least one parameter must be sampled")


def load_parameters(path: str | Path = DEFAULT_PARAMETERS) -> list[Parameter]:
    """Read and validate the CSV specification, preserving excluded rows and order."""
    parameters = []
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if (len(reader.fieldnames or []) != len(PARAMETER_FIELDS)
                or set(reader.fieldnames or []) != set(PARAMETER_FIELDS)):
            raise ValueError(f"Parameter CSV must have columns: {', '.join(PARAMETER_FIELDS)}")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Line {reader.line_num}: incorrect number of fields")
            row = {key: value.strip() for key, value in row.items()}
            try:
                parameters.append(Parameter(
                    name=row["var"], kind=row["kind"],
                    lower=float(row["lower"]) if row["lower"] else None,
                    upper=float(row["upper"]) if row["upper"] else None,
                    categories=tuple(c.strip() for c in row["categories"].split("|"))
                    if row["categories"] else (),
                    source_range=row["range"], notes=row["notes"],
                ))
            except ValueError as exc:
                raise ValueError(f"Line {reader.line_num}: {exc}") from exc
    _validate_parameters(parameters)
    return parameters


def _check_integer(name: str, value: int, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def sample_lhs(
    parameters: Sequence[Parameter], samples: int = 256, seed: int = 42,
) -> tuple[list[dict], np.ndarray]:
    """Return typed scenario rows and their unit-cube coordinates.

    All active marginals are uniform and sampled independently. Discrete values
    use inverse CDF mapping, so stratification applies before discretization.
    """
    _validate_parameters(parameters)
    _check_integer("samples", samples, 1)
    _check_integer("seed", seed, 0)
    samples, seed = int(samples), int(seed)
    active = [p for p in parameters if p.kind != "excluded"]
    design_seed = np.random.SeedSequence(seed).spawn(2)[0]
    unit = qmc.LatinHypercube(
        d=len(active), scramble=True, strength=1, optimization=None,
        rng=np.random.default_rng(design_seed),
    ).random(n=samples)
    rows = [{"sample_id": i + 1} for i in range(samples)]
    for j, p in enumerate(active):
        for i, u in enumerate(unit[:, j]):
            if p.kind == "continuous":
                value = float(p.lower + u * (p.upper - p.lower))
            elif p.kind == "integer":
                width = int(p.upper) - int(p.lower) + 1
                value = int(p.lower) + min(int(u * width), width - 1)
            else:
                value = p.categories[min(int(u * len(p.categories)), len(p.categories) - 1)]
            rows[i][p.name] = value
    return rows, unit


def _write_csv(path: Path, fieldnames: Sequence[str], rows) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def create_experiment(
    parameters_path: str | Path,
    output_dir: str | Path,
    samples: int = 256,
    seed: int = 42,
    replicates: int = 5,
) -> dict:
    """Write a design, replicate inputs, latent samples, and reproducibility metadata.

    The output directory must not already exist. Model seeds are unique within
    this experiment and use a random stream separate from the sampling stream.
    """
    _check_integer("replicates", replicates, 1)
    _check_integer("samples", samples, 1)
    _check_integer("seed", seed, 0)
    samples, seed, replicates = int(samples), int(seed), int(replicates)
    total_runs = samples * replicates
    if total_runs > 2**31:
        raise ValueError("samples * replicates must not exceed the model seed space (2**31)")
    parameters_path, output_dir = Path(parameters_path), Path(output_dir)
    parameters = load_parameters(parameters_path)
    rows, unit = sample_lhs(parameters, samples, seed)
    names = [p.name for p in parameters if p.kind != "excluded"]
    run_seed = np.random.SeedSequence(seed).spawn(2)[1]
    model_seeds = np.random.default_rng(run_seed).choice(2**31, size=total_runs, replace=False)
    metadata = {
        "samples": samples, "dimensions": len(names), "replicates": replicates,
        "total_runs": total_runs, "seed": seed,
        "sampler": "scipy.stats.qmc.LatinHypercube",
        "settings": {"scramble": True, "strength": 1, "optimization": None},
        "marginals": "uniform continuous; discrete uniform integers and categories",
        "parameter_order": names,
        "excluded_parameters": [p.name for p in parameters if p.kind == "excluded"],
        "seed_streams": {"design": 0, "model_runs": 1},
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "scipy": scipy.__version__},
        "parameter_sha256": hashlib.sha256(parameters_path.read_bytes()).hexdigest(),
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "parameters.csv").write_bytes(parameters_path.read_bytes())
    _write_csv(output_dir / "design.csv", ["sample_id", *names], rows)
    unit_rows = (
        {"sample_id": i + 1, **dict(zip(names, point))} for i, point in enumerate(unit)
    )
    _write_csv(output_dir / "unit_samples.csv", ["sample_id", *names], unit_rows)
    run_rows = (
        {"run_id": i * replicates + r + 1, "replicate": r + 1,
         "model_seed": int(model_seeds[i * replicates + r]), **row}
        for i, row in enumerate(rows) for r in range(replicates)
    )
    _write_csv(output_dir / "runs.csv", ["run_id", "sample_id", "replicate", "model_seed", *names], run_rows)
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8",
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameters", type=Path, default=DEFAULT_PARAMETERS)
    parser.add_argument("--output", type=Path, default=Path("outputs/lhs_256"))
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--replicates", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        metadata = create_experiment(args.parameters, args.output, args.samples, args.seed, args.replicates)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(f"Created {metadata['samples']} configurations across {metadata['dimensions']} parameters "
          f"and {metadata['total_runs']} model runs in {args.output}")


if __name__ == "__main__":
    main()
