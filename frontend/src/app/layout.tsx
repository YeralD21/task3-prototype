import type { Metadata } from "next";
import Header from "@/components/Header";
import "./globals.css";
export const metadata: Metadata = {
  title: "Recursos lingüísticos indígenas",
  description: "Catálogo de datasets de Quechua y Aymara.",
};
export default function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>
        <a className="skip" href="#contenido">
          Saltar al contenido
        </a>
        <Header />
        <main id="contenido">{children}</main>
        <footer>
          task3-prototype{" "}
          <span>Datos con contexto. Lenguas con identidad.</span>
        </footer>
      </body>
    </html>
  );
}
