"""Export generated JSON Schemas into `contracts/`.

Only `datapack.schema.json` is generated: its source of truth is the pydantic
models in `apexfin.reporting.models`, and a hand-maintained copy would drift
away from them within a week. The other contract files (`sources`, `manifest`,
`expectations`) are hand-authored because they describe *input* config that has
no Python model to generate from, and because their descriptions are written
for the person editing the YAML.

Run `python tools/export_schemas.py` to write, `--check` to verify the checked-in
file is current. CI runs `--check`, so a model change with no regenerated schema
fails the build instead of silently shipping a frontend contract that no longer
matches what the backend emits.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:  # allow running without an editable install
    sys.path.insert(0, str(SRC))

from apexfin.reporting.models import DataPack  # noqa: E402

CONTRACTS = ROOT / "contracts"
DATAPACK_SCHEMA = CONTRACTS / "datapack.schema.json"

_HEADER = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://github.com/apexfin/apexfin/contracts/datapack.schema.json",
}


def datapack_schema() -> dict[str, object]:
    """The DataPack schema, with a stable `$id` prepended.

    `mode="serialization"` is not optional here: the dashboard consumes what
    `model_dump(mode="json")` produces, and the validation-mode schema would
    describe the inputs the model accepts instead of the output it emits.
    """
    schema = DataPack.model_json_schema(mode="serialization")
    return {**_HEADER, **schema}


def _rendered() -> str:
    return json.dumps(datapack_schema(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the checked-in schema differs from the models",
    )
    args = parser.parse_args()

    rendered = _rendered()
    if args.check:
        if not DATAPACK_SCHEMA.exists():
            print(f"missing {DATAPACK_SCHEMA.relative_to(ROOT)}; run tools/export_schemas.py")
            return 1
        if DATAPACK_SCHEMA.read_text(encoding="utf-8") != rendered:
            print(
                f"{DATAPACK_SCHEMA.relative_to(ROOT)} is out of date with "
                "apexfin.reporting.models; run tools/export_schemas.py"
            )
            return 1
        print(f"{DATAPACK_SCHEMA.relative_to(ROOT)} is current")
        return 0

    CONTRACTS.mkdir(parents=True, exist_ok=True)
    DATAPACK_SCHEMA.write_text(rendered, encoding="utf-8")
    print(f"wrote {DATAPACK_SCHEMA.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
