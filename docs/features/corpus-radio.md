# Corpus Radio

Corpus Radio permite escuchar registros que tienen audio **disponible localmente** mientras se muestran su transcripción completa, la traducción si existe, el idioma, la variedad, metadata no sensible y la procedencia. Está en la sección «Corpus Radio» de `/datasets/[id]`.

No descarga, copia, transcodifica ni redistribuye audio. No incluye TTS, ASR, alineación forzada ni karaoke.

## Arquitectura

```text
data/raw/<...>/clips/archivo.mp3        (copia original; nunca se copia ni modifica)
        │  referenciado por
data/processed/<dataset_id>/audio-resources.jsonl   (AudioResource.path_or_url)
data/processed/<dataset_id>/ingestion-manifest.json (source_path de la ingestión)
        │
LocalAudioRepository  →  CorpusRadioService  →  routes/radio.py
        │
GET /api/v1/datasets/{dataset_id}/radio?limit=20&offset=0
GET /api/v1/datasets/{dataset_id}/records/{source_record_id}/audio
        │
<audio controls> en el frontend
```

| Capa | Archivo | Responsabilidad |
|---|---|---|
| Repositorio | `backend/app/repositories/audio_repository.py` | Lee `audio-resources.jsonl` y `source_path`; caché en memoria invalidada por tamaño y fecha de modificación |
| Servicio | `backend/app/services/corpus_radio_service.py` | Decide si un registro tiene audio, resuelve y valida la ruta, detecta el formato y prepara la vista sin datos del hablante |
| Rutas | `backend/app/api/routes/radio.py` | Traduce errores a HTTP y responde el archivo con `FileResponse` |
| Frontend | `CorpusRadio.tsx`, `RadioView.tsx`, `RadioPlayer.tsx`, `services/radio.ts` | Estados, reproductor nativo, anterior/siguiente |

## Por qué el audio permanece en `data/raw`

`data/raw/` es la copia inmutable que el usuario obtuvo del proveedor. El pipeline de ingestión ya decidió **no copiar clips**: `AudioResource.path_or_url` apunta al archivo original. Corpus Radio respeta esa decisión:

- no duplica audio en `data/processed/` (hay una prueba que lo verifica);
- si el archivo desaparece de la copia local, el registro sigue visible y el audio se marca como no disponible;
- ninguna parte del audio entra en Git: `data/raw/**` y `data/processed/**` están ignorados y las pruebas usan bytes sintéticos creados en directorios temporales.

## Seguridad

El cliente **nunca envía rutas**. No existe ningún endpoint del tipo `/audio?path=...`. El clip se localiza solo mediante identificadores:

```text
dataset_id  →  CorpusRecord (source_record_id, coincidencia exacta y única)
            →  AudioResource (record.audio_id)
            →  path_or_url
```

`source_record_id` se usa únicamente como clave de búsqueda: nunca se concatena a una ruta. Por eso `../`, `..%2F`, `..\` o `C:\...` producen `404 Record ... was not found`.

Validación de la ruta resuelta (`CorpusRadioService._resolve_resource`):

1. Se rechazan las referencias vacías y las URL remotas (`://`): no se hace de proxy de contenido externo.
2. La carpeta fuente (`source_path` del `ingestion-manifest.json`) se resuelve y **debe estar dentro de la raíz raw autorizada**: `DATASET_RAW_PATH`, por defecto `data/raw/`.
3. La referencia se resuelve con `Path.resolve()`, que sigue los enlaces simbólicos, y **debe quedar dentro de esa carpeta fuente**. Esto bloquea `../`, rutas absolutas externas y symlinks que escapan; hay pruebas para los tres casos.
4. La contención se comprueba **antes** de consultar el disco, para no revelar qué archivos existen fuera.
5. El tipo se toma de una lista blanca de formatos de audio: `.mp3` → `audio/mpeg`, `.wav`, `.ogg`/`.oga`/`.opus`, `.flac`, `.m4a`, `.webm`. Si la extensión no aparece, se acepta el `mime_type` declarado solo si empieza por `audio/`. Cualquier otro formato no se sirve.

Las respuestas nunca contienen rutas del sistema. `audio_url` es una ruta relativa al endpoint controlado. El frontend solo acepta valores con la forma `/api/v1/datasets/<id>/records/<id>/audio` (`radioAudioSource`). Los errores devuelven mensajes sin rutas.

Cabeceras del audio: `Content-Disposition: inline` (sin nombre de archivo), `Cache-Control: private, no-store` y `X-Content-Type-Options: nosniff`.

### Configuración

```text
DATASET_RAW_PATH=/ruta/a/data/raw   # única raíz desde la que se puede leer audio
```

Si se ingirió desde una carpeta fuera de esa raíz (por ejemplo, un fixture), el audio aparece como «no puede reproducirse desde esta instalación» hasta ajustar la configuración o volver a ingerir desde `data/raw/`.

## Reproducción local y Range

Se usa `FileResponse` de Starlette 0.47.3, que ya atiende peticiones `Range`: responde `206 Partial Content` con `Content-Range`, `416` si el rango no es satisfacible y `Accept-Ranges: bytes`. No hace falta infraestructura propia de streaming. Esto se verificó en pruebas y en Chrome: el navegador pide `Range: bytes=0-`, recibe `206`, reproduce y permite avanzar y retroceder.

Como el navegador puede pedir el mismo clip varias veces, el índice de `audio-resources.jsonl` se guarda en memoria y se invalida si cambian el tamaño o la fecha del archivo. Cada petición sigue validando el registro y la ruta.

## API

### Listado

```http
GET /api/v1/datasets/{dataset_id}/radio?limit=20&offset=0
```

`limit` va de 1 a 100 (por defecto 20) y `offset` es ≥ 0. Solo incluye registros con referencia de audio (`audio_id`), en el orden de `records.jsonl`.

```json
{
  "dataset_id": "common-voice-scripted-speech-qxp-26.0",
  "contains_audio": true,
  "items": [{
    "record": {"source_record_id": "clip.mp3", "language_code": "qxp", "audio_id": "…:audio:clip.mp3", "...": "..."},
    "has_audio": true,
    "audio_status": "available",
    "audio_url": "/api/v1/datasets/common-voice-scripted-speech-qxp-26.0/records/clip.mp3/audio",
    "media_type": "audio/mpeg"
  }],
  "total": 3, "limit": 20, "offset": 0
}
```

`audio_status` puede ser:

- `available`: se incluye `audio_url`;
- `missing_file`: el registro referencia audio, pero el archivo no está en la copia local;
- `unsupported_format`: el formato no está en la lista blanca;
- `unavailable`: sin `AudioResource`, URL remota, ruta fuera de la carpeta autorizada o fuente fuera de `DATASET_RAW_PATH`.

Un archivo ausente **no** hace fallar el listado.

| Situación | Respuesta |
|---|---|
| Dataset sin modalidad `audio` (AmericasNLP) | `200` con `contains_audio: false`, sin comprobar disponibilidad local |
| Dataset con audio pero sin copia local | `409` «not available locally» |
| Dataset inexistente | `404` |
| `limit`/`offset` inválidos | `422` |

### Audio

```http
GET /api/v1/datasets/{dataset_id}/records/{source_record_id}/audio
```

Responde `200` o `206` con el archivo. Errores:

- `404`: dataset o registro inexistente, registro sin audio, o archivo ausente («Audio for record '…' is not available locally.»);
- `409`: dataset no local, o audio que no puede servirse (formato o ubicación);
- `500`: índice de audio corrupto, con un mensaje sin rutas.

## Privacidad

El adaptador de Common Voice ya descartaba `client_id`, `age`, `gender` y `sex` al ingerir. Corpus Radio va más allá y devuelve una **vista reducida** del registro:

- `speaker_id` no aparece: el identificador seudónimo permitiría vincular clips de una misma persona y escuchar no lo requiere;
- se eliminan de `metadata` los atributos descriptivos del hablante (`accent`/`accents`, `age`, `gender`, `sex`, `client_id`), sin distinguir mayúsculas.

Esta vista es `PublicCorpusRecord` (`backend/app/schemas/public.py`), la misma que usan `/records`, la búsqueda semántica y Atlas Vivo. Se aplica al construir la respuesta: `records.jsonl` en `data/processed` conserva el modelo canónico completo que produjo la ingestión.

La interfaz solo muestra idioma, variedad, split, registro original, dataset, formato y procedencia. No hay botón ni enlace de descarga, y el reproductor usa `controlsList="nodownload"`. Esto **no impide técnicamente** que un navegador guarde lo que reproduce: la protección real es no redistribuir ni publicar la instalación. La nota visible recuerda que el audio procede de la copia local, que no se redistribuye y que no debe intentarse identificar a quienes grabaron.

## Interfaz

- `<audio controls preload="metadata">` nativo, **sin autoplay**. Cada cambio de registro monta un reproductor nuevo en pausa.
- «← Registro anterior» y «Registro siguiente →» son botones con texto; se deshabilitan en los extremos y cruzan páginas de 20 registros.
- La posición («Registro 2 de 3») se anuncia con `aria-live`. El audio se asocia a la transcripción con `aria-describedby`.
- Estados:
  - carga;
  - dataset inexistente;
  - dataset no local («Para escuchar el audio, primero debe existir una copia local procesada del dataset.»);
  - sin audio («Este dataset no contiene audio.»);
  - lista vacía;
  - archivo ausente («El registro referencia audio, pero el archivo no está disponible localmente.»);
  - formato no compatible;
  - audio no reproducible;
  - error del navegador al reproducir;
  - error genérico con «Reintentar».

## Common Voice

Es el caso inicial. Se conservan `qxp`, «Puno Quechua / Punu qhichwa», `source_record_id` (el nombre del clip) y la procedencia completa, incluida la nota por fila «Loaded locally from validated.tsv row N». Se respetan las condiciones registradas en el manifiesto: `do_not_rehost` y `do_not_attempt_speaker_identification`. Los clips de Common Voice suelen ser MP3, pero el servicio no lo asume.

## AmericasNLP

Es texto paralelo, sin modalidad `audio`. Corpus Radio muestra «Este dataset no contiene audio.» y no inventa audio ni síntesis de voz.

## Limitaciones

- Solo se reproduce lo que existe en la copia local y está bajo `DATASET_RAW_PATH`.
- El listado reutiliza `list_records` del repositorio, que carga el `records.jsonl` completo en cada petición, igual que el resto de la API. Es adecuado para el prototipo, no para corpus muy grandes.
- No hay filtros por idioma o variedad en Radio, ni reproducción continua.
- Lo mismo ocurre con los formatos: el navegador decide qué puede reproducir.
- La vista pública retira atributos por nombre de clave. Un adaptador futuro que guarde datos personales bajo otros nombres deberá añadirlos a `PRIVATE_METADATA_KEYS`.

## Alineación temporal futura

Solo se muestran audio y transcripción completa. Un resaltado palabra por palabra necesitaría **timestamps reales por palabra o segmento**, aportados por la fuente o producidos por una alineación forzada validada para la lengua y la variedad. Los datos actuales no los contienen, y generarlos con modelos no evaluados para Quechua o Aymara podría inducir a error.

## Pruebas

- `backend/tests/test_corpus_radio.py` (22 pruebas, red bloqueada, bytes sintéticos) cubre:
  - audio: dataset con y sin audio, archivo existente y ausente, `Content-Type` MP3/WAV, formato no soportado y Range 206/416;
  - seguridad: traversal relativo, ruta absoluta externa, URL remota, fuente fuera de la raíz raw, symlink que escapa e ids del cliente nunca usados como ruta;
  - errores y listado: dataset inexistente o no local, paginación y ausencia de audio en `processed`;
  - datos: ausencia de rutas absolutas y de atributos sensibles, y conservación de procedencia y `source_record_id`.
- `frontend/tests/radio.test.ts` (12 pruebas) cubre:
  - la petición y la validación de `audio_url`;
  - carga, dataset sin audio y lista vacía;
  - transcripción, traducción opcional, reproductor nativo sin autoplay, anterior/siguiente entre páginas y audio ausente;
  - errores, procedencia y ausencia de `any`.
