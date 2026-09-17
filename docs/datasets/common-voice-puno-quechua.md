# Common Voice Scripted Speech — Puno Quechua

## Descripción

Mozilla Common Voice es una iniciativa de recopilación colaborativa de voz. Esta integración cataloga la colección **Common Voice Scripted Speech 26.0 — Puno Quechua**, donde las personas leen oraciones y los clips se distribuyen junto con transcripciones tabulares.

- Idioma/variedad: Puno Quechua / Punu qhichwa.
- Código ISO 639-3 y locale de Common Voice: `qxp`.
- Modalidades: audio MP3 y texto transcrito.
- Uso previsto registrado: reconocimiento automático del habla (ASR).
- Organización fuente: Mozilla Foundation / Common Voice.
- Corte de la versión documentada: 12 de junio de 2026.

El [catálogo oficial de Common Voice](https://commonvoice.mozilla.org/en/datasets) identifica la colección, licencia, locale, tarea y formato. El [repositorio oficial de estadísticas](https://github.com/common-voice/cv-dataset/blob/main/datasets/scripted-speech/cv-corpus-26.0-2026-06-12.json) documenta para `qxp` en la versión 26.0: 25 423 clips, 22 727 clips validados, 81 contribuyentes, 34.88 horas totales y 31.18 horas validadas. Estas cifras no se extrapolan a otras versiones.

## Licencia y condiciones adicionales

La licencia indicada es CC0-1.0. Eso no se presenta como ausencia absoluta de condiciones. Los términos de acceso de Mozilla Data Collective son adicionales y, entre otras reglas, prohíben intentar determinar o reidentificar a contribuyentes y restringen alojar o redistribuir el dataset fuera de la plataforma salvo autorización aplicable.

Este proyecto, por política:

- no redistribuye el corpus ni sus clips;
- no intenta identificar hablantes;
- conserva únicamente identificadores seudónimos cuando el TSV los aporta y son necesarios para representar la fuente;
- dirige la obtención del corpus completo a la fuente oficial;
- mantiene `data/raw/` fuera de Git.

Revise siempre los [términos vigentes para consumidores de Mozilla Data Collective](https://mozilladatacollective.com/terms/consumers) antes de usar una copia descargada.

## Obtención y ubicación local

La descarga no está automatizada. Acceda al catálogo oficial, autentíquese o acepte las condiciones que la fuente solicite y obtenga manualmente la versión adecuada. Después de extraer el paquete de `qxp`, ubique su contenido así:

```text
data/raw/quechua/common-voice-puno/
├── validated.tsv
├── train.tsv
├── dev.tsv
├── test.tsv
└── clips/
    └── <archivos proporcionados por Common Voice>.mp3
```

El adaptador usa `validated.tsv` por defecto; otro TSV puede seleccionarse con `tsv_filename`. No abre ni copia los clips: crea `AudioResource.path_or_url` apuntando a `clips/<path>`.

## Adaptador

`CommonVoiceAdapter` implementa `load_metadata()` y `load_records()` del contrato de ingestión, y ofrece además `load_audio_resources()` y `load_speakers()`.

- `load_metadata()` lee el manifiesto versionado del Registry y funciona sin corpus local.
- `load_records()` exige la carpeta local, interpreta TSV y produce `CorpusRecord`.
- `path` se conserva como `source_record_id` cuando existe.
- Si una fila no tiene `path`, se usa la posición estable `archivo:row:n`; nunca un UUID aleatorio.
- Los campos opcionales vacíos permanecen ausentes o `null`.
- `client_id` se trata exclusivamente como identificador seudónimo; edad, género o sexo no se copian al modelo.
- No existe código de descarga, scraping ni acceso de red.

## Estado en el Registry

El manifiesto contiene `cataloged: true` y `available_locally: false`. Por ello, la API puede descubrir el recurso aunque los archivos completos no estén presentes. El estado local no se cambia automáticamente; una futura iteración podrá calcularlo mediante configuración operativa.

## Funcionalidades futuras

Corpus Radio podrá usar las referencias locales de audio únicamente cuando el usuario haya montado una copia autorizada; esta iteración no reproduce ni transmite clips. Dataset Playbook podrá mostrar la utilidad ASR, versión, licencia, restricciones, procedencia y pasos de acceso oficial sin ofrecer una descarga duplicada.
