"""Ejecuta manualmente el benchmark técnico con modelos reales o fake."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "backend"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from app.embeddings.provider import FakeEmbeddingProvider  # noqa: E402
from app.embeddings.sentence_transformer_provider import SentenceTransformerProvider  # noqa: E402
from ml.embeddings.evaluation import evaluate_provider, load_benchmark  # noqa: E402

DEFAULT_BENCHMARK = PROJECT_ROOT / "datasets/evaluation/synthetic-semantic-benchmark.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate embedding models locally.")
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument(
        "--fake", action="store_true", help="Use deterministic fake providers; tests only."
    )
    args = parser.parse_args()
    benchmark = load_benchmark(args.benchmark)
    serialized: list[dict[str, object]] = []
    for model_name in args.models:
        if args.fake:
            provider = FakeEmbeddingProvider(dimension=64, model_name=model_name)
            load_seconds = 0.0
        else:
            provider = SentenceTransformerProvider(model_name)
            load_start = perf_counter()
            provider.load()
            load_seconds = perf_counter() - load_start
        result = evaluate_provider(provider, benchmark, k=args.k, load_seconds=load_seconds)
        serialized.append(asdict(result))
        print(f"\n{result.model_name}")
        print(f"Dimension: {result.dimension}")
        print(f"Precision@{result.k}: {result.precision_at_k:.4f}")
        print(f"Recall@{result.k}: {result.recall_at_k:.4f}")
        print(f"MRR: {result.mrr:.4f}")
        print(f"Load: {result.load_seconds:.3f}s")
        print(f"Embeddings: {result.embedding_seconds:.3f}s")
        print(f"Search: {result.search_seconds:.6f}s")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(serialized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
