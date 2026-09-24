import { test } from "node:test";
import assert from "node:assert/strict";
import { createElement, isValidElement, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import {
  ApiError,
  ATLAS_MISSING,
  ATLAS_NO_INDEX,
  ATLAS_NOT_LOCAL,
  ATLAS_STALE,
  atlasErrorMessage,
  getDatasetAtlas,
} from "../src/services/api.ts";
import {
  ATLAS_PLOT,
  readingOrder,
  scaleAtlasPoints,
  stepSelection,
  truncate,
} from "../src/services/atlas.ts";
import AtlasView, { type AtlasState } from "../src/components/AtlasView.tsx";
import AtlasPlot from "../src/components/AtlasPlot.tsx";
import AtlasExplorer, { ATLAS_EXPLANATION } from "../src/components/AtlasExplorer.tsx";
import type { AtlasPoint, AtlasResponse, CorpusRecord, Dataset } from "../src/types/dataset.ts";

const sample = JSON.parse(readFileSync(new URL("../../data/samples/canonical-development-sample.json", import.meta.url), "utf8")) as {
  dataset: Dataset; records: CorpusRecord[];
};
const withTranslation = sample.records.find((record) => record.translation)!;
const withoutTranslation = { ...sample.records[0], translation: null };

function point(record: CorpusRecord, x: number, y: number): AtlasPoint {
  return { record_id: record.id, dataset_id: record.dataset_id, source_record_id: record.source_record_id, x, y, record };
}
const points: AtlasPoint[] = [
  point(withoutTranslation, -2.5, 1),
  point(withTranslation, 4, -3),
  point(sample.records[2], 0.5, 6),
];
function atlasResponse(items: AtlasPoint[] = points, overrides: Partial<AtlasResponse> = {}): AtlasResponse {
  return {
    dataset_id: sample.dataset.id, reducer: "pca", created_at: "2026-09-24T13:08:00+00:00",
    source_embedding_model: "synthetic-model", source_embedding_dimension: 16,
    parameters: { n_components: 2 }, diagnostics: { explained_variance_ratio_total: 0.918 },
    total_records: 10, returned_records: items.length, limit: 3,
    sampling: { applied: true, method: "sha256_record_id" }, items, ...overrides,
  };
}
const noop = () => {};
function renderView(state: AtlasState, selectedId: string | null = null, hoveredId: string | null = null) {
  return renderToStaticMarkup(createElement(AtlasView, {
    state, selectedId, hoveredId, onSelect: noop, onHover: noop, onRetry: noop,
  }));
}
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

// --- API client ---------------------------------------------------------------

test("atlas request uses the dataset endpoint, encoded id, limit and abort signal", async (t) => {
  useApi(t);
  const signal = new AbortController().signal;
  const urls: string[] = [];
  const fetch = t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    urls.push(url);
    assert.equal(init.signal, signal);
    assert.equal(init.cache, "no-store");
    assert.equal(init.method, undefined);
    return Response.json(atlasResponse());
  });
  const response = await getDatasetAtlas("id x", 500, signal);
  await getDatasetAtlas("id", undefined, signal);
  assert.deepEqual(urls, [
    "https://api.example.org/api/v1/datasets/id%20x/atlas?limit=500",
    "https://api.example.org/api/v1/datasets/id/atlas?limit=1000",
  ]);
  assert.equal(fetch.mock.callCount(), 2);
  assert.equal(response.items[0].record.source_record_id, points[0].source_record_id);
});

// --- Escalado -----------------------------------------------------------------

const { width, height, padding } = ATLAS_PLOT;
const inside = ({ cx, cy }: { cx: number; cy: number }) =>
  cx >= padding - 1e-9 && cx <= width - padding + 1e-9 && cy >= padding - 1e-9 && cy <= height - padding + 1e-9;

test("scaling keeps negative coordinates inside the padded frame and preserves proportions", () => {
  const scaled = scaleAtlasPoints(points);
  assert.equal(scaled.length, 3);
  assert.ok(scaled.every(inside));
  const [a, b, c] = scaled;
  const ratio = (p: { x: number; y: number }, q: { x: number; y: number }) => Math.hypot(p.x - q.x, p.y - q.y);
  const svgRatio = (p: { cx: number; cy: number }, q: { cx: number; cy: number }) => Math.hypot(p.cx - q.cx, p.cy - q.cy);
  assert.ok(Math.abs(svgRatio(a, b) / svgRatio(a, c) - ratio(points[0], points[1]) / ratio(points[0], points[2])) < 1e-3);
  assert.ok(b.cx > a.cx, "larger x goes right");
  assert.ok(c.cy < b.cy, "larger y goes up");
  assert.equal(Math.max(...scaled.map((p) => p.cy)) - Math.min(...scaled.map((p) => p.cy)), height - 2 * padding);
});

test("scaling handles constant axes, a single point and does not mutate input", () => {
  const constantX = [point(sample.records[0], 3, -1), point(sample.records[1], 3, 5)];
  const constantY = [point(sample.records[0], -9, 2), point(sample.records[1], 7, 2)];
  const frozen = constantX.map((item) => Object.freeze({ ...item }));
  const scaledX = scaleAtlasPoints(frozen);
  assert.ok(scaledX.every((p) => p.cx === width / 2));
  assert.ok(scaledX.every(inside));
  const scaledY = scaleAtlasPoints(constantY);
  assert.ok(scaledY.every((p) => p.cy === height / 2));
  assert.deepEqual(scaledY.map((p) => p.cx), [padding, width - padding]);
  const single = scaleAtlasPoints([point(sample.records[0], -123, 456)]);
  assert.deepEqual([single[0].cx, single[0].cy], [width / 2, height / 2]);
  assert.deepEqual(frozen.map((p) => [p.x, p.y]), [[3, -1], [3, 5]]);
  assert.deepEqual(scaleAtlasPoints([]), []);
});

// --- Render de estados ------------------------------------------------------------

test("loading is announced and does not render a map", () => {
  const html = renderView({ status: "loading" });
  assert.match(html, /aria-busy="true"/);
  assert.match(html, /Cargando el Atlas/);
  assert.doesNotMatch(html, /<svg/);
});

test("explorer explains the map, labels the limit and waits for the user before fetching", (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => Response.json({}));
  const html = renderToStaticMarkup(createElement(AtlasExplorer, { dataset: sample.dataset }));
  assert.ok(html.includes(ATLAS_EXPLANATION));
  assert.match(html, /for="atlas-limit"/);
  assert.match(html, /<option value="1000" selected="">1000<\/option>/);
  assert.doesNotMatch(html, /value="5000"/);
  assert.match(html, /Abrir Atlas Vivo/);
  assert.equal(fetch.mock.callCount(), 0);
});

test("nonlocal dataset explains the requirement without controls", () => {
  const dataset = { ...sample.dataset, metadata: { available_locally: false } };
  const html = renderToStaticMarkup(createElement(AtlasExplorer, { dataset }));
  assert.ok(html.includes(ATLAS_NOT_LOCAL));
  assert.doesNotMatch(html, /atlas-limit|Abrir Atlas/);
});

test("ready atlas renders one point per record, accessible svg and discreet metadata", () => {
  const html = renderView({ status: "ready", response: atlasResponse() });
  assert.equal(html.match(/class="atlas-point /g)?.length, points.length);
  assert.match(html, /<title id="atlas-svg-title">/);
  assert.match(html, /aria-describedby="atlas-svg-desc atlas-keyboard-help"/);
  assert.match(html, /tabindex="0"/);
  assert.match(html, /Reductor: PCA/);
  assert.match(html, /3 de 10 puntos visibles \(muestra reproducible\)/);
  assert.match(html, /91[.,]8\s?%/);
  assert.match(html, /Selecciona un punto del mapa/);
  assert.doesNotMatch(html, /atlas-tooltip|atlas-ring/);
});

test("UMAP atlas does not claim explained variance", () => {
  const html = renderView({ status: "ready", response: atlasResponse(points, { reducer: "umap" }) });
  assert.match(html, /Reductor: UMAP/);
  assert.doesNotMatch(html, /Varianza/);
});

test("empty atlas response shows a clear message", () => {
  const html = renderView({ status: "ready", response: atlasResponse([], { total_records: 0 }) });
  assert.match(html, /no contiene puntos/);
  assert.doesNotMatch(html, /<svg/);
});

// --- Hover y selección ----------------------------------------------------------

test("clicking and hovering a point report its record id", () => {
  const selected: (string | null)[] = [];
  const hovered: (string | null)[] = [];
  const tree = AtlasPlot({
    points: scaleAtlasPoints(points), selectedId: null, hoveredId: null,
    onSelect: (id) => selected.push(id), onHover: (id) => hovered.push(id), onKeyDown: noop,
  });
  const circles = elements(tree).filter((node) => node.type === "circle");
  assert.equal(circles.length, points.length);
  const target = circles.find((node) => node.props["data-record-id"] === points[1].record_id)!;
  (target.props.onClick as () => void)();
  (target.props.onMouseEnter as () => void)();
  const svg = elements(tree).find((node) => node.type === "svg")!;
  (svg.props.onMouseLeave as () => void)();
  assert.deepEqual(selected, [points[1].record_id]);
  assert.deepEqual(hovered, [points[1].record_id, null]);
});

test("selected point is marked by size and ring and fully described outside the svg", () => {
  const selected = points[1];
  const html = renderView({ status: "ready", response: atlasResponse() }, selected.record_id);
  assert.match(html, /atlas-point--selected/);
  assert.match(html, /class="atlas-ring"/);
  const details = html.slice(html.indexOf("<aside"));
  assert.ok(details.includes(selected.record.text));
  assert.ok(details.includes(selected.record.translation!));
  assert.ok(details.includes(selected.source_record_id));
  assert.ok(details.includes(selected.dataset_id));
  assert.ok(details.includes(selected.record.language!.name));
  assert.match(details, /Audio/);
  assert.match(details, /Dataset original/);
  assert.match(details, /Coordenadas en el mapa/);
  assert.match(details, /Punto 3 de 3/);
  assert.match(details, /aria-live="polite"/);
});

test("hover tooltip is brief and shows translation only when present", () => {
  const long = { ...withTranslation, text: "palabra ".repeat(80) };
  const render = (item: AtlasPoint) => renderToStaticMarkup(createElement(AtlasPlot, {
    points: scaleAtlasPoints([item, points[2]]), selectedId: null, hoveredId: item.record_id,
    onSelect: noop, onHover: noop, onKeyDown: noop,
  }));
  const translated = render(point(long, 0, 0));
  assert.match(translated, /role="tooltip"/);
  assert.ok(translated.includes(withTranslation.translation!));
  assert.ok(translated.includes(withTranslation.source_record_id));
  assert.ok(translated.includes(withTranslation.language!.name));
  assert.ok(!translated.includes(long.text.trim()), "long text is truncated");
  assert.match(translated, /…/);
  const plain = render(points[0]);
  assert.match(plain, /role="tooltip"/);
  assert.doesNotMatch(plain, /atlas-tooltip-translation/);
});

test("optional translation is omitted from the details panel when absent", () => {
  const html = renderView({ status: "ready", response: atlasResponse() }, points[0].record_id);
  assert.doesNotMatch(html.slice(html.indexOf("<aside")), /class="translation"/);
});

test("keyboard and button navigation follow left-to-right order", () => {
  const order = readingOrder(points);
  assert.deepEqual(order, [points[0], points[2], points[1]].map((p) => p.record_id));
  assert.equal(stepSelection(order, null, "next"), order[0]);
  assert.equal(stepSelection(order, null, "previous"), order[2]);
  assert.equal(stepSelection(order, order[0], "next"), order[1]);
  assert.equal(stepSelection(order, order[2], "next"), order[2]);
  assert.equal(stepSelection(order, order[0], "previous"), order[0]);
  assert.equal(stepSelection(order, order[1], "last"), order[2]);
  assert.equal(stepSelection([], null, "next"), null);
  assert.equal(truncate("  a   b  ", 10), "a b");
});

// --- Errores ------------------------------------------------------------------------

for (const [detail, expected] of [
  ["Atlas for dataset 'id' was not found.", ATLAS_MISSING],
  ["Atlas for dataset 'id' is stale: canonical records changed.", ATLAS_STALE],
  ["Atlas for dataset 'id' is stale: embeddings changed.", ATLAS_STALE],
  ["Semantic index for dataset 'id' was not found; the atlas cannot be verified.", ATLAS_NO_INDEX],
  ["Dataset 'id' is not available locally.", ATLAS_NOT_LOCAL],
] as const) {
  test("API conflict is translated without raw detail: " + detail, async (t) => {
    useApi(t);
    t.mock.method(globalThis, "fetch", async () => Response.json({ detail }, { status: 409 }));
    const error = await getDatasetAtlas("id").then(() => assert.fail("expected error"), (e: unknown) => e);
    const message = atlasErrorMessage(error);
    assert.equal(message, expected);
    const html = renderView({ status: "unavailable", message });
    assert.ok(html.includes(expected));
    assert.ok(!html.includes(detail));
    assert.doesNotMatch(html, /Reintentar/);
  });
}

test("generic errors are friendly, hide internals and offer a retry", () => {
  const message = atlasErrorMessage(new ApiError(500, "Atlas for dataset 'id' is invalid."));
  assert.equal(atlasErrorMessage(new TypeError("Failed to fetch at line 3")), message);
  assert.match(message, /No pudimos cargar el Atlas/);
  const html = renderView({ status: "error", message });
  assert.match(html, /role="alert"/);
  assert.match(html, /Reintentar/);
  assert.doesNotMatch(html, /invalid|line 3/);
  assert.match(atlasErrorMessage(new ApiError(404, "Dataset 'id' was not found.")), /ya no está disponible/);
});

test("Atlas sources are typed without any", () => {
  for (const file of [
    "../src/services/atlas.ts", "../src/components/AtlasExplorer.tsx", "../src/components/AtlasView.tsx",
    "../src/components/AtlasPlot.tsx", "../src/components/AtlasPointDetails.tsx",
    "../src/services/api.ts", "../src/types/dataset.ts",
  ]) {
    const source = readFileSync(new URL(file, import.meta.url), "utf8");
    assert.doesNotMatch(source, /:\s*any\b|\bas\s+any\b|<any>|\bany\[\]/, file);
  }
});
