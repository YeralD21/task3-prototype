"""CLI para proyectar un índice semántico local a coordenadas 2D (Atlas Vivo).

Reutiliza embeddings.npy; no recalcula embeddings ni carga modelos de lenguaje.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "backend"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from app.config import get_settings  # noqa: E402
from ml.atlas.builder import AtlasBuilder  # noqa: E402
from ml.atlas.reducers import REDUCERS, create_reducer  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Build a local 2-D atlas from a semantic index.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--processed-root", type=Path, default=settings.dataset_processed_path)
    parser.add_argument("--reducer", choices=sorted(REDUCERS), default="pca")
    parser.add_argument("--random-state", type=int, default=42, help="UMAP only.")
    parser.add_argument("--n-neighbors", type=int, default=15, help="UMAP only.")
    parser.add_argument("--min-dist", type=float, default=0.1, help="UMAP only.")
    args = parser.parse_args(argv)
    options = (
        {
            "random_state": args.random_state,
            "n_neighbors": args.n_neighbors,
            "min_dist": args.min_dist,
        }
        if args.reducer == "umap"
        else {}
    )
    try:
        result = AtlasBuilder(create_reducer(args.reducer, **options)).build(
            args.dataset, args.processed_root
        )
    except Exception as error:
        parser.exit(1, f"Atlas build failed: {error}\n")
    print(f"Dataset: {result.dataset_id}")
    print(f"Destination: {result.destination}")
    print(f"Reducer: {result.reducer}")
    print(f"Records: {result.record_count}")
    print(f"Records fingerprint: {result.source_records_fingerprint}")
    print(f"Semantic index fingerprint: {result.semantic_index_fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
