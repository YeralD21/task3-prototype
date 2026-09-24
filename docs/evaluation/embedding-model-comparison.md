# Comparación de modelos de embeddings

Fecha de ejecución: 17 de septiembre de 2026.

Esta es una **evaluación técnica de desarrollo**, no una evaluación científica ni lingüística. Sirve para elegir una configuración inicial del prototipo y comprobar el flujo local. No demuestra calidad para Quechua, Aymara ni sus variedades. Una evaluación válida para esas lenguas requerirá datos reales autorizados, criterios definidos con hablantes y anotación humana.

## Entorno

- Windows, CPU, Python 3.13.0 en `backend/.venv-ml`.
- `sentence-transformers==6.0.1`.
- `torch==2.14.0`.
- `numpy==2.5.3`.
- ejecución local, sin API de inferencia ni servicio cloud.

Se usó un entorno ML separado para no alterar el entorno del backend. NumPy y Torch publican artefactos para Python 3.14, pero Sentence Transformers 6.0.1 solo enumera clasificadores hasta Python 3.13. Por eso Python 3.13 es la combinación verificada en esta ejecución.

## Benchmark

`datasets/evaluation/synthetic-semantic-benchmark.json` contiene 24 frases creadas para esta prueba: tres registros para cada uno de ocho temas (agricultura, familia, educación, salud, naturaleza, comercio, viaje y comida). Dos registros de cada tema están en español y uno en inglés. Las ocho consultas están en español y tienen tres identificadores relevantes explícitos.

Los ejemplos son sintéticos y no pretenden representar Quechua o Aymara. Las consultas usan formulaciones distintas a varios registros relevantes para exigir algo más que coincidencia textual, aunque el conjunto sigue siendo pequeño y sencillo.

Se calculó macro Precision@5, Recall@5 y MRR sobre las ocho consultas. Como solo existen tres relevantes por consulta, la Precision@5 máxima es `3/5 = 0.60`.

## Candidatos

| Modelo | Motivo de inclusión | Dimensión | Tamaño publicado | Licencia |
|---|---|---:|---:|---|
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Alternativa compacta para similitud, integración directa y 50 idiomas declarados | 384 | ~0.1B parámetros | Apache-2.0 |
| `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | Variante de mayor capacidad para comprobar si 768 dimensiones mejoran el ranking | 768 | ~0.3B parámetros | Apache-2.0 |
| `sentence-transformers/distiluse-base-multilingual-cased-v2` | Arquitectura destilada, 50 idiomas declarados y representación intermedia | 512 | ~0.1B parámetros | Apache-2.0 |

Las fichas dicen “50 languages”, pero no aportan evidencia específica suficiente para afirmar buen soporte de Quechua o Aymara. Esa incertidumbre se conserva como limitación central.

Fuentes: [MiniLM](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2), [MPNet](https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2) y [DistilUSE](https://huggingface.co/sentence-transformers/distiluse-base-multilingual-cased-v2).

## Resultados

| Modelo | Precision@5 | Recall@5 | MRR | Carga inicial* | Carga con caché | Embeddings** | Búsqueda |
|---|---:|---:|---:|---:|---:|---:|---:|
| MiniLM-L12-v2 | 0.6000 | 1.0000 | 1.0000 | 65.833 s | 10.710 s | 0.132 s | 0.000418 s |
| multilingual-mpnet-base-v2 | 0.6000 | 1.0000 | 1.0000 | 82.842 s | 10.665 s | 0.303 s | 0.000864 s |
| distiluse-multilingual-cased-v2 | 0.6000 | 1.0000 | 1.0000 | 45.432 s | 4.121 s | 0.220 s | 0.000413 s |

\* La carga inicial incluye descarga desde Hugging Face y depende de red, caché y límites del servicio; no es una medida comparable de inferencia.

\** Tiempo para 24 registros y ocho consultas en CPU. Son mediciones orientativas de una sola ejecución con caché caliente, no un benchmark de rendimiento científico.

Los tres modelos recuperaron los tres relevantes dentro de los primeros cinco lugares para cada consulta y colocaron al menos uno en la primera posición. El benchmark es demasiado sencillo para establecer diferencias de calidad entre ellos.

## Recomendación

**Modelo recomendado para el prototipo: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.**

La calidad quedó empatada. MiniLM produce el vector más pequeño (384 dimensiones), tuvo la inferencia más rápida de los tres en esta ejecución y su tamaño publicado es aproximadamente 0.1B parámetros. Esto reduce almacenamiento por índice y costo de cálculo frente a MPNet. DistilUSE cargó más rápido desde caché, pero genera vectores de 512 dimensiones y su inferencia fue más lenta en esta muestra.

La recomendación es operativa y provisional. No constituye evidencia de calidad para Quechua o Aymara. Si una evaluación futura con datos autorizados y anotación humana muestra otra cosa, `EMBEDDING_MODEL_NAME` permite cambiar el modelo y reconstruir el índice sin alterar la arquitectura.

## Repetir la evaluación

Crear el entorno aislado desde la raíz:

```powershell
py -3.13 -m venv backend\.venv-ml
backend\.venv-ml\Scripts\python.exe -m pip install -r backend\requirements-ml.txt
```

Ejecutar:

```powershell
backend\.venv-ml\Scripts\python.exe scripts\evaluate_embedding_models.py `
  --models `
    sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 `
    sentence-transformers/paraphrase-multilingual-mpnet-base-v2 `
    sentence-transformers/distiluse-base-multilingual-cased-v2 `
  --benchmark datasets\evaluation\synthetic-semantic-benchmark.json `
  --k 5
```

La ejecución manual puede descargar modelos públicos si no están en caché. `pytest`, `npm test` y el build no ejecutan esa descarga. No se versionan pesos ni cachés.
