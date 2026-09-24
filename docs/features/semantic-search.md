# Búsqueda semántica local

La búsqueda textual existente encuentra subcadenas en `text` y `translation`. La búsqueda semántica compara vectores y puede recuperar textos cercanos a una consulta aunque no contengan exactamente las mismas palabras. Un embedding es un vector numérico generado por un modelo a partir de un texto; su utilidad depende del modelo, el idioma, la variedad y el dominio.

## Arquitectura

`EmbeddingProvider` separa el sistema del modelo. Expone operaciones para un texto o un lote de textos. El proyecto incluye:

- `SentenceTransformerProvider`, implementación real y opcional;
- `FakeEmbeddingProvider`, representación determinista por tokens usada solo en pruebas y demostraciones técnicas.

El proveedor fake no mide significado ni calidad lingüística. No utiliza red ni carga modelos. La arquitectura deja abierta una evaluación posterior con Precision@k, Recall@k y MRR, pero esas métricas todavía no están implementadas.

Para esta primera versión la estrategia es `text_only`: se embebe exactamente `CorpusRecord.text`. Una traducción presente se conserva en el registro y en la respuesta, pero no se concatena al texto fuente. Esto evita mezclar idiomas silenciosamente y permite comparar otras estrategias más adelante.

## Índice local y fingerprint

El indexador lee `records.jsonl` sin modificarlo, valida cada `CorpusRecord`, genera una matriz y publica de forma segura:

```text
data/processed/<dataset_id>/semantic/
├── embeddings.npy
├── records.jsonl
└── index-manifest.json
```

El `records.jsonl` semántico solo relaciona posiciones de la matriz con `record_id`, `dataset_id` y `source_record_id`; no duplica el corpus. `embeddings.npy` contiene una matriz NumPy `float32`. El manifest registra dataset, proveedor, modelo, dimensión, cantidad de registros, fecha, estrategia y SHA-256 de los bytes exactos del `records.jsonl` canónico.

Antes de cada búsqueda se recalcula la huella. Si los registros cambiaron, el servicio rechaza el índice como desactualizado. También rechaza dimensiones inconsistentes o un proveedor/modelo distinto del usado durante la indexación.

## Dependencias y modelo configurable

NumPy es la única dependencia nueva del backend y se usa para `.npy` y similitud coseno. La integración real con Sentence Transformers se instala por separado:

```powershell
python -m pip install -r backend\requirements-ml.txt
```

El modelo se configura una sola vez mediante `EMBEDDING_MODEL_NAME` o `--model`. El valor inicial es una opción multilingüe de propósito general, no una afirmación de calidad para Quechua o Aymara. Que un modelo se describa como multilingüe no demuestra cobertura adecuada para todas las lenguas o variedades indígenas; se requiere evaluación con consultas y relevancias revisadas para cada caso.

La [comparación técnica de modelos](../evaluation/embedding-model-comparison.md) recomienda provisionalmente `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Los tres candidatos empataron en el benchmark sintético; MiniLM se eligió por sus vectores de 384 dimensiones, tamaño y latencia de inferencia. La configuración sigue siendo reemplazable.

Sentence Transformers puede descargar el modelo configurado desde Hugging Face cuando no existe en su caché. Esa acción solo ocurre al construir o consultar con el proveedor real; las pruebas nunca instancian ese proveedor ni descargan modelos. También se puede configurar una ruta local compatible como nombre del modelo.

Al 17 de septiembre de 2026, NumPy 2.5.3 y PyTorch 2.14 publican wheels para CPython 3.14. Sentence Transformers 6.0.1 declara Python 3.10 o posterior, pero sus clasificadores publicados enumeran hasta Python 3.13. Por prudencia, esta integración no declara Python 3.14 como combinación verificada de extremo a extremo; Python 3.12 o 3.13 es la recomendación para la función ML hasta verificar el conjunto completo. El entorno usado para las pruebas de esta iteración es Python 3.13.0.

## Construcción y reconstrucción

Después de ingerir el dataset:

```powershell
python scripts\build_semantic_index.py `
  --dataset americasnlp-2021-aymara-spanish `
  --processed-root data\processed
```

Para escoger otro modelo:

```powershell
python scripts\build_semantic_index.py `
  --dataset americasnlp-2021-aymara-spanish `
  --processed-root data\processed `
  --model nombre-o-ruta-del-modelo
```

Volver a ejecutar el comando reemplaza de forma segura únicamente `semantic/`. Debe reconstruirse después de reingerir o editar `records.jsonl`, o al cambiar proveedor, modelo o estrategia.

## Uso desde la interfaz

En `/datasets/[id]`, la información del dataset y «Explorar registros» se mantienen.
La sección «Búsqueda semántica» permite enviar una consulta con el botón
«Buscar semánticamente» o con Enter. No se realizan búsquedas por cada tecla.
La búsqueda textual encuentra coincidencias de palabras en texto y traducción;
la semántica utiliza el índice del texto original y devuelve hasta 10 registros.

Cada tarjeta conserva texto, traducción opcional, idioma, variedad, split,
identificadores y fuente. «Similitud semántica» expresa el coseno como porcentaje,
con hasta un decimal; puede ser negativo y no representa una probabilidad.
La consulta enviada permanece identificada sobre sus resultados.

La interfaz anuncia carga, errores y resultados vacíos. Explica cuándo falta
la copia local procesada, el índice o el modelo, y cuándo el índice está
desactualizado. No construye ni reconstruye índices automáticamente.
Su funcionamiento requiere que el backend ya tenga un índice y proveedor compatibles.

Las pruebas frontend usan respuestas sintéticas y renderizado React; no invocan
el proveedor real ni descargan modelos.

## Evaluación de modelos

`scripts/evaluate_embedding_models.py` carga el benchmark sintético, genera rankings y calcula Precision@k, Recall@k y MRR. También informa tiempos orientativos de carga, embeddings y búsqueda. Solo una ejecución manual sin `--fake` puede cargar o descargar modelos reales; las pruebas usan `FakeEmbeddingProvider`.

El benchmark versionado tiene 24 registros sintéticos y ocho consultas sobre agricultura, familia, educación, salud, naturaleza, comercio, viaje y comida. No contiene corpus reales ni ejemplos presentados como Quechua o Aymara. Consulta el informe para la metodología, resultados, limitaciones y comando reproducible.

## API

```http
POST /api/v1/search/semantic
Content-Type: application/json

{
  "query": "agricultura",
  "dataset_id": "americasnlp-2021-aymara-spanish",
  "limit": 10
}
```

La respuesta contiene la vista pública de cada registro (`PublicCorpusRecord`: sin `speaker_id` ni atributos del hablante) y su `score` coseno, preservando `dataset_id`, `source_record_id` y procedencia. Los vectores de norma cero reciben score `0`. Se informan explícitamente dataset inexistente o no materializado, índice ausente o desactualizado, consulta vacía, límite inválido, índice incoherente y proveedor no disponible.

[Atlas Vivo](atlas-vivo.md) reutiliza `embeddings.npy` para proyectar el corpus a 2D sin recalcular embeddings y se invalida cuando este índice cambia.

Los índices, modelos y cachés no deben incorporarse a Git. El índice deriva del corpus y queda sujeto a sus condiciones de licencia y redistribución.
