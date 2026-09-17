import Link from "next/link";
export default function Header() {
  return (
    <header className="header">
      <Link className="brand" href="/">
        <span className="mark" aria-hidden="true">
          ◈
        </span>{" "}
        Lenguas · Recursos
      </Link>
      <nav aria-label="Navegación principal">
        <Link href="/">Explorar catálogo</Link>
      </nav>
      <span className="edition">PROTOTIPO ABIERTO</span>
    </header>
  );
}
