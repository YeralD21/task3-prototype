export default function Pagination({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}) {
  if (!total) return null;
  const start = offset + 1;
  const end = Math.min(offset + limit, total);
  return (
    <nav className="pagination" aria-label="Paginación de registros">
      <button
        className="secondary"
        disabled={offset === 0}
        onClick={() => onChange(Math.max(0, offset - limit))}
      >
        Anterior
      </button>
      <span aria-live="polite">
        {start}–{end} de {total}
      </span>
      <button
        className="secondary"
        disabled={offset + limit >= total}
        onClick={() => onChange(offset + limit)}
      >
        Siguiente
      </button>
    </nav>
  );
}
