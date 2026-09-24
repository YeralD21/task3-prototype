import { test } from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import {
  ApiError,
  getDatasetPlaybook,
  getPlaybookDatasets,
  playbookErrorMessage,
} from "../src/services/api.ts";
import { COMPATIBILITY, TASK_LABELS, permissionStatus } from "../src/services/playbook.ts";
import PlaybookView, { type PlaybookState } from "../src/components/PlaybookView.tsx";
import PlaybookTaskCard from "../src/components/PlaybookTaskCard.tsx";
import DatasetPlaybookSection from "../src/components/DatasetPlaybook.tsx";
import type {
  DatasetPlaybook,
  PlaybookCompatibility,
  PlaybookTaskAssessment,
  PlaybookTaskId,
} from "../src/types/dataset.ts";

function task(
  id: PlaybookTaskId, compatibility: PlaybookCompatibility, extra: Partial<PlaybookTaskAssessment> = {},
): PlaybookTaskAssessment {
  return {
    task: id, compatibility, reasons: [], limitations: [], license_notes: [],
    data_requirements: ["Requisito sintético."], next_steps: [], ...extra,
  };
}

const partialVariety =
  "La variedad Central Aymara (Aymara La Paz jilata) (ayr) está documentada solo para: dev, test. " +
  "La variedad del resto del corpus no está especificada.";

const playbook: DatasetPlaybook = {
  dataset_id: "americasnlp-2021-aymara-spanish",
  dataset_name: "AmericasNLP 2021 - Aymara-Spanish",
  languages: [{ name: "Aymara", iso_code: "aym" }, { name: "Spanish", iso_code: "es" }],
  variety: {
    status: "partial",
    varieties: [{
      id: "ayr", name: "Central Aymara (Aymara La Paz jilata)", language_code: "aym",
      region: null, country: null, glottocode: null, metadata: { splits: ["dev", "test"] },
    }],
    note: partialVariety,
  },
  license: {
    known: false, name: null, url: null, commercial_use: null, redistribution: null,
    derivatives: null, attribution_required: null, notes: "No unambiguous license.",
  },
  provenance: {
    source_organization: "AmericasNLP 2021 Shared Task organizers",
    source_url: "https://github.com/AmericasNLP/americasnlp2021/tree/main/data/aymara-spanish",
    documentation_url: "https://aclanthology.org/2021.americasnlp-1.23/",
    citation: "Mager et al. (2021)",
    provenance: {
      source_name: "AmericasNLP 2021 Shared Task on Open Machine Translation", source_url: null,
      organization: "AmericasNLP", original_dataset_id: "data/aymara-spanish", citation: null,
      retrieved_at: null, notes: null,
    },
  },
  local: { available_locally: false, semantic_index: "unknown", atlas: "unknown" },
  tasks: [
    task("machine_translation", "compatible", {
      reasons: ["Contiene texto paralelo (modalidad parallel_text)."],
      limitations: ["La alineación por registro no garantiza que cada traducción sea correcta.", partialVariety],
      license_notes: [
        "Según la metadata registrada, la licencia no está determinada; el permiso de uso no puede determinarse con la información disponible.",
        "La compatibilidad técnica no implica permiso: la metadata registrada no incluye una autorización explícita para entrenar modelos.",
      ],
      next_steps: ["Obtenga el recurso desde la fuente oficial y ejecute el pipeline de ingestión."],
    }),
    task("automatic_speech_recognition", "not_applicable", { limitations: ["No contiene audio registrado."] }),
    task("semantic_search", "compatible"),
    task("corpus_exploration", "compatible"),
    task("language_modeling", "potential"),
    task("linguistic_research", "potential"),
    task("educational_use", "unknown"),
  ],
  disclaimer: "No es asesoría legal ni una valoración de calidad.",
};

const render = (state: PlaybookState) =>
  renderToStaticMarkup(createElement(PlaybookView, { state, onRetry: () => {} }));
const ready = () => render({ status: "ready", playbook });

function useApi(t: { after: (fn: () => void) => void }) {
  const previous = process.env.NEXT_PUBLIC_API_URL;
  process.env.NEXT_PUBLIC_API_URL = "https://api.example.org";
  t.after(() => { if (previous === undefined) delete process.env.NEXT_PUBLIC_API_URL; else process.env.NEXT_PUBLIC_API_URL = previous; });
}

test("playbook requests use the dataset and discovery endpoints with GET and abort signal", async (t) => {
  useApi(t);
  const signal = new AbortController().signal;
  const urls: string[] = [];
  t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    urls.push(url);
    assert.equal(init.signal, signal);
    assert.equal(init.method, undefined);
    return Response.json(url.includes("/playbook/datasets") ? { task: "machine_translation" } : playbook);
  });
  const response = await getDatasetPlaybook("id x", signal);
  await getPlaybookDatasets("machine_translation", signal);
  assert.deepEqual(urls, [
    "https://api.example.org/api/v1/datasets/id%20x/playbook",
    "https://api.example.org/api/v1/playbook/datasets?task=machine_translation",
  ]);
  assert.equal(response.tasks.length, 7);
});

test("renders one card per task with Spanish labels", () => {
  const html = ready();
  assert.equal(html.match(/<article class="playbook-card /g)?.length, 7);
  for (const label of Object.values(TASK_LABELS)) assert.ok(html.includes(label), label);
});

test("compatibility is explicit text with a symbol, not only color", () => {
  for (const [state, { label, symbol }] of Object.entries(COMPATIBILITY)) {
    const html = renderToStaticMarkup(createElement(PlaybookTaskCard, {
      task: task("semantic_search", state as PlaybookCompatibility),
    }));
    assert.ok(html.includes(label), state);
    assert.ok(html.includes(symbol), state);
    assert.match(html, /Compatibilidad técnica: <\/span>/);
    assert.match(html, new RegExp(`playbook-badge--${state}`));
  }
  assert.doesNotMatch(ready(), /mejor|best|puntuaci[oó]n:|score/i);
});

test("reasons, limitations, license notes and next steps are listed under their headings", () => {
  const html = renderToStaticMarkup(createElement(PlaybookTaskCard, { task: playbook.tasks[0] }));
  for (const heading of ["¿Por qué?", "Limitaciones", "Licencia y uso", "Siguiente paso"])
    assert.ok(html.includes(`<h4>${heading}</h4>`), heading);
  assert.ok(html.includes("Contiene texto paralelo (modalidad parallel_text)."));
  assert.ok(html.includes("La alineación por registro no garantiza"));
  assert.ok(html.includes("no implica permiso"));
  assert.ok(html.includes("pipeline de ingestión"));
});

test("not applicable card omits empty sections", () => {
  const html = renderToStaticMarkup(createElement(PlaybookTaskCard, { task: playbook.tasks[1] }));
  assert.ok(html.includes("No contiene audio registrado."));
  assert.doesNotMatch(html, /¿Por qué\?|Licencia y uso|Siguiente paso/);
});

test("unknown license keeps every null permission as 'No determinado'", () => {
  const html = ready();
  assert.match(html, /Licencia no determinada/);
  assert.match(html, /el permiso no puede\s+determinarse/i);
  const license = html.slice(html.indexOf("playbook-license-title"), html.indexOf("playbook-variety-title"));
  assert.equal(license.match(/<dd>No determinado<\/dd>/g)?.length, 4);
  assert.doesNotMatch(license, /<dd>(Sí|No)<\/dd>/);
  assert.equal(permissionStatus(null), "No determinado");
  assert.equal(permissionStatus(false), "No");
  assert.equal(permissionStatus(true), "Sí");
});

test("partial variety is shown with its restricted scope and provenance stays visible", () => {
  const html = ready();
  assert.ok(html.includes("Central Aymara (Aymara La Paz jilata) (ayr)"));
  assert.ok(html.includes("Variedad documentada solo en parte del corpus"));
  assert.ok(html.includes("documentada solo para: dev, test"));
  assert.ok(html.includes("AmericasNLP 2021 Shared Task organizers"));
  assert.ok(html.includes("data/aymara-spanish"));
  assert.ok(html.includes('href="https://aclanthology.org/2021.americasnlp-1.23/"'));
  assert.ok(html.includes("No disponible localmente"));
  assert.doesNotMatch(html, /Índice semántico/);
  const unspecified = render({ status: "ready", playbook: {
    ...playbook, variety: { status: "unspecified", varieties: [], note: "Variedad no especificada en la metadata." },
  } });
  assert.match(unspecified, /<dd>No especificada<\/dd>/);
});

test("loading is announced", () => {
  const html = render({ status: "loading" });
  assert.match(html, /aria-busy="true"/);
  assert.match(html, /Cargando el Playbook/);
  assert.doesNotMatch(html, /playbook-card/);
  const section = renderToStaticMarkup(createElement(DatasetPlaybookSection, {
    dataset: { id: "x", name: "x", license: {}, provenance: {} } as never,
  }));
  assert.match(section, /id="playbook"/);
  assert.match(section, /Cargando el Playbook/);
});

test("generic errors hide raw details and offer a retry", () => {
  const message = playbookErrorMessage(new ApiError(500, "Dataset registry source could not be loaded."));
  assert.equal(playbookErrorMessage(new TypeError("Failed to fetch at line 9")), message);
  const html = render({ status: "error", message });
  assert.match(html, /role="alert"/);
  assert.match(html, /Reintentar/);
  assert.doesNotMatch(html, /registry source|line 9/);
});

test("missing dataset is explained without retry", async (t) => {
  useApi(t);
  t.mock.method(globalThis, "fetch", async () => Response.json({ detail: "Dataset 'x' was not found." }, { status: 404 }));
  const error = await getDatasetPlaybook("x").then(() => assert.fail("expected 404"), (e: unknown) => e);
  const message = playbookErrorMessage(error);
  assert.match(message, /no figura en el catálogo/);
  const html = render({ status: "missing", message });
  assert.doesNotMatch(html, /Reintentar|was not found/);
});

test("Playbook sources are typed without any", () => {
  for (const file of [
    "../src/services/playbook.ts", "../src/components/DatasetPlaybook.tsx", "../src/components/PlaybookView.tsx",
    "../src/components/PlaybookTaskCard.tsx", "../src/components/PlaybookContext.tsx",
    "../src/services/api.ts", "../src/types/dataset.ts",
  ]) {
    const source = readFileSync(new URL(file, import.meta.url), "utf8");
    assert.doesNotMatch(source, /:\s*any\b|\bas\s+any\b|<any>|\bany\[\]/, file);
  }
});
