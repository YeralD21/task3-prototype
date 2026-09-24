import type { DatasetPlaybook } from "@/types/dataset";
import PlaybookContext from "./PlaybookContext";
import PlaybookTaskCard from "./PlaybookTaskCard";

export type PlaybookState =
  | { status: "loading" }
  | { status: "missing"; message: string }
  | { status: "error"; message: string }
  | { status: "ready"; playbook: DatasetPlaybook };

export default function PlaybookView({
  state, onRetry,
}: { state: PlaybookState; onRetry: () => void }) {
  return (
    <div aria-live="polite" aria-busy={state.status === "loading"}>
      {state.status === "loading" && <p className="notice">Cargando el Playbook…</p>}
      {state.status === "missing" && <p className="notice">{state.message}</p>}
      {state.status === "error" && (
        <div className="notice" role="alert">
          <p>{state.message}</p>
          <button type="button" onClick={onRetry}>Reintentar</button>
        </div>
      )}
      {state.status === "ready" && (
        <>
          <p className="playbook-disclaimer">{state.playbook.disclaimer}</p>
          <PlaybookContext playbook={state.playbook} />
          <div className="playbook-grid">
            {state.playbook.tasks.map((task) => (
              <PlaybookTaskCard key={task.task} task={task} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
