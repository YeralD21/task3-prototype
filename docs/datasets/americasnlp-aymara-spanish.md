# AmericasNLP 2021 — Aymara–Español

AmericasNLP organiza tareas de traducción para lenguas indígenas de las Américas.
Esta entrada cataloga exclusivamente los archivos Aymara–Español de la edición
2021. No representa todas las ediciones ni todos los recursos de AmericasNLP.

## Evidencia y procedencia

- El [README oficial del par](https://github.com/AmericasNLP/americasnlp2021/tree/main/data/aymara-spanish)
  identifica Global Voices vía OPUS como fuente del entrenamiento y usa `aym` y `es`.
- El [artículo de los organizadores](https://aclanthology.org/2021.americasnlp-1.23/)
  (Mager et al., 2021, secciones 3.1–3.2) atribuye dev/test a pares de AmericasNLI,
  traducidos desde XNLI en español. Describe Aymara central (`ayr`), específicamente
  Aymara La Paz jilata, para dev/test. No asignamos esa variedad a cada fila de train.
- El [directorio oficial de prueba](https://github.com/AmericasNLP/americasnlp2021/tree/main/test_data)
  contiene `test.aym` y `test.es`. El directorio del par contiene train/dev y también
  un `test.es`; para pruebas emparejar los dos archivos de `test_data/`.
- Citar también Tiedemann (2012), *Parallel Data, Tools and Interfaces in OPUS*,
  según solicita el proveedor. No atribuir dev/test a Global Voices.

## Códigos y variedad

El código del archivo se conserva: `language_code = aym`, `translation_language.iso_code = es`.
`ay` es el código ISO 639-1 de Aymara y `aym` su código de tres letras según la
[Library of Congress](https://www.loc.gov/standards/iso639-2/php/langcodes-keyword.php?SearchTerm=ay&SearchType=iso_639_1).
El artículo diferencia `aym`, `ayr` y `ayc`; atribuye expresamente `ayr` a dev/test.
Aquí `ayr` se guarda en la variedad, sin reemplazar `aym` en el registro. No se
infiere `ayc` ni se convierten códigos automáticamente. La variedad de train es
`null`. Países y regiones quedan desconocidos: distribución de un idioma no
equivale a ubicación documentada de todos los textos.

## Licencia

Los README oficiales consultados describen procedencia y solicitan citas, pero
no permiten establecer una licencia inequívoca para todos los archivos elegidos.
Por ello nombre, URL y permisos son `null`. Esto no concede permiso de uso ni
redistribución. Deben revisarse por separado las condiciones de Global Voices/OPUS
y de los pares de evaluación antes de reutilizarlos. No se traslada una licencia
de otra edición, del código de un repositorio, de un artículo o de AmericasNLI
automáticamente a esta colección. No se incluyen estadísticas ni una revisión de
Git inventadas; la edición es 2021 y `source_revision` permanece `null`.

## Formato y obtención manual

Son pares de archivos de texto UTF-8, sin cabecera ni columnas TSV/CSV. La línea
n de `.aym` corresponde a la línea n de `.es`. No eliminar líneas vacías para
intentar reparar un archivo: eso puede desalinear todos los pares posteriores.

Obtenga manualmente los archivos desde los enlaces oficiales anteriores, revise
las condiciones aplicables y conserve la revisión de origen con su copia local.
Coloque train/dev del directorio del par y test del directorio `test_data` así:

```text
data/raw/aymara/americasnlp/
├── train.aym
├── train.es
├── dev.aym
├── dev.es
├── test.aym
└── test.es
```

También puede pasar directamente otra carpeta local con estos nombres; solo
necesita los pares de los splits seleccionados. No hay descarga automática.
`data/raw/` está excluido de Git.

## Uso del adaptador

Desde la raíz, con las dependencias del backend instaladas y su Python activo:

```powershell
$env:PYTHONPATH = "$PWD/backend"
python
```

En Python:

```python
from pathlib import Path
from ml.ingestion.adapters.americas_nlp_adapter import AmericasNLPAdapter

adapter = AmericasNLPAdapter(
    Path("data/raw/aymara/americasnlp"),
    splits=("train", "dev", "test"),
)
dataset = adapter.load_metadata()  # Funciona sin descargar el corpus.
records = adapter.load_records()  # Exige los pares seleccionados.
```

El adaptador cumple `CorpusAdapter` y devuelve los modelos existentes. Por
defecto selecciona solo train. Cada par produce un `CorpusRecord`, orientado
explícitamente Aymara → Español aunque la evaluación original traducía hacia la
lengua indígena. `source_record_id` es una referencia derivada como `train.aym:1`,
no un identificador nativo inventado: la fuente ofrece líneas sin IDs explícitos.
El ID es estable para la misma copia y orden de archivos; cambiar líneas o la
revisión cambia esa referencia. Se conservan split, nombres de archivos, número
de línea, fuente original y procedencia; traducción y texto no se normalizan.

Las longitudes diferentes, líneas vacías, UTF-8 inválido y archivos ausentes
producen `AmericasNLPAdapterError`. No se devuelve una lista parcial ni se truncan
pares silenciosamente. Audio y hablante quedan `null`.

Los fixtures en `backend/tests/fixtures/americas_nlp/` son `synthetic` y
`development_only`, sin corpus real. Para convertirlos use `synthetic=True`;
los registros resultantes llevan ambas marcas y procedencia explícita de prueba.

## Catálogo y limitaciones

`GET /api/v1/datasets?language=aym` descubre el manifiesto con `cataloged: true`
y `available_locally: false`. Montar archivos no cambia automáticamente ese
estado ni publica registros por HTTP: esta iteración separa catálogo e ingestión.
El adaptador devuelve los registros al llamador; aún no los persiste.

La alineación sintáctica no garantiza traducciones correctas. Train y dev/test
tienen orígenes y dominios diferentes; deben conservarse separados para evitar
contaminación de evaluación. El lector materializa los registros en memoria,
una decisión adecuada para este prototipo, pendiente de revisar con corpus grandes.

Dataset Playbook podrá orientar el uso para Machine Translation, mostrando
origen, licencia desconocida y diferencias entre splits. Una futura búsqueda
semántica podrá consultar ambos textos sin perder procedencia. Estas capacidades
no se implementan aquí.

| Recurso | Modalidad | Uso principal | Modelo de salida |
| --- | --- | --- | --- |
| Common Voice Puno Quechua | audio y transcripción | ASR | Dataset, CorpusRecord, AudioResource, Speaker |
| AmericasNLP Aymara–Español | texto paralelo | Machine Translation | Dataset, CorpusRecord |

Ambos proveedores convergen al mismo contrato canónico y al catálogo existente.
