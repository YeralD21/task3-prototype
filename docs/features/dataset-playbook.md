# Dataset Playbook

El Playbook responde dos preguntas:

- **¿Para qué puedo utilizar este dataset?** Con `GET /api/v1/datasets/{dataset_id}/playbook` y la sección «Playbook» del detalle del dataset.
- **¿Qué dataset podría servirme para una tarea concreta?** Con `GET /api/v1/playbook/datasets?task=<tarea>`.

Funciona con **reglas deterministas y explicables sobre la metadata registrada**. No usa LLM, embeddings, modelos ni red. No asigna puntuaciones, no ordena de mejor a peor y no afirma que un dataset sea «el mejor». Cada conclusión va acompañada de las razones que la producen.

> El Playbook **no es asesoría legal**. Sus textos usan fórmulas como «según la metadata registrada» y «el permiso no puede determinarse con la información disponible». Consulte siempre las condiciones originales del proveedor.

## Compatibilidad técnica frente a permiso de uso

Son dos ejes separados que nunca se mezclan:

| Eje | Dónde aparece | Qué responde |
|---|---|---|
| Compatibilidad técnica | `compatibility`, `reasons`, `limitations` | ¿Los datos registrados tienen la forma que la tarea necesita? |
| Permiso / condiciones | `license`, `license_notes` | ¿Qué dice la metadata registrada sobre licencia, redistribución, uso comercial, obras derivadas y condiciones del proveedor? |

Un dataset puede ser técnicamente compatible con traducción automática y, al mismo tiempo, tener una licencia no determinada. Así ocurre con AmericasNLP.

- La compatibilidad **nunca** depende de la licencia.
- La licencia **nunca** se deduce de la compatibilidad.
- En las tareas que implican entrenar modelos (MT, ASR, modelado del lenguaje), el Playbook indica siempre que la metadata registrada no incluye una autorización explícita para entrenar. Nunca afirma que el recurso «puede utilizarse para entrenamiento».

### Permisos: `null` es «No determinado»

`LicenseInfo` usa `bool | None`, y el Playbook conserva esos valores tal cual:

- `null` → «No determinado» (API: `null`; interfaz: «No determinado»). **Nunca se convierte en `false` ni en `true`.**
- `true` / `false` → «Sí» / «No», siempre acompañado de «según la metadata registrada».

La licencia se considera conocida (`license.known`) solo si tiene nombre. Las marcas del manifiesto `do_not_rehost` y `do_not_attempt_speaker_identification` se convierten en notas explícitas. La nota de licencia registrada se cita textualmente, sin interpretarla.

## Estados

| Estado | Significado | Interfaz |
|---|---|---|
| `compatible` | La metadata registrada cubre los requisitos técnicos | ✓ Compatible (borde continuo) |
| `potential` | Podría servir, pero faltan datos o condiciones por confirmar | ◐ Potencial (borde discontinuo) |
| `not_applicable` | Los datos registrados no cubren los requisitos | — No aplicable (borde punteado) |
| `unknown` | La metadata no permite decidir (p. ej., sin modalidades) | ? Desconocido (borde doble) |

La interfaz siempre muestra el estado como texto y símbolo, no solo con color. Los lectores de pantalla oyen «Compatibilidad técnica: …».

## Reglas

Todas las reglas están en `backend/app/services/playbook_rules.py`. Parten de `modalities`, `tasks`, `languages`, `language_varieties`, `license`, `provenance`, los conteos y la `metadata` del dataset. Si no hay modalidades registradas, todas las tareas quedan como `unknown`.

| Tarea | `compatible` | `potential` | `not_applicable` |
|---|---|---|---|
| `machine_translation` | `parallel_text` | declara MT sin `parallel_text` | sin texto paralelo |
| `automatic_speech_recognition` | `audio` + texto | audio sin texto, o declara ASR sin audio | sin audio |
| `semantic_search` | hay texto | — | sin texto |
| `corpus_exploration` | hay texto | — | sin texto |
| `language_modeling` | — (nunca se afirma) | hay texto | sin texto |
| `linguistic_research` | — (depende de la pregunta) | texto o audio | — (`unknown` si no hay ninguno) |
| `educational_use` | — (no hay permiso educativo registrado) | texto, traducción o audio | — (`unknown` si no hay ninguno) |

Si el Registry declara una tarea en `tasks`, eso se muestra como razón, pero no basta por sí solo para que la tarea sea `compatible`.

Además, según la tarea:

- **MT:** indica la dirección canónica si `metadata.canonical_direction` coincide con los idiomas registrados (AmericasNLP: `aym → es`). Advierte si los splits tienen orígenes distintos (`split_sources`), si no se registra el número de pares y que la alineación no garantiza traducciones correctas.
- **ASR:** muestra las horas de audio (y las validadas), los hablantes registrados y la advertencia de habla leída si `dataset_type = scripted_speech`.
- **Búsqueda semántica:** advierte que el modelo de embeddings no está evaluado para todas las lenguas y variedades.
- **Modelado del lenguaje:** advierte si faltan tokens, dominios o calidad documentada, y si el texto procede de oraciones leídas.
- **Investigación lingüística:** enumera la evidencia disponible (texto, traducciones, audio, variedad, procedencia por split, metadata de hablantes).
- **Uso educativo:** nunca afirma autorización educativa y advierte que no hay revisión pedagógica documentada.

Las tareas `not_applicable` no incluyen notas de licencia ni pasos siguientes.

### Pasos siguientes

También son reglas; nunca se generan comandos con datos externos:

- sin copia local (`available_locally: false`) → «Obtenga el recurso desde la fuente oficial y ejecute el pipeline de ingestión.» Si `download_policy` es manual, se añade que la plataforma no descarga ni aloja el corpus;
- disponibilidad no determinada (`null`) → se indica explícitamente, sin tratarla como `false`;
- copia local sin índice semántico → «Construya el índice semántico para habilitar búsqueda por similitud.»; con índice desactualizado → reconstruirlo; con índice disponible → usar «Búsqueda semántica»;
- exploración del corpus con copia local → usar «Explorar registros»; el Atlas se sugiere **solo como opción**;
- licencia desconocida en MT/ASR/LM/educación → verificar licencia y condiciones con el proveedor.

## Estado local

`local.available_locally` repite `metadata.available_locally` (`true`, `false` o `null`). Solo si es `true` se revisan los artefactos. La comprobación reutiliza los fingerprints SHA-256 existentes, no carga matrices y no depende de que el Atlas exista:

- `semantic_index`: `available` si los archivos existen y el fingerprint de `records.jsonl` coincide; `stale` si no coincide; `missing` si faltan archivos;
- `atlas`: igual, y además comprueba el fingerprint del índice semántico;
- `unknown` si no hay copia local o no se pudo leer.

El estado local **no cambia la compatibilidad técnica**, solo las razones y los pasos siguientes. El endpoint de descubrimiento no inspecciona artefactos.

## Procedencia

Cada Playbook incluye `provenance`: quién publica (`source_organization`), la URL de la fuente, la documentación (`metadata.documentation_url`), la cita y el `ProvenanceInfo` completo (nombre de la fuente, identificador original, notas). La interfaz lo muestra junto a las tarjetas, no detrás de ellas.

## Variedades

- `specified`: se muestra la variedad registrada y se advierte que no debe generalizarse (Common Voice: «Puno Quechua / Punu qhichwa (qxp). No generalice los resultados a otras variedades de Quechua.»).
- `partial`: una variedad está limitada a ciertos splits (`metadata.splits`). En AmericasNLP, Central Aymara (`ayr`) está documentada solo para dev/test; el Playbook indica que la variedad del resto del corpus no está especificada y que no debe atribuirse a todo el corpus ni generalizarse a Aymara en su conjunto.
- `unspecified`: «Variedad no especificada».

La nota de variedad aparece como limitación en todas las tareas aplicables salvo la exploración del corpus.

## API

### Por dataset

```http
GET /api/v1/datasets/{dataset_id}/playbook
```

```json
{
  "dataset_id": "americasnlp-2021-aymara-spanish",
  "dataset_name": "AmericasNLP 2021 - Aymara-Spanish",
  "languages": [{"name": "Aymara", "iso_code": "aym"}, {"name": "Spanish", "iso_code": "es"}],
  "variety": {"status": "partial", "varieties": [{"id": "ayr", "...": "..."}], "note": "..."},
  "license": {"known": false, "name": null, "url": null, "commercial_use": null,
              "redistribution": null, "derivatives": null, "attribution_required": null, "notes": "..."},
  "provenance": {"source_organization": "...", "source_url": "...", "documentation_url": "...",
                 "citation": "...", "provenance": {"...": "..."}},
  "local": {"available_locally": false, "semantic_index": "unknown", "atlas": "unknown"},
  "tasks": [{
    "task": "machine_translation",
    "compatibility": "compatible",
    "reasons": ["Contiene texto paralelo (modalidad parallel_text).", "..."],
    "limitations": ["Los splits tienen orígenes distintos (...)", "..."],
    "license_notes": ["Según la metadata registrada, la licencia no está determinada; ...", "..."],
    "data_requirements": ["Texto paralelo (modalidad parallel_text).", "..."],
    "next_steps": ["Obtenga el recurso desde la fuente oficial y ejecute el pipeline de ingestión.", "..."]
  }],
  "disclaimer": "El Playbook evalúa compatibilidad técnica ... No es asesoría legal ..."
}
```

`tasks` contiene siempre las 7 tareas en orden fijo. Si el dataset no existe, responde `404`; si el Registry no se puede leer, `500` con un mensaje genérico.

### Por tarea

```http
GET /api/v1/playbook/datasets?task=machine_translation
```

Devuelve `compatible`, `potential` y `unknown` como listas, y `not_applicable_count`. Cada elemento incluye `dataset_id`, `dataset_name`, `compatibility`, `reasons`, `limitations`, `available_locally` y `license_known`. **Dentro de cada grupo el orden es alfabético por `dataset_id` (`ordering: "dataset_id"`)**: no es un ranking y no hay puntuaciones. Una tarea desconocida o ausente devuelve `422`.

## Interfaz

En `/datasets/[id]`, después de «Atlas Vivo», la sección **Playbook** carga la evaluación al abrir la página (es una consulta ligera de metadata). Muestra:

1. el aviso de alcance (no es asesoría legal);
2. el contexto común: licencia registrada con los cuatro permisos («No determinado» cuando son `null`), idioma y variedad con su alcance, procedencia con enlaces seguros y estado en esta instalación;
3. una tarjeta por tarea con su estado, «¿Por qué?», «Limitaciones», «Licencia y uso», «Siguiente paso» y los requisitos de datos (plegables).

Estados: carga (`aria-busy`), dataset inexistente («no figura en el catálogo») y error genérico con «Reintentar». Nunca se muestran detalles técnicos crudos. En pantallas estrechas, las tarjetas pasan a una columna.

El descubrimiento global en el catálogo («Uso previsto») **no se implementó en la interfaz**. El endpoint y `getPlaybookDatasets(task)` están disponibles para una iteración posterior. El filtro existente «Uso potencial» sigue usando las tareas declaradas en el Registry.

## Ejemplos

| | AmericasNLP Aymara–Español | Common Voice Puno Quechua |
|---|---|---|
| MT | Compatible | No aplicable |
| ASR | No aplicable | Compatible |
| Búsqueda semántica / Exploración | Compatible | Compatible (sobre transcripciones) |
| Modelado del lenguaje / Investigación / Educación | Potencial | Potencial |
| Licencia | No determinada; los 4 permisos «No determinado» | CC0-1.0; redistribución **No** y marcas de no re-alojar y no reidentificar |
| Variedad | Parcial: `ayr` solo dev/test | Registrada: Puno Quechua (`qxp`) |

## Pruebas

`backend/tests/test_playbook.py` (23 pruebas, red bloqueada) y `frontend/tests/playbook.test.ts` (11 pruebas) cubren: compatibilidad por tarea, licencias y permisos nulos, separación técnico/legal, variedades, procedencia, estado local (ausente, disponible y desactualizado), independencia entre compatibilidad y estado local, determinismo, endpoints, descubrimiento sin ranking e independiente del orden del catálogo, tareas inválidas, render, estados y ausencia de `any`.

## Limitaciones

- Las reglas son tan buenas como la metadata registrada: si un manifiesto se equivoca, el Playbook también. No inspecciona los registros.
- «Texto» en un dataset de audio se interpreta como transcripciones, porque así lo modela el esquema canónico.
- No valora la calidad, el tamaño suficiente ni la representatividad; solo advierte cuando faltan datos.
- No hay campos para permisos de entrenamiento o uso educativo. Por eso nunca se afirman.
- Los textos están en español y las notas de licencia registradas se citan en su idioma original.
