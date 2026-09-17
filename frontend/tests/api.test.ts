import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  ApiError,
  getDataset,
  listDatasets,
  queryString,
} from "../src/services/api.ts";
import {
  availability,
  number,
  permission,
  safeUrl,
  text,
  values,
} from "../src/services/display.ts";

test("both catalog manifests can be presented without implying download rights", () => {
  const readManifest = (path: string) => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
  const commonVoice = readManifest("../../datasets/registry/quechua/common-voice-puno-quechua.json");
  const americas = readManifest("../../datasets/registry/aymara/americasnlp-aymara-spanish.json");
  assert.match(commonVoice.name, /Common Voice/);
  assert.equal(commonVoice.languages[0].iso_code, "qxp");
  assert.equal(values(commonVoice.modalities), "Audio · Texto");
  assert.equal(permission(commonVoice.license.redistribution), "No");
  assert.ok(safeUrl(commonVoice.source_url));
  assert.match(americas.name, /AmericasNLP/);
  assert.equal(americas.languages[0].iso_code, "aym");
  assert.equal(values(americas.modalities), "Texto paralelo");
  assert.equal(americas.license.name, null);
  assert.equal(number(americas.record_count), "No especificado");
  for (const dataset of [commonVoice, americas]) {
    assert.match(availability(dataset.metadata), /fuente oficial/);
  }
});

test("unknown values and zero are represented honestly", () => {
  assert.equal(text(null), "No especificado");
  assert.equal(values(null), "No especificado");
  assert.equal(number(null), "No especificado");
  assert.equal(number(0), "0");
  assert.equal(permission(null), "No especificado");
  assert.equal(permission(false), "No");
  assert.equal(availability(null), "Disponibilidad local no especificada");
  assert.match(
    availability({ cataloged: true, available_locally: false }),
    /fuente oficial/,
  );
});
test("official links allow only HTTP and HTTPS", () => {
  assert.equal(safeUrl("javascript:alert(1)"), null);
  assert.equal(safeUrl("file:///private"), null);
  assert.equal(safeUrl(null), null);
  assert.equal(safeUrl("https://example.org"), "https://example.org/");
});
test("filters are encoded for the backend", () => {
  assert.equal(
    queryString({ language: "aym", modality: "parallel_text", task: "" }),
    "language=aym&modality=parallel_text",
  );
  assert.equal(queryString({ language: "qxp" }), "language=qxp");
});
test("API uses configured URL, keeps errors and encodes identifiers", async (t) => {
  const previous = process.env.NEXT_PUBLIC_API_URL;
  process.env.NEXT_PUBLIC_API_URL = "https://api.example.org/";
  t.after(() => {
    if (previous === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = previous;
  });
  const calls: string[] = [];
  t.mock.method(globalThis, "fetch", async (url: string) => {
    calls.push(url);
    return new Response(JSON.stringify([]), { status: 200 });
  });
  await listDatasets({ language: "aym", task: "machine_translation" });
  await getDataset("id/with space");
  assert.equal(
    calls[0],
    "https://api.example.org/api/v1/datasets?language=aym&task=machine_translation",
  );
  assert.equal(
    calls[1],
    "https://api.example.org/api/v1/datasets/id%2Fwith%20space",
  );
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response("", { status: 404 }),
  );
  await assert.rejects(
    getDataset("missing"),
    (error: unknown) => error instanceof ApiError && error.status === 404,
  );
});
