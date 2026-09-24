# task3-prototype

Prototipo open source para abrir, explorar, comprender y reutilizar datasets lingüísticos indígenas, inicialmente de Quechua y Aymara.

## Problema y objetivo

Muchos corpus valiosos son difíciles de descubrir y requieren descargar archivos, comprender formatos heterogéneos y escribir scripts antes de saber qué contienen. El proyecto busca reducir esa barrera mediante una arquitectura centrada en datasets, con procedencia, licencia y variante lingüística explícitas.

El prototipo incluye un modelo canónico, Dataset Registry y adaptadores locales para Common Voice y AmericasNLP. Atlas Vivo, Corpus Radio y Playbook quedan para iteraciones posteriores.

## Arquitectura general

- `backend/`: API FastAPI y futuras capas de dominio, servicios y persistencia.
- `frontend/`: catálogo web Next.js con TypeScript, filtros y fichas de datasets.
- `ml/`: ingestión, preprocesamiento, embeddings, análisis y evaluación.
- `datasets/`: manifiestos futuros y esquemas canónicos.
- `data/`: datos originales, intermedios, procesados y muestras.
- `notebooks/`: exploración reproducible.
- `docs/`: documentación de arquitectura.
- `scripts/`: automatizaciones del proyecto.

Consulta [la descripción de arquitectura](docs/architecture/overview.md), [el modelo canónico](docs/architecture/data-model.md), [el Dataset Registry](docs/architecture/dataset-registry.md) y [Corpus Explorer](docs/features/corpus-explorer.md).

## Tecnologías

- Next.js y TypeScript (App Router)
- Python 3.12, FastAPI y Pydantic
- PostgreSQL 16 y pgvector (infraestructura preparada; búsqueda aún no implementada)
- Docker Compose
- pytest

## Estructura

```text
backend/     API y pruebas
frontend/    catálogo web y fichas de datasets
ml/          canal de procesamiento futuro
data/        artefactos locales por etapa
datasets/    manifiestos y esquemas futuros
notebooks/   análisis exploratorio
docs/        documentación técnica
scripts/     tareas operativas
```

## Ejecutar el backend localmente

Desde la raíz del repositorio:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

La API estará disponible en `http://localhost:8000`. Verificación:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
```

Consultas disponibles del Registry:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/datasets
Invoke-RestMethod http://localhost:8000/api/v1/datasets/synthetic-development-dataset
Invoke-RestMethod http://localhost:8000/api/v1/datasets/common-voice-scripted-speech-qxp-26.0
Invoke-RestMethod "http://localhost:8000/api/v1/datasets/synthetic-development-dataset/records?limit=20&offset=0"
Invoke-RestMethod "http://localhost:8000/api/v1/datasets/synthetic-development-dataset/records?q=translation&limit=20&offset=0"
```

Las fuentes predeterminadas son `data/samples/` (`DATASET_REGISTRY_PATH`), `datasets/registry/` (`DATASET_CATALOG_PATH`) y `data/processed/` (`DATASET_PROCESSED_PATH`). Las rutas pueden configurarse mediante variables de entorno.

El catálogo también incluye [AmericasNLP 2021 Aymara–Español](docs/datasets/americasnlp-aymara-spanish.md), con códigos `aym`/`es`, texto paralelo y licencia pendiente de determinar. Sus archivos se obtienen manualmente; el adaptador conserva splits e identificadores de línea.

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/datasets?language=aym"
Invoke-RestMethod "http://localhost:8000/api/v1/datasets?language=qxp"
Invoke-RestMethod "http://localhost:8000/api/v1/datasets?modality=parallel_text"
Invoke-RestMethod "http://localhost:8000/api/v1/datasets?modality=audio"
Invoke-RestMethod "http://localhost:8000/api/v1/datasets?task=machine_translation"
```

También se puede iniciar el backend y PostgreSQL desde la raíz:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

## Ejecutar la aplicación web

Requisitos: Node.js 22.18+ (Node 24 recomendado para las pruebas TypeScript) y Python 3.12 con las dependencias del backend.

Terminal 1, desde la raíz (crear el entorno la primera vez siguiendo los pasos anteriores):

```powershell
cd backend
.venv\Scripts\Activate.ps1
$env:CORS_ORIGINS = '["http://localhost:3000"]'
uvicorn app.main:app --reload
```

Terminal 2, desde la raíz:

```powershell
cd frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

Aplicación: http://localhost:3000 · API: http://localhost:8000.

`frontend/.env.local` contiene `NEXT_PUBLIC_API_URL=http://localhost:8000`.
Es una URL pública accesible desde el navegador; reiniciar Next.js después de modificarla.
El backend admite `CORS_ORIGINS` como array JSON de orígenes concretos.
Si se utiliza un archivo `.env` para FastAPI, debe estar en el directorio de ejecución
(`backend/` con estos comandos); la variable de entorno anterior también funciona.

El App Router proporciona catálogo y `/datasets/[id]`; `services/api.ts` centraliza
las peticiones, `types/` refleja el contrato canónico y los componentes presentan
las fichas. Los filtros se envían al backend. La ficha incluye Corpus Explorer con
búsqueda textual, filtro de idioma y paginación; si el corpus no está instalado,
explica cómo acudir a la fuente oficial. No se ofrecen descargas de corpus.
La interfaz muestra carga, fallos de conexión, resultados vacíos y recursos inexistentes.

Comprobaciones frontend desde `frontend/`:

```powershell
npm run typecheck
npm test
npm run build
```

## Pruebas del backend

Con el entorno virtual activo y desde `backend/`:

```powershell
python -m pytest
```

## Ingestar un corpus local

Obtén el corpus manualmente desde su proveedor y colócalo bajo `data/raw/`. Esa fuente es inmutable y permanece fuera de Git. Desde la raíz, materializa una copia canónica con:

```powershell
python scripts\ingest_dataset.py `
  --adapter americas_nlp `
  --source data\raw\aymara\americasnlp `
  --output data\processed
```

También está disponible el adaptador `common_voice`. El comando valida los modelos, escribe `dataset.json`, `records.jsonl` e `ingestion-manifest.json`, y reemplaza de forma segura una materialización anterior. Common Voice referencia los clips originales sin copiarlos. Consulta [la guía del pipeline de ingestión](docs/features/ingestion-pipeline.md) para el flujo, privacidad, licencias y verificación mediante la API.

## Construir y consultar el índice semántico

La búsqueda semántica local usa NumPy y un `EmbeddingProvider` intercambiable. Para usar el proveedor real, instala las dependencias ML opcionales y construye el índice después de ingerir el dataset:

```powershell
python -m pip install -r backend\requirements-ml.txt
python scripts\build_semantic_index.py `
  --dataset americasnlp-2021-aymara-spanish `
  --processed-root data\processed
```

El modelo se configura con `EMBEDDING_MODEL_NAME` o `--model`. Sentence Transformers puede descargarlo si no está en caché; las pruebas usan un proveedor fake sin red. El endpoint es `POST /api/v1/search/semantic`. Consulta [la guía de búsqueda semántica](docs/features/semantic-search.md) para el formato, fingerprint, reconstrucción, compatibilidad y limitaciones lingüísticas.

Una [evaluación técnica reproducible](docs/evaluation/embedding-model-comparison.md) comparó tres modelos sobre 24 frases sintéticas. Recomienda provisionalmente `paraphrase-multilingual-MiniLM-L12-v2` por empatar en calidad con vectores más pequeños e inferencia rápida. El resultado no demuestra calidad para Quechua o Aymara y `EMBEDDING_MODEL_NAME` continúa configurable.

## Estado actual

En el detalle de cada dataset, la sección «Búsqueda semántica» permite enviar
consultas y comparar sus resultados con «Explorar registros» (búsqueda textual).
Muestra hasta 10 registros con similitud semántica y trazabilidad. Requiere un
índice local y un proveedor configurado; la interfaz explica si faltan o si el
índice debe reconstruirse.

El Registry cataloga Common Voice Scripted Speech 26.0 para Puno Quechua (`qxp`) y AmericasNLP 2021 Aymara–Español (`aym`/`es`), aunque los corpus no estén descargados. El frontend permite consultar el catálogo, filtrar datasets y explorar registros locales mediante búsqueda textual y paginación. Los adaptadores y el pipeline procesan copias locales obtenidas manualmente; la API descubre sus registros e índices semánticos bajo `data/processed/`. La búsqueda semántica está disponible mediante API y en la página de detalle. No existen persistencia PostgreSQL, autenticación, reproducción de audio ni descarga automática.
