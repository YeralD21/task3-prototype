"use client";

import { useEffect, useState } from "react";
import { ApiError, RADIO_PAGE_SIZE, getDatasetRadio, radioErrorMessage } from "@/services/api";
import { stepRadio, type RadioPosition } from "@/services/radio";
import type { Dataset } from "@/types/dataset";
import RadioView, { type RadioState } from "./RadioView";

export default function CorpusRadio({ dataset }: { dataset: Dataset }) {
  const [state, setState] = useState<RadioState>({ status: "loading" });
  const [position, setPosition] = useState<RadioPosition>({ offset: 0, index: 0 });
  const [attempt, setAttempt] = useState(0);
  const { offset } = position;

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading" });
    getDatasetRadio(dataset.id, offset, RADIO_PAGE_SIZE, controller.signal)
      .then((page) => {
        if (!controller.signal.aborted) setState({ status: "ready", page });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const message = radioErrorMessage(error);
        const expected = error instanceof ApiError && (error.status === 404 || error.status === 409);
        setState(expected ? { status: "unavailable", message } : { status: "error", message });
      });
    return () => controller.abort();
  }, [dataset.id, offset, attempt]);

  const step = (direction: "previous" | "next") => {
    if (state.status !== "ready") return;
    const next = stepRadio(position, direction, state.page.total, RADIO_PAGE_SIZE);
    if (next) setPosition(next);
  };

  return (
    <section className="explorer" id="radio" aria-labelledby="radio-title">
      <div className="explorer-title">
        <div>
          <p className="eyebrow">CORPUS RADIO</p>
          <h2 id="radio-title">Corpus Radio</h2>
        </div>
        <p>
          Escucha registros con audio disponible localmente junto a su transcripción completa.
          No hay sincronización palabra por palabra.
        </p>
      </div>
      <RadioView
        state={state}
        index={position.index}
        onPrevious={() => step("previous")}
        onNext={() => step("next")}
        onRetry={() => setAttempt((value) => value + 1)}
      />
    </section>
  );
}
