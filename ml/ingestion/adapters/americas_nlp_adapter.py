"""Local AmericasNLP 2021 Aymara-Spanish reader; no downloads or normalization."""

from itertools import zip_longest
from pathlib import Path

from pydantic import ValidationError

from app.schemas.canonical import CorpusRecord, Dataset, Language
from ml.ingestion.base_adapter import CorpusAdapter

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = PROJECT_ROOT / "datasets/registry/aymara/americasnlp-aymara-spanish.json"


class AmericasNLPAdapterError(ValueError):
    """Missing, unreadable or unaligned local source; includes actionable context."""


class AmericasNLPAdapter(CorpusAdapter):
    """Read UTF-8 .aym/.es files aligned by line, without headers or columns.

    The directory holds manually obtained split.aym and split.es files.
    Select splits explicitly; the default reads train only. Fixture mode must
    be explicitly enabled and labels every derived record as development data.
    """

    def __init__(
        self,
        dataset_directory: Path,
        *,
        splits: tuple[str, ...] = ("train",),
        manifest_path: Path = MANIFEST_PATH,
        synthetic: bool = False,
    ) -> None:
        if not splits or len(set(splits)) != len(splits):
            raise AmericasNLPAdapterError("Select distinct, non-empty splits.")
        if any(split not in {"train", "dev", "test"} for split in splits):
            raise AmericasNLPAdapterError("Supported splits: train, dev, test.")
        self.dataset_directory = Path(dataset_directory)
        self.splits = splits
        self.manifest_path = Path(manifest_path)
        self.synthetic = synthetic

    def load_metadata(self) -> Dataset:
        """Read the catalog independently of the presence of a local corpus."""
        try:
            return Dataset.model_validate_json(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValidationError) as error:
            raise AmericasNLPAdapterError(
                f"Cannot read AmericasNLP manifest: {self.manifest_path}"
            ) from error

    def load_records(self) -> list[CorpusRecord]:
        """Return complete aligned pairs, or raise without returning partial data."""
        dataset = self.load_metadata()
        records: list[CorpusRecord] = []
        for split in self.splits:
            aym_path = self.dataset_directory / f"{split}.aym"
            es_path = self.dataset_directory / f"{split}.es"
            for path in (aym_path, es_path):
                if not path.is_file():
                    raise AmericasNLPAdapterError(
                        f"Missing file: {path}. Place the manually obtained paired "
                        f"{split}.aym and {split}.es files in {self.dataset_directory}."
                    )
            try:
                with aym_path.open(encoding="utf-8", newline="") as aym_file, es_path.open(
                    encoding="utf-8", newline=""
                ) as es_file:
                    for line_number, (aym, es) in enumerate(
                        zip_longest(aym_file, es_file), start=1
                    ):
                        if aym is None or es is None:
                            raise AmericasNLPAdapterError(
                                f"Unaligned {split} files at line {line_number}: different lengths."
                            )
                        # Only remove physical line terminators, not source whitespace.
                        text, translation = aym.rstrip("\r\n"), es.rstrip("\r\n")
                        if not text.strip() or not translation.strip():
                            raise AmericasNLPAdapterError(
                                f"Empty parallel text in {split} at line {line_number}."
                            )
                        source_id = f"{split}.aym:{line_number}"
                        upstream = (
                            "Global Voices via OPUS" if split == "train"
                            else "AmericasNLI: translations of Spanish XNLI"
                        )
                        provenance = dataset.provenance.model_copy(deep=True)
                        provenance.notes = (
                            f"AmericasNLP 2021; {upstream}; paired files "
                            f"{split}.aym / {split}.es; line {line_number}."
                        )
                        metadata = {
                            "split": split,
                            "source_file": aym_path.name,
                            "translation_file": es_path.name,
                            "line_number": line_number,
                            "original_source": upstream,
                            "source_record_id_kind": "derived_file_line_reference",
                        }
                        if self.synthetic:
                            metadata.update(synthetic=True, development_only=True)
                            provenance.notes = (
                                "Synthetic development_only fixture imitating AmericasNLP; "
                                "not a sentence supplied by the original provider. "
                                f"{split}.aym / {split}.es; line {line_number}."
                            )
                        variety = next(
                            (v for v in dataset.language_varieties or []
                             if split in (v.metadata or {}).get("splits", [])),
                            None,
                        )
                        records.append(CorpusRecord(
                            id=f"{dataset.id}:{source_id}",
                            dataset_id=dataset.id,
                            source_record_id=source_id,
                            language=Language(name="Aymara", iso_code="aym"),
                            language_code="aym",
                            language_variety=variety,
                            text=text,
                            translation=translation,
                            translation_language=Language(name="Spanish", iso_code="es"),
                            provenance=provenance,
                            metadata=metadata,
                        ))
            except (OSError, UnicodeError) as error:
                raise AmericasNLPAdapterError(
                    f"Cannot read UTF-8 parallel files for {split} in {self.dataset_directory}."
                ) from error
        return records
