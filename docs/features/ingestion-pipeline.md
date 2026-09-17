# Pipeline de ingestión local

El pipeline convierte una copia local obtenida y autorizada por el usuario en artefactos canónicos que el Dataset Registry y Corpus Explorer pueden leer. No descarga corpus, no llama APIs externas y nunca modifica la fuente.

## Raw y processed

`data/raw/` contiene la copia original del proveedor y se considera inmutable. Debe conservarse fuera de Git y no se limpia, normaliza ni reescribe. `data/processed/` contiene una representación derivada y reemplazable:

```text
data/processed/<dataset_id>/
├── dataset.json
├── records.jsonl
├── ingestion-manifest.json
├── audio-resources.jsonl   # cuando corresponda
└── speakers.jsonl          # cuando corresponda
```

Las colecciones usan JSONL: cada línea es un objeto canónico independiente en UTF-8. Esto evita escribir un único array JSON grande. `dataset.json` conserva la metadata de la colección. El manifest de ejecución solo incluye identificadores, ruta de origen, fecha, conteos, advertencias y nombres relativos de archivos fuente; no incluye texto del corpus ni atributos sensibles de hablantes.

## Flujo y adaptadores

La CLI resuelve un nombre mediante el registro explícito de adaptadores:

- `americas_nlp` lee los pares `train`, `dev` y `test` en Aymara y español;
- `common_voice` lee `validated.tsv`, crea referencias a `clips/` y no copia MP3.

El adaptador carga metadata y registros. El pipeline vuelve a validar cada `Dataset`, `CorpusRecord`, `AudioResource` y `Speaker` con los modelos canónicos, comprueba que todos pertenezcan al mismo `dataset_id`, escribe en un directorio temporal y publica el directorio completo mediante renombrado. Una segunda ejecución reemplaza de forma segura la materialización anterior. Si la nueva ejecución falla antes de publicarse, la anterior permanece disponible.

Cada `CorpusRecord` conserva `dataset_id`, `source_record_id` y `provenance`. AmericasNLP añade el split y los nombres de los archivos fuente en `metadata`; Common Voice conserva la referencia local al audio original sin duplicarlo.

## Ejecutar

Desde la raíz del repositorio en PowerShell:

```powershell
python scripts\ingest_dataset.py `
  --adapter americas_nlp `
  --source data\raw\aymara\americasnlp `
  --output data\processed
```

Para Common Voice:

```powershell
python scripts\ingest_dataset.py `
  --adapter common_voice `
  --source data\raw\quechua\common-voice-puno `
  --output data\processed
```

La CLI imprime el destino y los conteos. Las advertencias también quedan en `ingestion-manifest.json`; por ejemplo, una referencia a un clip ausente se conserva y se reporta. Un adaptador desconocido, una fuente ausente o datos canónicos inválidos terminan con código de salida 1 sin publicar resultados parciales.

Con el backend en ejecución, se puede verificar la disponibilidad derivada y consultar los registros:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/datasets/americasnlp-2021-aymara-spanish
Invoke-RestMethod "http://localhost:8000/api/v1/datasets/americasnlp-2021-aymara-spanish/records?q=texto&limit=20&offset=0"
```

El repositorio combina la descripción versionada en `datasets/registry/` con `records.jsonl`. Si existe una materialización válida, expone `metadata.available_locally: true` sin editar el manifest catalogado. La búsqueda textual y la paginación operan sobre esos registros mediante el flujo existente.

Para recrear una materialización basta con volver a ejecutar el mismo comando. Para borrarla, detener cualquier proceso que la esté leyendo y eliminar únicamente `data/processed/<dataset_id>/`; no borrar ni alterar `data/raw/`.

## Privacidad, licencias y redistribución

La ingestión local no concede derechos sobre el corpus. Antes de procesar datos, el usuario debe obtenerlos desde el proveedor autorizado y revisar licencia, términos de acceso, atribución, uso comercial, derivados y privacidad. Los artefactos procesados pueden seguir sujetos a las mismas restricciones que la fuente.

No se deben añadir `data/raw/**` ni `data/processed/**` a Git, publicar materializaciones o redistribuir audio si la licencia o los términos no lo permiten. Para Common Voice se conservan identificadores seudónimos solo cuando la fuente los aporta; no deben usarse para intentar identificar participantes. El proyecto no incluye corpus reales.
