# Atlas Vivo

Atlas Vivo proyecta cada registro de un dataset a un punto `(x, y)` y lo muestra como un mapa interactivo en el detalle del dataset. Incluye reducción dimensional, artefactos locales, detección de desactualización, API y una primera visualización SVG con hover y selección. Todavía no hay clustering ni base de datos.

## La cercanía en 2D es una aproximación

Un embedding de MiniLM tiene 384 dimensiones; el Atlas conserva 2. **La proyección pierde información de forma inevitable**:

- dos puntos cercanos en el mapa pueden estar lejos en el espacio original, y viceversa;
- las distancias en 2D no equivalen a la similitud coseno usada por la búsqueda semántica;
- con PCA, `diagnostics.explained_variance_ratio_total` indica qué fracción de la varianza conservan los dos ejes. Un valor de `0.15` significa que el 85 % de la variación no es visible en el mapa;
- con UMAP, las distancias entre grupos lejanos y el tamaño aparente de cada grupo no tienen una interpretación cuantitativa fiable;
- los ejes no tienen significado lingüístico. En PCA son direcciones de máxima varianza; en UMAP son arbitrarios.

La proyección hereda además las limitaciones del modelo de embeddings, que no está evaluado para Quechua ni Aymara (ver [comparación de modelos](../evaluation/embedding-model-comparison.md)). El Atlas sirve para explorar y formular hipótesis, no para sacar conclusiones sobre la lengua. Para medir similitud, usa la [búsqueda semántica](semantic-search.md).

## Flujo

```text
data/processed/<dataset_id>/records.jsonl          (canónico, solo lectura)
data/processed/<dataset_id>/semantic/embeddings.npy (solo lectura; no se recalcula)
        │  LocalSemanticIndexRepository.load  → valida frescura y coherencia
        ▼
DimensionalityReducer.fit_transform  (N×D → N×2)
        ▼
data/processed/<dataset_id>/atlas/
├── coordinates.jsonl
└── atlas-manifest.json
        ▼
GET /api/v1/datasets/{dataset_id}/atlas
```

El Atlas **no recalcula embeddings ni carga modelos de lenguaje**. Reutiliza la matriz publicada por `scripts/build_semantic_index.py`. Construirlo no importa `sentence_transformers`, `torch` ni `transformers`.

## Arquitectura

| Capa | Archivo | Responsabilidad |
|---|---|---|
| Reductores | `ml/atlas/reducers.py` | Protocolo `DimensionalityReducer`, `PCAReducer`, `UMAPReducer` opcional, validación de entrada |
| Builder | `ml/atlas/builder.py` | Lee el índice semántico, reduce, valida la salida y publica los artefactos de forma atómica |
| Repositorio | `backend/app/repositories/atlas_repository.py` | Carga los artefactos, verifica frescura y coherencia |
| Servicio | `backend/app/services/atlas_service.py` | Comprueba el dataset, aplica el límite y el muestreo |
| API | `backend/app/api/routes/atlas.py` | Endpoint HTTP y traducción de errores |
| CLI | `scripts/build_atlas.py` | Construcción manual |

`DimensionalityReducer` expone `name`, `parameters` y `fit_transform(embeddings) -> ReductionResult(coordinates, diagnostics)`. Para añadir un reductor, basta con implementar ese contrato y registrarlo en `REDUCERS`.

## Reductores

### PCA (predeterminado)

Implementado en NumPy puro, sin dependencias nuevas:

1. centra la matriz;
2. obtiene los autovectores de la matriz de dispersión `XᵀX` (D×D) con `numpy.linalg.eigh`;
3. ordena por varianza descendente y conserva dos componentes;
4. **canoniza el signo** de cada componente (la carga de mayor valor absoluto queda positiva).

El paso 4 hace la salida determinista: la misma matriz produce coordenadas idénticas byte a byte en cada ejecución. Sin él, un eje podría invertirse entre ejecuciones. Resolver un problema D×D en lugar de una SVD N×D mantiene bajo el uso de memoria cuando hay muchos registros.

Si el rango es menor que 2 (por ejemplo, un solo registro o una sola dimensión), las columnas faltantes se completan con ceros. Se rechazan matrices vacías, no bidimensionales, no numéricas o con `NaN`/`inf`.

### UMAP (opcional)

`UMAPReducer` usa `umap-learn` con `random_state` explícito (predeterminado `42`) y `n_jobs=1`, porque UMAP solo es reproducible en modo de un hilo. `n_neighbors` se limita a `N - 1` y el valor efectivo queda en `diagnostics`. La métrica predeterminada es `cosine`, coherente con la búsqueda semántica.

No se instala con el backend. Su compatibilidad se verificó el 24 de septiembre de 2026 en `backend/.venv-ml` (Windows, CPython 3.13.0, NumPy 2.5.3): `umap-learn 0.5.12` añade `numba 0.67.0`, `llvmlite 0.49.0` y `pynndescent 0.6.0` sin modificar NumPy. Dos ejecuciones con `random_state=42` generaron archivos idénticos. La primera ejecución tardó unos 2 minutos por la compilación JIT de numba. La reproducibilidad está garantizada solo con las mismas versiones y la misma plataforma.

```powershell
backend\.venv-ml\Scripts\python -m pip install -r backend\requirements-umap.txt
```

Sin la dependencia, `--reducer umap` falla con un mensaje claro y el Atlas existente se conserva.

PCA es el baseline recomendado: es exacto, rápido, sin dependencias y su pérdida de información se puede medir. UMAP suele separar mejor los grupos locales, pero distorsiona las distancias globales.

## Artefactos

`coordinates.jsonl` tiene una línea por registro, en el mismo orden que la matriz de embeddings:

```json
{"record_id": "synthetic-record-001", "dataset_id": "synthetic-development-dataset", "source_record_id": "synthetic-source-record-001", "x": 1.973, "y": 63.24}
```

`dataset_id` y `source_record_id` conservan la trazabilidad hasta la fuente original. `record_id` permite cruzar con `records.jsonl` o con la API de registros. No se duplican textos.

`atlas-manifest.json`:

| Campo | Contenido |
|---|---|
| `atlas_format_version` | Versión del formato (`1`) |
| `dataset_id` | Dataset proyectado |
| `reducer` | `pca` o `umap` |
| `created_at` | Fecha de construcción en UTC, ISO 8601 |
| `source_embedding_provider` / `source_embedding_model` | Proveedor y modelo del índice semántico |
| `source_embedding_dimension` | Dimensión original (p. ej. 384) |
| `record_count` | Número de puntos |
| `source_records_fingerprint` | SHA-256 del `records.jsonl` canónico |
| `semantic_index_fingerprint` | SHA-256 de `semantic/embeddings.npy` + `semantic/records.jsonl` |
| `parameters` | Parámetros del reductor (incluye `random_state` en UMAP) |
| `diagnostics` | Varianza explicada (PCA) o `n_neighbors` efectivo (UMAP), y versión de la librería |

La publicación escribe en un directorio temporal y lo intercambia con `atlas/`. Un error nunca deja un Atlas a medio escribir. Los artefactos quedan bajo `data/processed/`, que Git ignora.

## Detección de Atlas desactualizado

En cada lectura, el repositorio recalcula ambas huellas:

- si cambió `records.jsonl` (reingesta o edición) → `StaleAtlasError` («canonical records changed»);
- si cambió `embeddings.npy` o el mapeo de filas (índice reconstruido, otro modelo, otro orden) → `StaleAtlasError` («embeddings changed»);
- si falta el índice semántico → `SemanticIndexNotFoundError`: el Atlas no se puede verificar y no se sirve.

El fingerprint del índice cubre los bytes de la matriz y del mapeo, no el `index-manifest.json`. Así, reconstruir el índice con resultados idénticos no invalida el Atlas, pero cualquier cambio en un solo valor sí lo hace. El builder también rechaza un índice semántico desactualizado y vuelve a calcular la huella tras la reducción, para detectar cambios concurrentes.

Coste: cada petición recalcula SHA-256 sobre `records.jsonl` y `embeddings.npy` (como ya ocurre en la búsqueda semántica). Es aceptable para corpus del tamaño actual. Si se vuelve un cuello de botella, puede cachearse por tamaño y fecha de modificación.

## Construcción

Requiere haber ingerido el dataset y construido el índice semántico:

```powershell
python scripts\build_atlas.py `
  --dataset americasnlp-2021-aymara-spanish `
  --processed-root data\processed
```

Con UMAP (desde el entorno que tenga `umap-learn`):

```powershell
backend\.venv-ml\Scripts\python scripts\build_atlas.py `
  --dataset americasnlp-2021-aymara-spanish `
  --reducer umap --random-state 42 --n-neighbors 15 --min-dist 0.1
```

Reconstruye el Atlas después de reingerir o de reconstruir el índice semántico. Mientras no lo hagas, la API responde `409`.

## API

```http
GET /api/v1/datasets/{dataset_id}/atlas?limit=2000
```

- `limit`: predeterminado `2000`, mínimo `1`, **máximo `5000`**. Fuera de rango devuelve `422`.
- Si el Atlas tiene más puntos que `limit`, se devuelve una **muestra reproducible**: los `limit` registros con menor SHA-256 de `record_id`, en el orden original. No usa semillas ni depende del orden del archivo. La misma petición devuelve siempre los mismos puntos, y una muestra más pequeña está contenida en una mayor. Es una muestra pseudoaleatoria uniforme, no estratificada por idioma, variedad ni split.

Respuesta:

```json
{
  "dataset_id": "synthetic-development-dataset",
  "reducer": "pca",
  "created_at": "2026-09-24T13:08:00.455117+00:00",
  "source_embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
  "source_embedding_dimension": 384,
  "parameters": {"n_components": 2, "centered": true, "whiten": false, "...": "..."},
  "diagnostics": {"explained_variance_ratio": [0.47, 0.45], "explained_variance_ratio_total": 0.92},
  "total_records": 60,
  "returned_records": 12,
  "limit": 12,
  "sampling": {"applied": true, "method": "sha256_record_id"},
  "items": [{
    "record_id": "...", "dataset_id": "...", "source_record_id": "...", "x": 0.71, "y": 63.31,
    "record": {"id": "...", "text": "...", "translation": null, "language": {"...": "..."}, "provenance": {"...": "..."}}
  }]
}
```

Cada elemento de `items` incluye el `CorpusRecord` completo en `record`, para que la interfaz muestre texto, traducción y procedencia sin otra petición. Los artefactos en disco no cambian: `coordinates.jsonl` sigue sin duplicar textos. El servicio une los puntos muestreados con los registros canónicos y comprueba que `source_record_id` coincida. Si un punto referencia un registro inexistente, responde `500` con un mensaje genérico.

| Situación | Código |
|---|---|
| Dataset inexistente | `404` |
| Dataset catalogado sin copia local | `409` |
| Atlas no construido | `409` |
| Índice semántico ausente | `409` |
| Atlas desactualizado | `409` |
| `limit` inválido | `422` |
| Artefactos corruptos o incoherentes | `500` con mensaje genérico |

Las respuestas de error contienen solo un `detail` legible, sin rutas locales ni stack traces.

## Uso desde el frontend

En `/datasets/[id]`, después de «Búsqueda semántica», está la sección **Atlas Vivo** (ancla `#atlas`). Las secciones existentes no cambian.

1. La sección explica qué representa el mapa y sus límites. Si el dataset no tiene copia local, muestra el aviso y no hace ninguna petición.
2. «Puntos a solicitar» ofrece 250, 500, 1000 (predeterminado) y 2000. La interfaz nunca pide 5000.
3. «Abrir Atlas Vivo» carga el Atlas solo cuando la persona lo pide. Así, visitar el detalle no descarga cientos de registros. Cambiar el límite después vuelve a consultar.
4. Sobre el mapa se muestra el reductor (PCA/UMAP), «N de M puntos visibles», si se aplicó la muestra reproducible y, solo con PCA, la varianza conservada por los dos ejes.

### Interacción

- **Hover:** el punto crece y recibe un contorno. Un tooltip breve muestra el texto (hasta 120 caracteres), la traducción si existe (hasta 100), el idioma y el `source_record_id`.
- **Clic:** selecciona el punto. Se marca en naranja, con mayor tamaño, contorno grueso y un anillo discontinuo, así que no depende solo del color. El panel «Registro seleccionado» muestra el texto completo, la traducción, el idioma, la variedad, el split, `source_record_id`, `dataset_id`, el audio disponible, la procedencia completa (organización, dataset original, cita, fecha, notas, URL) y las coordenadas originales.
- **Teclado:** el mapa es un solo elemento enfocable, con el foco visible en naranja. Las flechas recorren los puntos de izquierda a derecha, `Inicio`/`Fin` saltan al primero y al último, y `Escape` limpia la selección. Los puntos no son elementos de tabulación individuales, para no crear cientos de paradas de foco.
- **Botones:** «Punto anterior» y «Punto siguiente» recorren el mismo orden sin necesidad de ratón.
- El SVG tiene `<title>` y `<desc>`. El registro seleccionado se anuncia fuera del SVG, en una región `aria-live`, junto con su posición («Punto 29 de 60»).
- **Diseño:** en escritorio, el mapa y el panel quedan lado a lado. Por debajo de 900 px, el mapa queda arriba y el detalle debajo, sin scroll horizontal.

### Estados

| Situación | Mensaje |
|---|---|
| Cargando | «Cargando el Atlas…» (`aria-busy`) |
| Sin copia local | «Para ver el Atlas Vivo, primero debe existir una copia local procesada del dataset.» |
| Atlas no construido | «Este dataset todavía no tiene un Atlas construido.» |
| Atlas desactualizado | «El Atlas está desactualizado y debe reconstruirse.» |
| Sin índice semántico | «Este dataset todavía no tiene un índice semántico. Es necesario construirlo antes que el Atlas.» |
| Respuesta vacía | «El Atlas no contiene puntos para mostrar.» |
| Otro error | Mensaje genérico con botón «Reintentar» |

Nunca se muestran el `detail` crudo de la API ni stack traces.

### Escalado

`scaleAtlasPoints` (`frontend/src/services/atlas.ts`) convierte las coordenadas del Atlas a un `viewBox` de 800×520 con 32 px de padding, sin modificar los datos:

- usa **la misma escala en ambos ejes** para no deformar la proyección. Por eso, una nube alargada no ocupa todo el alto;
- centra la nube; un eje constante queda en el centro; un solo punto queda en el centro del mapa;
- admite coordenadas negativas y cualquier rango;
- invierte el eje vertical para que `y` crezca hacia arriba.

### Limitaciones visuales

- Los puntos cercanos pueden **solaparse**. El hover y el clic corresponden al punto visible encima. Para llegar a todos, usa las flechas o los botones anterior/siguiente.
- No hay zoom, desplazamiento, búsqueda dentro del mapa, filtros ni colores por tema o categoría. Todos los puntos usan el mismo color.
- Con escala uniforme, si un eje tiene mucho más rango que el otro, la nube se ve aplanada. Es intencional: refleja la proyección real.
- El SVG está pensado para los límites que ofrece la interfaz (hasta 2000 puntos).
- El tooltip requiere un puntero. En pantallas táctiles, el toque selecciona y el detalle aparece debajo del mapa.

### Componentes

| Archivo | Responsabilidad |
|---|---|
| `components/AtlasExplorer.tsx` | Sección, explicación, límite, petición y estado de selección |
| `components/AtlasView.tsx` | Estados, metadata y teclado; compone mapa y detalle |
| `components/AtlasPlot.tsx` | SVG, puntos (normal/hover/seleccionado) y tooltip; sin estado propio |
| `components/AtlasPointDetails.tsx` | Panel del registro; reutiliza `CorpusRecordCard` y añade procedencia y coordenadas |
| `services/atlas.ts` | Escalado, orden de lectura, navegación y formato |
| `services/api.ts` | `getDatasetAtlas(datasetId, limit)` y traducción de errores |

Sin dependencias nuevas: SVG nativo de React, sin D3, Plotly ni WebGL.

## Pruebas

`frontend/tests/atlas.test.ts` (21 pruebas, sin red ni modelos) cubre: petición (URL, id codificado, límite, señal), escalado (rango normal, negativos, x/y constantes, un punto, proporciones, sin mutar la entrada), carga, puntos renderizados, SVG accesible, metadata, respuesta vacía, clic y hover (invocando los handlers de los puntos), marcado del seleccionado, detalle completo, traducción opcional en tooltip y panel, navegación por teclado, Atlas inexistente o desactualizado, índice ausente, dataset no local, error genérico y ausencia de `any`.

`backend/tests/test_atlas.py` (42 pruebas) usa embeddings sintéticos y `FakeEmbeddingProvider`, con la red bloqueada. Cubre: forma N×2, determinismo, invariancia de signo, recuperación de la dirección dominante, rango bajo, entradas inválidas, UMAP ausente, `random_state` explícito en UMAP (con un módulo simulado), artefactos, manifest, fingerprints, inmutabilidad de `embeddings.npy` y `records.jsonl`, reconstrucción determinista, índice semántico inexistente o desactualizado, Atlas desactualizado por registros o embeddings, artefactos corruptos, muestreo, CLI y todos los códigos del endpoint. No descargan ni cargan modelos.

## Fuera de alcance

Clustering, colores por tema, clasificación automática, búsqueda o filtros dentro del Atlas, zoom, D3/Plotly/WebGL, PostgreSQL/pgvector, Corpus Radio y entrenamiento o fine-tuning.
