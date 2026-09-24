"use client";

import { useEffect, useState } from "react";
import { ApiError, getDatasetPlaybook, playbookErrorMessage } from "@/services/api";
import type { Dataset } from "@/types/dataset";
import PlaybookView, { type PlaybookState } from "./PlaybookView";

export default function DatasetPlaybook({ dataset }: { dataset: Dataset }) {
  const [state, setState] = useState<PlaybookState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading" });
    getDatasetPlaybook(dataset.id, controller.signal)
      .then((playbook) => {
        if (!controller.signal.aborted) setState({ status: "ready", playbook });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const message = playbookErrorMessage(error);
        setState(
          error instanceof ApiError && error.status === 404
            ? { status: "missing", message }
            : { status: "error", message },
        );
      });
    return () => controller.abort();
  }, [dataset.id, attempt]);

  return (
    <section className="explorer" id="playbook" aria-labelledby="playbook-title">
      <div className="explorer-title">
        <div>
          <p className="eyebrow">DATASET PLAYBOOK</p>
          <h2 id="playbook-title">Playbook</h2>
        </div>
        <p>
          ¿Para qué puedo utilizar este dataset? Reglas transparentes sobre la metadata
          registrada, sin puntuaciones ni rankings.
        </p>
      </div>
      <PlaybookView state={state} onRetry={() => setAttempt((value) => value + 1)} />
    </section>
  );
}
