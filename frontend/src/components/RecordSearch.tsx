import type { Language } from "@/types/dataset";

export default function RecordSearch({
  query,
  language,
  languages,
  onQueryChange,
  onLanguageChange,
  onSubmit,
}: {
  query: string;
  language: string;
  languages: Language[] | null;
  onQueryChange: (value: string) => void;
  onLanguageChange: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <form
      className="record-search"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <label>
        Buscar dentro del corpus
        <input
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Texto o traducción"
        />
      </label>
      <label>
        Idioma
        <select
          value={language}
          onChange={(event) => onLanguageChange(event.target.value)}
        >
          <option value="">Todos los idiomas</option>
          {languages?.map((item) => (
            <option
              key={item.iso_code ?? item.name}
              value={item.iso_code ?? item.name}
            >
              {item.name}
              {item.iso_code ? ` (${item.iso_code})` : ""}
            </option>
          ))}
        </select>
      </label>
      <button type="submit">Buscar</button>
    </form>
  );
}
