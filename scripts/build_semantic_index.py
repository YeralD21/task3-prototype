"""CLI para construir un índice semántico local con Sentence Transformers."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "backend"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from app.config import get_settings  # noqa: E402
from app.embeddings.sentence_transformer_provider import (  # noqa: E402
    SentenceTransformerProvider,
)
from ml.embeddings.indexer import SemanticIndexer  # noqa: E402


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Build a local semantic index.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--processed-root", type=Path, default=settings.dataset_processed_path)
    parser.add_argument("--model", default=settings.embedding_model_name)
    args = parser.parse_args()
    try:
        result = SemanticIndexer(SentenceTransformerProvider(args.model)).build(
            args.dataset, args.processed_root
        )
    except Exception as error:
        parser.exit(1, f"Semantic indexing failed: {error}\n")
    print(f"Dataset: {result.dataset_id}")
    print(f"Destination: {result.destination}")
    print(f"Records: {result.record_count}")
    print(f"Dimension: {result.dimension}")
    print(f"Fingerprint: {result.fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
