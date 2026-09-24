import { COMPATIBILITY, TASK_LABELS } from "@/services/playbook";
import type { PlaybookTaskAssessment } from "@/types/dataset";

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="playbook-list">
      <h4>{title}</h4>
      <ul>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

export default function PlaybookTaskCard({ task }: { task: PlaybookTaskAssessment }) {
  const status = COMPATIBILITY[task.compatibility];
  const titleId = `playbook-${task.task}`;
  return (
    <article
      className={`playbook-card playbook-card--${task.compatibility}`}
      aria-labelledby={titleId}
    >
      <header className="playbook-card-heading">
        <h3 id={titleId}>{TASK_LABELS[task.task]}</h3>
        <span className={`playbook-badge playbook-badge--${task.compatibility}`}>
          <span aria-hidden="true">{status.symbol} </span>
          <span className="sr-only">Compatibilidad técnica: </span>
          {status.label}
        </span>
      </header>
      <p className="playbook-status-description">{status.description}</p>
      <List title="¿Por qué?" items={task.reasons} />
      <List title="Limitaciones" items={task.limitations} />
      <List title="Licencia y uso" items={task.license_notes} />
      <List title="Siguiente paso" items={task.next_steps} />
      <details className="playbook-requirements">
        <summary>Requisitos de datos para esta tarea</summary>
        <ul>
          {task.data_requirements.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </details>
    </article>
  );
}
