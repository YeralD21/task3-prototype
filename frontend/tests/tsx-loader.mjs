// Compile JSX for the existing Node test runner; no new test dependency.
import { readFile } from "node:fs/promises";
import { loadBindings, transform } from "next/dist/build/swc/index.js";

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("@/")) {
    specifier = new URL("../src/" + specifier.slice(2), import.meta.url).href;
  }
  try {
    return await nextResolve(specifier, context);
  } catch (error) {
    if (specifier.startsWith(".") || specifier.startsWith("file:")) {
      for (const extension of [".ts", ".tsx"]) {
        try { return await nextResolve(specifier + extension, context); } catch {}
      }
    }
    throw error;
  }
}

export async function load(url, context, nextLoad) {
  if (url.endsWith(".tsx")) {
    const source = await readFile(new URL(url), "utf8");
    await loadBindings();
    const compiled = await transform(source, {
      jsc: {
        parser: { syntax: "typescript", tsx: true },
        transform: { react: { runtime: "automatic" } },
        target: "es2022",
      },
      module: { type: "es6" },
    });
    return {
      format: "module", shortCircuit: true,
      source: compiled.code,
    };
  }
  return nextLoad(url, context);
}
