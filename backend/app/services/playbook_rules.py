"""Reglas deterministas del Dataset Playbook.

Solo usan metadata registrada. La compatibilidad técnica nunca depende del estado
local ni de permisos, y los permisos nunca se infieren: ``None`` significa no
determinado. Ninguna regla ordena datasets ni produce puntuaciones.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.schemas.canonical import Dataset, Language
from app.schemas.playbook import (
    Compatibility,
    LicenseSummary,
    LocalStatus,
    PlaybookTask,
    ProvenanceSummary,
    TaskAssessment,
    VarietySummary,
)

DISCLAIMER = (
    "El Playbook evalúa compatibilidad técnica mediante reglas sobre la metadata registrada. "
    "No es asesoría legal ni una valoración de calidad: la compatibilidad técnica no implica "
    "permiso de uso. Consulte las condiciones originales del proveedor."
)

DATA_REQUIREMENTS: dict[PlaybookTask, list[str]] = {
    PlaybookTask.MACHINE_TRANSLATION: [
        "Texto paralelo (modalidad parallel_text).",
        "Texto fuente y traducción alineados por registro.",
        "Idioma de la traducción identificado.",
    ],
    PlaybookTask.AUTOMATIC_SPEECH_RECOGNITION: [
        "Audio.",
        "Transcripción o texto asociado a cada clip.",
        "Idioma y variedad identificados.",
    ],
    PlaybookTask.SEMANTIC_SEARCH: [
        "Registros con texto.",
        "Copia local procesada e índice semántico para consultar.",
    ],
    PlaybookTask.CORPUS_EXPLORATION: [
        "Registros con texto.",
        "Copia local procesada para explorar registros.",
    ],
    PlaybookTask.LANGUAGE_MODELING: [
        "Corpus textual.",
        "Tamaño, dominio y calidad documentados para valorar si es suficiente.",
    ],
    PlaybookTask.LINGUISTIC_RESEARCH: [
        "Texto, audio o traducciones con procedencia documentada.",
        "Variedad y metadata de hablantes cuando la pregunta de investigación lo requiera.",
    ],
    PlaybookTask.EDUCATIONAL_USE: [
        "Texto, traducciones o audio.",
        "Condiciones de uso que permitan el uso educativo previsto.",
    ],
}

# Nombres con los que el Registry declara usos; la declaración es un indicio, no una regla.
DECLARED_TASK_NAMES: dict[PlaybookTask, str] = {
    PlaybookTask.MACHINE_TRANSLATION: "machine_translation",
    PlaybookTask.AUTOMATIC_SPEECH_RECOGNITION: "automatic_speech_recognition",
    PlaybookTask.SEMANTIC_SEARCH: "semantic_search",
    PlaybookTask.CORPUS_EXPLORATION: "corpus_exploration",
    PlaybookTask.LANGUAGE_MODELING: "language_modeling",
    PlaybookTask.LINGUISTIC_RESEARCH: "linguistic_research",
    PlaybookTask.EDUCATIONAL_USE: "education",
}

TRAINING_TASKS = frozenset(
    {
        PlaybookTask.MACHINE_TRANSLATION,
        PlaybookTask.AUTOMATIC_SPEECH_RECOGNITION,
        PlaybookTask.LANGUAGE_MODELING,
    }
)


def language_label(language: Language) -> str:
    return f"{language.name} ({language.iso_code})" if language.iso_code else language.name


def _count(value: float | int) -> str:
    return f"{value:,}".replace(",", " ")


def _permission(label: str, value: bool | None) -> str:
    if value is None:
        return f"{label}: no determinado con la información disponible."
    return f"{label}: {'sí' if value else 'no'}, según la metadata registrada."


@dataclass(frozen=True)
class DatasetFacts:
    """Hechos derivados exclusivamente de la metadata del dataset."""

    dataset: Dataset
    modalities: frozenset[str]
    declared_tasks: frozenset[str]
    metadata: dict[str, Any]
    variety: VarietySummary

    @property
    def modalities_known(self) -> bool:
        return bool(self.modalities)

    @property
    def has_parallel_text(self) -> bool:
        return "parallel_text" in self.modalities

    @property
    def has_text(self) -> bool:
        return bool(self.modalities & {"text", "parallel_text"})

    @property
    def has_audio(self) -> bool:
        return "audio" in self.modalities

    @property
    def license_known(self) -> bool:
        return bool(self.dataset.license.name)

    def declares(self, task: PlaybookTask) -> bool:
        return DECLARED_TASK_NAMES[task] in self.declared_tasks


def dataset_facts(dataset: Dataset) -> DatasetFacts:
    return DatasetFacts(
        dataset=dataset,
        modalities=frozenset(value.casefold() for value in dataset.modalities or []),
        declared_tasks=frozenset(value.casefold() for value in dataset.tasks or []),
        metadata=dict(dataset.metadata or {}),
        variety=variety_summary(dataset),
    )


# --- Contexto compartido -------------------------------------------------------------


def variety_summary(dataset: Dataset) -> VarietySummary:
    varieties = list(dataset.language_varieties or [])
    if not varieties:
        return VarietySummary(
            status="unspecified",
            varieties=[],
            note=(
                "Variedad no especificada en la metadata. No generalice los resultados "
                "a otras variedades de la lengua."
            ),
        )
    notes: list[str] = []
    partial = False
    for variety in varieties:
        language = next(
            (
                item.name
                for item in dataset.languages or []
                if variety.language_code and item.iso_code == variety.language_code
            ),
            "la lengua",
        )
        code = f" ({variety.id})" if variety.id else ""
        splits = (variety.metadata or {}).get("splits")
        if isinstance(splits, list) and splits:
            partial = True
            notes.append(
                f"La variedad {variety.name}{code} está documentada solo para: "
                f"{', '.join(str(split) for split in splits)}. La variedad del resto del corpus "
                f"no está especificada. No la atribuya a todo el corpus ni la generalice a "
                f"{language} en su conjunto."
            )
        else:
            notes.append(
                f"Variedad registrada: {variety.name}{code}. No generalice los resultados "
                f"a otras variedades de {language}."
            )
    return VarietySummary(
        status="partial" if partial else "specified", varieties=varieties, note=" ".join(notes)
    )


def license_summary(dataset: Dataset) -> LicenseSummary:
    license_info = dataset.license
    return LicenseSummary(
        known=bool(license_info.name),
        name=license_info.name,
        url=license_info.url,
        commercial_use=license_info.commercial_use,
        redistribution=license_info.redistribution,
        derivatives=license_info.derivatives,
        attribution_required=license_info.attribution_required,
        notes=license_info.notes,
    )


def provenance_summary(dataset: Dataset) -> ProvenanceSummary:
    documentation = (dataset.metadata or {}).get("documentation_url")
    return ProvenanceSummary(
        source_organization=dataset.source_organization or dataset.provenance.organization,
        source_url=dataset.source_url or dataset.provenance.source_url,
        documentation_url=documentation if isinstance(documentation, str) else None,
        citation=dataset.citation or dataset.provenance.citation,
        provenance=dataset.provenance,
    )


def _license_notes(facts: DatasetFacts, task: PlaybookTask) -> list[str]:
    license_info = facts.dataset.license
    notes = [
        f"Según la metadata registrada, la licencia es {license_info.name}."
        if license_info.name
        else "Según la metadata registrada, la licencia no está determinada; "
        "el permiso de uso no puede determinarse con la información disponible."
    ]
    if task in TRAINING_TASKS:
        notes.append(
            "La compatibilidad técnica no implica permiso: la metadata registrada no incluye "
            "una autorización explícita para entrenar modelos."
        )
        notes.append(_permission("Obras derivadas", license_info.derivatives))
        notes.append(_permission("Uso comercial", license_info.commercial_use))
    if task in {PlaybookTask.SEMANTIC_SEARCH, PlaybookTask.CORPUS_EXPLORATION}:
        notes.append(
            "El procesamiento local no redistribuye el corpus; los índices y artefactos "
            "derivados quedan sujetos a las mismas condiciones que el recurso."
        )
    if task is PlaybookTask.EDUCATIONAL_USE:
        notes.append(
            "La metadata registrada no autoriza expresamente usos educativos; no se asume ese permiso."
        )
        notes.append(_permission("Uso comercial", license_info.commercial_use))
    notes.append(_permission("Redistribución", license_info.redistribution))
    if facts.metadata.get("do_not_rehost") is True:
        notes.append(
            "La metadata registra que el recurso no debe volver a alojarse ni redistribuirse "
            "desde este proyecto; obténgalo de la fuente oficial."
        )
    if facts.metadata.get("do_not_attempt_speaker_identification") is True:
        notes.append("No intente identificar ni reidentificar a hablantes o contribuyentes.")
    if license_info.notes:
        notes.append(f"Nota registrada sobre la licencia: «{license_info.notes}»")
    notes.append("Consulte las condiciones originales del proveedor antes de reutilizar el recurso.")
    return notes


def _acquisition_steps(facts: DatasetFacts, local: LocalStatus) -> list[str]:
    if local.available_locally is True:
        return []
    steps = (
        ["Obtenga el recurso desde la fuente oficial y ejecute el pipeline de ingestión."]
        if local.available_locally is False
        else [
            "No se pudo determinar si existe una copia local procesada; para usar las "
            "herramientas locales, ingiera el recurso con el pipeline."
        ]
    )
    policy = facts.metadata.get("download_policy")
    if isinstance(policy, str) and policy.startswith("manual"):
        steps.append("La obtención es manual: esta plataforma no descarga ni aloja el corpus.")
    return steps


def _common_limitations(facts: DatasetFacts) -> list[str]:
    limitations = [facts.variety.note]
    if facts.metadata.get("synthetic") is True:
        limitations.append(
            "Datos sintéticos de desarrollo: no representan una lengua real ni sirven para "
            "valorar calidad lingüística."
        )
    return limitations


def _language_reason(facts: DatasetFacts) -> str | None:
    languages = facts.dataset.languages or []
    if not languages:
        return None
    return "Idiomas registrados: " + ", ".join(language_label(item) for item in languages) + "."


def _direction(facts: DatasetFacts) -> tuple[Language, Language] | None:
    direction = facts.metadata.get("canonical_direction")
    if not isinstance(direction, str) or "-to-" not in direction:
        return None
    source_code, target_code = direction.split("-to-", 1)
    by_code = {item.iso_code: item for item in facts.dataset.languages or [] if item.iso_code}
    if source_code in by_code and target_code in by_code:
        return by_code[source_code], by_code[target_code]
    return None


def _declared(facts: DatasetFacts, task: PlaybookTask, reasons: list[str]) -> None:
    if facts.declares(task):
        reasons.append("La fuente declara este uso en la metadata del Registry.")


# --- Reglas por tarea -------------------------------------------------------------------

Evaluation = tuple[Compatibility, list[str], list[str], list[str]]


def _unknown_modalities() -> Evaluation:
    return (
        "unknown",
        [],
        ["La metadata no registra modalidades; no puede determinarse la compatibilidad."],
        [],
    )


def _machine_translation(facts: DatasetFacts, local: LocalStatus) -> Evaluation:
    reasons: list[str] = []
    limitations: list[str] = []
    if facts.has_parallel_text:
        compatibility: Compatibility = "compatible"
        reasons.append("Contiene texto paralelo (modalidad parallel_text).")
        reasons.append(
            "El modelo canónico conserva cada par alineado como un registro con texto y traducción."
        )
        direction = _direction(facts)
        if direction:
            reasons.append(
                f"Dirección canónica registrada: {language_label(direction[0])} como texto fuente "
                f"→ {language_label(direction[1])} como traducción."
            )
        else:
            limitations.append("La dirección de traducción no está registrada en la metadata.")
    elif facts.declares(PlaybookTask.MACHINE_TRANSLATION):
        compatibility = "potential"
        limitations.append(
            "La fuente declara traducción automática, pero la modalidad parallel_text no está registrada."
        )
    else:
        return "not_applicable", [], ["No contiene texto paralelo registrado."], []
    _declared(facts, PlaybookTask.MACHINE_TRANSLATION, reasons)
    splits = facts.metadata.get("split_sources")
    if isinstance(splits, dict) and len(set(map(str, splits.values()))) > 1:
        detail = "; ".join(f"{split}: {source}" for split, source in splits.items())
        limitations.append(
            f"Los splits tienen orígenes distintos ({detail}). Manténgalos separados para "
            "evitar contaminación en la evaluación."
        )
    if facts.dataset.record_count is None:
        limitations.append("El número de pares no está registrado.")
    limitations.append("La alineación por registro no garantiza que cada traducción sea correcta.")
    return compatibility, reasons, limitations, _acquisition_steps(facts, local)


def _speech_recognition(facts: DatasetFacts, local: LocalStatus) -> Evaluation:
    reasons: list[str] = []
    limitations: list[str] = []
    if facts.has_audio and facts.has_text:
        compatibility: Compatibility = "compatible"
        reasons.append("Contiene audio.")
        reasons.append("Contiene texto (transcripciones) asociado al audio.")
    elif facts.has_audio:
        compatibility = "potential"
        reasons.append("Contiene audio.")
        limitations.append("No hay transcripciones registradas; ASR supervisado requiere texto.")
    elif facts.declares(PlaybookTask.AUTOMATIC_SPEECH_RECOGNITION):
        compatibility = "potential"
        limitations.append("La fuente declara ASR, pero la modalidad de audio no está registrada.")
    else:
        return "not_applicable", [], ["No contiene audio registrado."], []
    _declared(facts, PlaybookTask.AUTOMATIC_SPEECH_RECOGNITION, reasons)
    dataset = facts.dataset
    if dataset.audio_hours is not None:
        validated = facts.metadata.get("validated_audio_hours")
        extra = f" (validadas: {validated})" if isinstance(validated, (int, float)) else ""
        reasons.append(f"Horas de audio registradas: {dataset.audio_hours}{extra}.")
    else:
        limitations.append("Las horas de audio no están registradas.")
    if dataset.speaker_count is not None:
        reasons.append(f"Hablantes o contribuyentes registrados: {_count(dataset.speaker_count)}.")
    if facts.metadata.get("dataset_type") == "scripted_speech":
        limitations.append(
            "Habla leída (scripted speech): el comportamiento puede diferir con habla espontánea."
        )
    return compatibility, reasons, limitations, _acquisition_steps(facts, local)


def _semantic_search(facts: DatasetFacts, local: LocalStatus) -> Evaluation:
    if not facts.has_text:
        return "not_applicable", [], ["No contiene texto registrado para indexar."], []
    reasons = ["Contiene texto que puede indexarse con embeddings."]
    limitations = [
        "La calidad depende del modelo de embeddings, que no está evaluado para todas las "
        "lenguas y variedades indígenas."
    ]
    if facts.dataset.record_count is None:
        limitations.append("El número de registros no está registrado.")
    steps = _acquisition_steps(facts, local)
    if local.available_locally is True:
        if local.semantic_index == "available":
            reasons.append("Índice semántico local disponible.")
            steps.append("Use «Búsqueda semántica» en esta página.")
        elif local.semantic_index == "stale":
            steps.append("El índice semántico está desactualizado: reconstrúyalo.")
        else:
            steps.append("Construya el índice semántico para habilitar búsqueda por similitud.")
    return "compatible", reasons, limitations, steps


def _corpus_exploration(facts: DatasetFacts, local: LocalStatus) -> Evaluation:
    if not facts.has_text:
        return (
            "not_applicable",
            [],
            ["«Explorar registros» muestra texto y no hay texto registrado."],
            [],
        )
    reasons = ["Contiene texto consultable con «Explorar registros» y búsqueda textual."]
    steps = _acquisition_steps(facts, local)
    if local.available_locally is True:
        steps.append("Use «Explorar registros» en esta página.")
        if local.atlas == "available":
            reasons.append("El Atlas Vivo local está disponible para una vista 2D aproximada.")
        elif local.atlas == "stale":
            steps.append("El Atlas Vivo está desactualizado; reconstrúyalo si lo necesita.")
        elif local.semantic_index == "available":
            steps.append("Opcionalmente, construya el Atlas Vivo para una vista 2D del corpus.")
    return "compatible", reasons, [], steps


def _language_modeling(facts: DatasetFacts, local: LocalStatus) -> Evaluation:
    if not facts.has_text:
        return "not_applicable", [], ["No contiene texto registrado."], []
    reasons = ["Contiene texto que podría formar parte de un corpus de entrenamiento."]
    limitations: list[str] = []
    if facts.dataset.token_count is None:
        limitations.append(
            "El número de tokens no está registrado; no puede valorarse si el tamaño es suficiente."
        )
    else:
        reasons.append(f"Tokens registrados: {_count(facts.dataset.token_count)}.")
    if not facts.dataset.domains:
        limitations.append("Los dominios no están registrados; la representatividad es desconocida.")
    limitations.append("La calidad del texto no está documentada en la metadata.")
    if facts.metadata.get("dataset_type") == "scripted_speech":
        limitations.append(
            "El texto procede de oraciones leídas; puede no representar el uso espontáneo de la lengua."
        )
    _declared(facts, PlaybookTask.LANGUAGE_MODELING, reasons)
    return "potential", reasons, limitations, _acquisition_steps(facts, local)


def _linguistic_research(facts: DatasetFacts, local: LocalStatus) -> Evaluation:
    if not (facts.has_text or facts.has_audio):
        return (
            "unknown",
            [],
            ["No hay texto ni audio registrados para valorar su relevancia."],
            [],
        )
    reasons: list[str] = []
    if facts.has_text:
        reasons.append("Contiene texto.")
    if facts.has_parallel_text:
        reasons.append("Contiene traducciones alineadas.")
    if facts.has_audio:
        reasons.append("Contiene audio.")
    if facts.variety.status != "unspecified":
        reasons.append("Registra variedad lingüística (ver su alcance en limitaciones).")
    provenance = facts.dataset.provenance
    if provenance.source_url or facts.dataset.citation or provenance.citation:
        reasons.append("Documenta procedencia y cita.")
    if isinstance(facts.metadata.get("split_sources"), dict):
        reasons.append("Documenta la procedencia de cada split.")
    if facts.dataset.speaker_count is not None:
        reasons.append(
            f"Registra metadata de hablantes: {_count(facts.dataset.speaker_count)} "
            "hablantes o contribuyentes."
        )
    limitations = ["La relevancia depende de la pregunta de investigación."]
    if not facts.dataset.countries and not facts.dataset.regions:
        limitations.append("Países y regiones no están registrados.")
    _declared(facts, PlaybookTask.LINGUISTIC_RESEARCH, reasons)
    return "potential", reasons, limitations, _acquisition_steps(facts, local)


def _educational_use(facts: DatasetFacts, local: LocalStatus) -> Evaluation:
    if not (facts.has_text or facts.has_audio):
        return "unknown", [], ["No hay texto ni audio registrados."], []
    reasons: list[str] = []
    if facts.has_text:
        reasons.append("Contiene texto.")
    if facts.has_parallel_text:
        reasons.append("Contiene traducciones que pueden apoyar la comparación entre lenguas.")
    if facts.has_audio:
        reasons.append("Contiene audio.")
    limitations = [
        "La metadata no documenta revisión pedagógica ni adecuación del contenido para aula."
    ]
    _declared(facts, PlaybookTask.EDUCATIONAL_USE, reasons)
    return "potential", reasons, limitations, _acquisition_steps(facts, local)


RULES: dict[PlaybookTask, Callable[[DatasetFacts, LocalStatus], Evaluation]] = {
    PlaybookTask.MACHINE_TRANSLATION: _machine_translation,
    PlaybookTask.AUTOMATIC_SPEECH_RECOGNITION: _speech_recognition,
    PlaybookTask.SEMANTIC_SEARCH: _semantic_search,
    PlaybookTask.CORPUS_EXPLORATION: _corpus_exploration,
    PlaybookTask.LANGUAGE_MODELING: _language_modeling,
    PlaybookTask.LINGUISTIC_RESEARCH: _linguistic_research,
    PlaybookTask.EDUCATIONAL_USE: _educational_use,
}

UNKNOWN_LOCAL = LocalStatus(available_locally=None, semantic_index="unknown", atlas="unknown")


def assess_task(facts: DatasetFacts, task: PlaybookTask, local: LocalStatus) -> TaskAssessment:
    if not facts.modalities_known:
        compatibility, reasons, limitations, steps = _unknown_modalities()
    else:
        compatibility, reasons, limitations, steps = RULES[task](facts, local)
    applicable = compatibility != "not_applicable"
    if applicable:
        language = _language_reason(facts)
        if language:
            reasons.append(language)
        if task is not PlaybookTask.CORPUS_EXPLORATION:
            limitations.extend(_common_limitations(facts))
        if (
            task in TRAINING_TASKS | {PlaybookTask.EDUCATIONAL_USE}
            and not facts.license_known
        ):
            steps.append(
                "Verifique la licencia y las condiciones con el proveedor antes de reutilizar "
                "o redistribuir."
            )
    return TaskAssessment(
        task=task,
        compatibility=compatibility,
        reasons=reasons,
        limitations=limitations,
        license_notes=_license_notes(facts, task) if applicable else [],
        data_requirements=DATA_REQUIREMENTS[task],
        next_steps=list(dict.fromkeys(steps)),
    )


def assess_all(dataset: Dataset, local: LocalStatus) -> list[TaskAssessment]:
    facts = dataset_facts(dataset)
    return [assess_task(facts, task, local) for task in PlaybookTask]
