"""CLI liviana para materializar un corpus local autorizado."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from ml.ingestion.adapter_registry import ADAPTERS  # noqa: E402
from ml.ingestion.pipeline import ingest_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize an authorized local corpus without changing its source."
    )
    parser.add_argument("--adapter", required=True, choices=sorted(ADAPTERS))
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        result = ingest_dataset(args.adapter, args.source, args.output)
    except Exception as error:
        parser.exit(1, f"Ingestion failed: {error}\n")

    print(f"Dataset: {result.dataset_id}")
    print(f"Destination: {result.destination}")
    print(f"Records: {result.record_count}")
    print(f"Audio resources: {result.audio_resource_count}")
    print(f"Speakers: {result.speaker_count}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
