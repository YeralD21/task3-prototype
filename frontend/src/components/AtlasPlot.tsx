import type { KeyboardEvent } from "react";
import { ATLAS_PLOT, type ScaledPoint, truncate } from "@/services/atlas";
import { recordTranslation, text } from "@/services/display";

interface AtlasPlotProps {
  points: ScaledPoint[];
  selectedId: string | null;
  hoveredId: string | null;
  onSelect: (recordId: string) => void;
  onHover: (recordId: string | null) => void;
  onKeyDown: (event: KeyboardEvent<SVGSVGElement>) => void;
}

function Tooltip({ scaled }: { scaled: ScaledPoint }) {
  const { point, cx, cy } = scaled;
  const translation = recordTranslation(point.record.translation);
  const horizontal = cx > ATLAS_PLOT.width * 0.6 ? " atlas-tooltip--left" : "";
  const vertical = cy > ATLAS_PLOT.height * 0.6 ? " atlas-tooltip--up" : "";
  return (
    <div
      className={"atlas-tooltip" + horizontal + vertical}
      role="tooltip"
      style={{
        left: `${(cx / ATLAS_PLOT.width) * 100}%`,
        top: `${(cy / ATLAS_PLOT.height) * 100}%`,
      }}
    >
      <p className="atlas-tooltip-text">{truncate(point.record.text, 120)}</p>
      {translation && <p className="atlas-tooltip-translation">{truncate(translation, 100)}</p>}
      <p className="atlas-tooltip-meta">
        {text(point.record.language?.name)} · {point.source_record_id}
      </p>
    </div>
  );
}

export default function AtlasPlot({
  points, selectedId, hoveredId, onSelect, onHover, onKeyDown,
}: AtlasPlotProps) {
  const hovered = points.find(({ point }) => point.record_id === hoveredId) ?? null;
  const selected = points.find(({ point }) => point.record_id === selectedId) ?? null;
  const regular = points.filter(
    ({ point }) => point.record_id !== hoveredId && point.record_id !== selectedId,
  );
  const circle = (scaled: ScaledPoint, state: "normal" | "hover" | "selected") => (
    <circle
      key={scaled.point.record_id}
      className={`atlas-point atlas-point--${state}`}
      data-record-id={scaled.point.record_id}
      cx={scaled.cx}
      cy={scaled.cy}
      r={state === "normal" ? 5 : state === "hover" ? 7 : 7.5}
      onMouseEnter={() => onHover(scaled.point.record_id)}
      onClick={() => onSelect(scaled.point.record_id)}
    />
  );
  return (
    <div className="atlas-plot">
      <svg
        viewBox={`0 0 ${ATLAS_PLOT.width} ${ATLAS_PLOT.height}`}
        role="group"
        aria-labelledby="atlas-svg-title"
        aria-describedby="atlas-svg-desc atlas-keyboard-help"
        tabIndex={0}
        onKeyDown={onKeyDown}
        onMouseLeave={() => onHover(null)}
      >
        <title id="atlas-svg-title">Mapa 2D del corpus</title>
        <desc id="atlas-svg-desc">
          {points.length} puntos; cada uno representa un registro del corpus.
          El registro seleccionado se describe en el panel de detalle.
        </desc>
        <rect className="atlas-frame" x="0.5" y="0.5"
          width={ATLAS_PLOT.width - 1} height={ATLAS_PLOT.height - 1} rx="6" />
        <g aria-hidden="true">
          {regular.map((scaled) => circle(scaled, "normal"))}
          {hovered && hovered !== selected && circle(hovered, "hover")}
          {selected && (
            <>
              <circle className="atlas-ring" cx={selected.cx} cy={selected.cy} r="14" />
              {circle(selected, "selected")}
            </>
          )}
        </g>
      </svg>
      {hovered && <Tooltip scaled={hovered} />}
    </div>
  );
}
