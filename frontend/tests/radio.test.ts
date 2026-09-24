import { test } from "node:test";
import assert from "node:assert/strict";
import { createElement, isValidElement, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import {
  ApiError,
  RADIO_NOT_LOCAL,
  getDatasetRadio,
  radioAudioSource,
  radioErrorMessage,
} from "../src/services/api.ts";
import { AUDIO_STATUS_MESSAGES, RADIO_USAGE_NOTE, stepRadio } from "../src/services/radio.ts";
import RadioView, { type RadioState } from "../src/components/RadioView.tsx";
import RadioPlayer from "../src/components/RadioPlayer.tsx";
import CorpusRadio from "../src/components/CorpusRadio.tsx";
import type { CorpusRecord, Dataset, RadioItem, RadioPage } from "../src/types/dataset.ts";

const sample = JSON.parse(readFileSync(new URL("../../data/samples/canonical-development-sample.json", import.meta.url), "utf8")) as {
  dataset: Dataset; records: CorpusRecord[];
};
const DATASET = "common-voice-scripted-speech-qxp-26.0";
const record: CorpusRecord = {
  ...sample.records[0],
  id: `${DATASET}:clip-001.mp3`,
  dataset_id: DATASET,
  source_record_id: "clip-001.mp3",
  text: "[synthetic transcription 001]",
  translation: null,
  language: { name: "Quechua", iso_code: "qxp" },
  language_code: "qxp",
  language_variety: {
    id: "qxp", name: "Puno Quechua / Punu qhichwa", language_code: "qxp", region: "Puno",
    country: "Peru", glottocode: null, metadata: null,
  },
  audio_id: `${DATASET}:audio:clip-001.mp3`,
  provenance: {
    source_name: "Common Voice Scripted Speech 26.0 - Puno Quechua",
    source_url: "https://commonvoice.mozilla.org/en/datasets",
    organization: "Mozilla Foundation / Common Voice",
    original_dataset_id: "common-voice-scripted-speech-26.0-qxp",
    citation: null, retrieved_at: null,
    notes: "Loaded locally from validated.tsv row 2; the source dataset remains external.",
  },
  metadata: { split: "synthetic-split" },
};
const audioUrl = `/api/v1/datasets/${DATASET}/records/clip-001.mp3/audio`;
const item = (overrides: Partial<RadioItem> = {}): RadioItem => ({
  record, has_audio: true, audio_status: "available", audio_url: audioUrl, media_type: "audio/mpeg", ...overrides,
});
const page = (items: RadioItem[], overrides: Partial<RadioPage> = {}): RadioPage => ({
  dataset_id: DATASET, contains_audio: true, items, total: items.length, limit: 20, offset: 0, ...overrides,
});
const noop = () => {};
const renderView = (state: RadioState, index = 0) =>
  renderToStaticMarkup(createElement(RadioView, { state, index, onPrevious: noop, onNext: noop, onRetry: noop }));

function useApi(t: { after: (fn: () => void) => void }) {
  const previous = process.env.NEXT_PUBLIC_API_URL;
  process.env.NEXT_PUBLIC_API_URL = "https://api.example.org/";
  t.after(() => { if (previous === undefined) delete process.env.NEXT_PUBLIC_API_URL; else process.env.NEXT_PUBLIC_API_URL = previous; });
}
function elements(node: ReactNode, found: ReactElement<Record<string, unknown>>[] = []) {
  if (Array.isArray(node)) node.forEach((child) => elements(child, found));
  else if (isValidElement<Record<string, unknown>>(node)) {
    found.push(node);
    elements(node.props.children as ReactNode, found);
  }
  return found;
}

test("radio request uses the dataset endpoint with limit, offset and abort signal", async (t) => {
  useApi(t);
  const signal = new AbortController().signal;
  const fetch = t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    assert.equal(url, "https://api.example.org/api/v1/datasets/id%20x/radio?limit=20&offset=40");
    assert.equal(init.signal, signal);
    return Response.json(page([item()]));
  });
  const response = await getDatasetRadio("id x", 40, 20, signal);
  assert.equal(fetch.mock.callCount(), 1);
  assert.equal(response.items[0].record.source_record_id, "clip-001.mp3");
});

test("loading is announced before any player appears", (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => new Promise<Response>(() => {}));
  const html = renderView({ status: "loading" });
  assert.match(html, /aria-busy="true"/);
  assert.match(html, /Cargando Corpus Radio/);
  assert.doesNotMatch(html, /<audio/);
  assert.match(renderToStaticMarkup(createElement(CorpusRadio, { dataset: sample.dataset })), /Cargando Corpus Radio/);
  assert.equal(fetch.mock.callCount(), 0);
});

test("text-only dataset says it contains no audio and never invents a player", () => {
  const html = renderView({ status: "ready", page: page([], { contains_audio: false }) });
  assert.match(html, /Este dataset no contiene audio\./);
  assert.doesNotMatch(html, /<audio|Registro 1/);
  assert.match(renderView({ status: "ready", page: page([]) }), /no contiene registros con referencias de audio/);
});

test("audio element uses native controls, the controlled endpoint and no autoplay", (t) => {
  useApi(t);
  const html = renderView({ status: "ready", page: page([item()]) });
  assert.match(html, /<audio class="radio-audio" controls="" preload="metadata"/);
  assert.ok(html.includes(`src="https://api.example.org${audioUrl}"`));
  assert.match(html, /controlsList="nodownload"/);
  assert.doesNotMatch(html, /autoplay|download=/i);
  assert.match(html, /aria-describedby="radio-transcript"/);
  assert.ok(html.includes(RADIO_USAGE_NOTE));
});

test("only controlled audio endpoint paths become sources", (t) => {
  useApi(t);
  assert.equal(radioAudioSource(audioUrl), "https://api.example.org" + audioUrl);
  for (const bad of [
    "https://evil.example/clip.mp3", "/api/v1/datasets/x/records/a/../../audio",
    "C:\\data\\raw\\clip.mp3", "/api/v1/datasets/x/records/a/audio?path=/etc", null,
  ])
    assert.equal(radioAudioSource(bad), null, String(bad));
});

test("transcription, language, variety and source ids are shown with the audio", (t) => {
  useApi(t);
  const html = renderView({ status: "ready", page: page([item()]) });
  assert.ok(html.includes("[synthetic transcription 001]"));
  assert.match(html, /id="radio-transcript"/);
  assert.match(html, /Quechua · qxp/);
  assert.ok(html.includes("Puno Quechua / Punu qhichwa"));
  assert.ok(html.includes("clip-001.mp3"));
  assert.ok(html.includes("synthetic-split"));
  assert.match(html, /audio\/mpeg/);
});

test("translation is optional", (t) => {
  useApi(t);
  assert.doesNotMatch(renderView({ status: "ready", page: page([item()]) }), /TRADUCCIÓN/);
  const translated = item({ record: { ...record, translation: "[synthetic translation]", translation_language: { name: "Spanish", iso_code: "es" } } });
  const html = renderView({ status: "ready", page: page([translated]) });
  assert.match(html, /TRADUCCIÓN · Spanish/);
  assert.ok(html.includes("[synthetic translation]"));
});

test("previous and next move across records and pages, disabled at the ends", () => {
  assert.deepEqual(stepRadio({ offset: 0, index: 0 }, "next", 45, 20), { offset: 0, index: 1 });
  assert.deepEqual(stepRadio({ offset: 0, index: 19 }, "next", 45, 20), { offset: 20, index: 0 });
  assert.deepEqual(stepRadio({ offset: 20, index: 0 }, "previous", 45, 20), { offset: 0, index: 19 });
  assert.equal(stepRadio({ offset: 0, index: 0 }, "previous", 45, 20), null);
  assert.equal(stepRadio({ offset: 40, index: 4 }, "next", 45, 20), null);

  const calls: string[] = [];
  const tree = RadioPlayer({
    item: item(), position: 1, total: 3,
    onPrevious: () => calls.push("previous"), onNext: () => calls.push("next"),
  });
  const buttons = elements(tree).filter((node) => node.type === "button");
  assert.deepEqual(buttons.map((button) => button.props.disabled), [true, false]);
  (buttons[1].props.onClick as () => void)();
  assert.deepEqual(calls, ["next"]);
  const html = renderView({ status: "ready", page: page([item(), item(), item()]) }, 2);
  assert.match(html, /Registro 3 de 3/);
  assert.match(html, /Registro anterior/);
  assert.match(html, /aria-live="polite"/);
});

test("missing audio file keeps the record visible with a clear message", () => {
  const html = renderView({ status: "ready", page: page([item({ audio_status: "missing_file", audio_url: null })]) });
  assert.ok(html.includes(AUDIO_STATUS_MESSAGES.missing_file));
  assert.equal(AUDIO_STATUS_MESSAGES.missing_file, "El registro referencia audio, pero el archivo no está disponible localmente.");
  assert.doesNotMatch(html, /<audio/);
  assert.ok(html.includes("[synthetic transcription 001]"));
});

test("expected and generic errors hide raw details", () => {
  assert.equal(radioErrorMessage(new ApiError(409, "Dataset 'x' is not available locally.")), RADIO_NOT_LOCAL);
  assert.match(radioErrorMessage(new ApiError(404, "Dataset 'x' was not found.")), /no figura en el catálogo/);
  const message = radioErrorMessage(new TypeError("Failed to fetch C:\\data\\raw"));
  assert.match(message, /No pudimos cargar Corpus Radio/);
  const html = renderView({ status: "error", message });
  assert.match(html, /role="alert"/);
  assert.match(html, /Reintentar/);
  assert.doesNotMatch(html, /data\\raw|Failed to fetch/);
  assert.doesNotMatch(renderView({ status: "unavailable", message: RADIO_NOT_LOCAL }), /Reintentar/);
});

test("provenance is shown alongside the audio", (t) => {
  useApi(t);
  const html = renderView({ status: "ready", page: page([item()]) });
  assert.ok(html.includes("Mozilla Foundation / Common Voice"));
  assert.ok(html.includes("common-voice-scripted-speech-26.0-qxp"));
  assert.ok(html.includes('href="https://commonvoice.mozilla.org/en/datasets"'));
  assert.ok(html.includes("Loaded locally from validated.tsv row 2"));
});

test("Radio sources are typed without any", () => {
  for (const file of [
    "../src/services/radio.ts", "../src/components/CorpusRadio.tsx", "../src/components/RadioView.tsx",
    "../src/components/RadioPlayer.tsx", "../src/services/api.ts", "../src/types/dataset.ts",
  ]) {
    const source = readFileSync(new URL(file, import.meta.url), "utf8");
    assert.doesNotMatch(source, /:\s*any\b|\bas\s+any\b|<any>|\bany\[\]/, file);
  }
});
