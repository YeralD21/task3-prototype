import { RADIO_USAGE_NOTE } from "@/services/radio";
import type { RadioPage } from "@/types/dataset";
import RadioPlayer from "./RadioPlayer";

export type RadioState =
  | { status: "loading" }
  | { status: "unavailable"; message: string }
  | { status: "error"; message: string }
  | { status: "ready"; page: RadioPage };

export default function RadioView({
  state, index, onPrevious, onNext, onRetry,
}: {
  state: RadioState;
  index: number;
  onPrevious: () => void;
  onNext: () => void;
  onRetry: () => void;
}) {
  const item = state.status === "ready" ? state.page.items[index] : undefined;
  return (
    <div aria-busy={state.status === "loading"}>
      {state.status === "loading" && <p className="notice" role="status">Cargando Corpus Radio…</p>}
      {state.status === "unavailable" && <p className="notice">{state.message}</p>}
      {state.status === "error" && (
        <div className="notice" role="alert">
          <p>{state.message}</p>
          <button type="button" onClick={onRetry}>Reintentar</button>
        </div>
      )}
      {state.status === "ready" && !state.page.contains_audio && (
        <p className="notice">Este dataset no contiene audio.</p>
      )}
      {state.status === "ready" && state.page.contains_audio && !state.page.total && (
        <p className="notice">La copia local no contiene registros con referencias de audio.</p>
      )}
      {state.status === "ready" && item && (
        <>
          <p className="radio-note">{RADIO_USAGE_NOTE}</p>
          <RadioPlayer
            item={item}
            position={state.page.offset + index + 1}
            total={state.page.total}
            onPrevious={onPrevious}
            onNext={onNext}
          />
        </>
      )}
    </div>
  );
}
