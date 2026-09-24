import { test } from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import { ApiError, semanticSearch, semanticErrorMessage } from "../src/services/api.ts";
import SemanticSearchResults from "../src/components/SemanticSearchResults.tsx";
import SemanticSearch from "../src/components/SemanticSearch.tsx";
import type { CorpusRecord, Dataset, SemanticSearchResponse } from "../src/types/dataset.ts";

const sample = JSON.parse(readFileSync(new URL("../../data/samples/canonical-development-sample.json", import.meta.url), "utf8")) as {
  dataset: Dataset; records: CorpusRecord[];
};
function renderResults(records: CorpusRecord[] = [sample.records[1]], score = 0.823) {
  const response: SemanticSearchResponse = {
    dataset_id: sample.dataset.id, query: "synthetic", items: records.map(record => ({ record, score })),
  };
  return renderToStaticMarkup(createElement(SemanticSearchResults, { state: { status: "ready", response } }));
}

test("semantic request sends POST JSON, limit and abort signal", async (t) => {
  const previous = process.env.NEXT_PUBLIC_API_URL;
  process.env.NEXT_PUBLIC_API_URL = "https://api.example.org";
  t.after(() => { if (previous === undefined) delete process.env.NEXT_PUBLIC_API_URL; else process.env.NEXT_PUBLIC_API_URL = previous; });
  const signal = new AbortController().signal;
  const fetch = t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    assert.equal(url, "https://api.example.org/api/v1/search/semantic");
    assert.equal(init.method, "POST");
    assert.equal(init.signal, signal);
    assert.deepEqual(init.headers, { "Content-Type": "application/json" });
    assert.deepEqual(JSON.parse(String(init.body)), { dataset_id: "id", query: "synthetic", limit: 10 });
    return Response.json({ query: "synthetic", dataset_id: "id", items: [] });
  });
  await semanticSearch("id", " synthetic ", 10, signal);
  assert.equal(fetch.mock.callCount(), 1);
});

test("blank queries never fetch and submit is disabled initially", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => Response.json({}));
  await assert.rejects(semanticSearch("id", "  "));
  assert.equal(fetch.mock.callCount(), 0);
  const html = renderToStaticMarkup(createElement(SemanticSearch, { dataset: sample.dataset }));
  assert.match(html, /type="submit" disabled/);
  assert.match(html, /for="semantic-query"/);
});

test("results render original text and traceability", () => {
  const html = renderResults();
  assert.ok(html.includes(sample.records[1].text));
  assert.ok(html.includes(sample.records[1].source_record_id));
  assert.ok(html.includes(sample.records[1].dataset_id));
});
test("optional translation is rendered only when present", () => {
  assert.ok(renderResults().includes(sample.records[1].translation!));
  assert.doesNotMatch(renderResults([{ ...sample.records[1], translation: null }]), /class="translation"/);
});
test("similarity uses a percentage and preserves negative values", () => {
  assert.match(renderResults(), /Similitud semántica: 82,3%/);
  assert.match(renderResults(undefined, -0.2), /-20%/);
});
for (const [detail, expected] of [
  ["Semantic index for dataset 'id' was not found.", /todavía no tiene un índice/],
  ["Semantic index for dataset 'id' is stale.", /desactualizado/],
] as const) {
  test("API translates semantic error: " + detail, async (t) => {
    const previous = process.env.NEXT_PUBLIC_API_URL;
    process.env.NEXT_PUBLIC_API_URL = "https://api.example.org";
    t.after(() => { if (previous === undefined) delete process.env.NEXT_PUBLIC_API_URL; else process.env.NEXT_PUBLIC_API_URL = previous; });
    t.mock.method(globalThis, "fetch", async () => Response.json({ detail }, { status: 409 }));
    try {
      await semanticSearch("id", "synthetic");
      assert.fail("Expected API error");
    } catch (error: unknown) {
      const message = semanticErrorMessage(error);
      assert.match(message, expected);
      const html = renderToStaticMarkup(createElement(SemanticSearchResults, { state: { status: "error", message } }));
      assert.match(html, /role="alert"/);
      assert.ok(!html.includes(detail));
    }
  });
}
test("generic and unavailable provider errors are useful and hide raw detail", () => {
  assert.match(semanticErrorMessage(new Error("private")), /Comprueba la conexión/);
  assert.match(semanticErrorMessage(new ApiError(503, "private")), /modelo.*no está disponible/);
});
test("loading is announced without showing stale results", () => {
  const html = renderToStaticMarkup(createElement(SemanticSearchResults, { state: { status: "loading", query: "synthetic" } }));
  assert.match(html, /aria-busy="true"/);
  assert.match(html, /Buscando registros/);
  assert.doesNotMatch(html, /record-card/);
});
test("empty results keep the submitted query visible", () => {
  const html = renderResults([]);
  assert.match(html, /No se encontraron registros/);
  assert.match(html, /synthetic/);
});
test("nonlocal dataset explains requirement without displaying a form", () => {
  const dataset = { ...sample.dataset, metadata: { available_locally: false } };
  const html = renderToStaticMarkup(createElement(SemanticSearch, { dataset }));
  assert.match(html, /copia local procesada/);
  assert.doesNotMatch(html, /<form/);
});
