"""Métricas y benchmark técnico sin modelos ni conexiones de red."""

import socket
from pathlib import Path

import numpy as np
import pytest

from app.embeddings.provider import FakeEmbeddingProvider
from ml.embeddings.evaluation import (
    BenchmarkValidationError,
    evaluate_provider,
    load_benchmark,
    precision_at_k,
    rank_records,
    recall_at_k,
    reciprocal_rank,
)
from scripts.evaluate_embedding_models import main
from tests.conftest import PROJECT_ROOT

BENCHMARK = PROJECT_ROOT / "datasets/evaluation/synthetic-semantic-benchmark.json"


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access forbidden in embedding evaluation tests")

    monkeypatch.setattr(socket, "create_connection", reject)


def test_precision_at_k() -> None:
    assert precision_at_k(["a", "x", "b", "y"], frozenset({"a", "b"}), 4) == 0.5


def test_recall_at_k() -> None:
    assert recall_at_k(["a", "x", "b"], frozenset({"a", "b", "c"}), 2) == pytest.approx(1 / 3)


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(["x", "y", "a"], frozenset({"a", "b"})) == pytest.approx(1 / 3)
    assert reciprocal_rank(["x"], frozenset({"a"})) == 0.0


def test_ranking_uses_descending_cosine_and_stable_ties() -> None:
    vectors = np.asarray([[1, 0], [0, 1], [1, 0]], dtype=np.float32)
    assert rank_records(vectors, np.asarray([1, 0]), ["first", "other", "second"]) == [
        "first", "second", "other"
    ]


def test_benchmark_loader_and_ground_truth() -> None:
    benchmark = load_benchmark(BENCHMARK)
    assert benchmark.name == "synthetic-semantic-development-v1"
    assert len(benchmark.records) == 24
    assert len(benchmark.queries) == 8
    topics = {record.topic for record in benchmark.records}
    assert topics == {"agriculture", "family", "education", "health", "nature", "commerce", "travel", "food"}
    assert all(len(query.relevant_record_ids) == 3 for query in benchmark.queries)
    assert benchmark.queries[0].relevant_record_ids == frozenset(
        {"agriculture-1", "agriculture-2", "agriculture-3"}
    )


def test_loader_rejects_unknown_ground_truth(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text(
        '{"name":"x","synthetic":true,"records":[{"id":"r","text":"x","topic":"x"}],'
        '"queries":[{"id":"q","text":"x","relevant_record_ids":["missing"]}]}',
        encoding="utf-8",
    )
    with pytest.raises(BenchmarkValidationError, match="Ground truth"):
        load_benchmark(invalid)


def test_fake_evaluation_is_reproducible() -> None:
    benchmark = load_benchmark(BENCHMARK)
    first = evaluate_provider(FakeEmbeddingProvider(dimension=64), benchmark)
    second = evaluate_provider(FakeEmbeddingProvider(dimension=64), benchmark)
    assert (first.precision_at_k, first.recall_at_k, first.mrr, first.dimension) == (
        second.precision_at_k, second.recall_at_k, second.mrr, second.dimension
    )


def test_cli_executes_with_fake_provider(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "sys.argv", ["evaluate_embedding_models.py", "--models", "fake-test", "--fake"]
    )
    assert main() == 0
    output = capsys.readouterr().out
    assert "fake-test" in output
    assert "Precision@5" in output
    assert "MRR" in output
