import { createHash } from "node:crypto";
import { copyFileSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const root = fileURLToPath(new URL(".", import.meta.url));
const outDir = resolve(root, "../backend/ncc_server/static");

function listFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? listFiles(path) : [path];
  });
}

/**
 * FastAPI only serves "/", "/assets/*" and "/api/*". The installed PWA
 * therefore starts at /assets/app.html, which the service worker under
 * /assets/ may control (see DECISIONS.md, P-01/P-02). This plugin copies the
 * built index.html there and writes the precache list into sw.js.
 */
function appShell(): Plugin {
  return {
    name: "ncc-app-shell",
    apply: "build",
    closeBundle() {
      const assets = join(outDir, "assets");
      copyFileSync(join(outDir, "index.html"), join(assets, "app.html"));
      const files = listFiles(assets)
        .map((file) => "/" + relative(outDir, file).split(sep).join("/"))
        .filter((url) => !url.endsWith("/sw.js") && !url.endsWith(".map") && !url.endsWith(".woff"));
      const hash = createHash("sha256");
      for (const url of files) hash.update(url).update(readFileSync(join(outDir, url)));
      const swPath = join(assets, "sw.js");
      const source = readFileSync(swPath, "utf8")
        .replace("self.__NCC_PRECACHE__", JSON.stringify(files))
        .replace("self.__NCC_VERSION__", JSON.stringify(hash.digest("hex").slice(0, 12)));
      writeFileSync(swPath, source);
    },
  };
}

/**
 * The overview is the usual first view. Preload its chunk and the two fonts
 * the headline needs, so the browser fetches them with the entry instead of
 * after it (no waterfall).
 */
function preloadFirstView(): Plugin {
  return {
    name: "ncc-preload-first-view",
    apply: "build",
    transformIndexHtml: {
      order: "post",
      handler(html, context) {
        type Chunk = { type: "chunk"; fileName: string; facadeModuleId: string | null; imports: string[]; isEntry: boolean };
        const bundle = context.bundle as Record<string, { type: string }> | undefined;
        if (!bundle) return html;
        const chunks = Object.values(bundle).filter((item): item is Chunk => item.type === "chunk");
        const overview = chunks.find((chunk) => chunk.facadeModuleId?.endsWith("features/overview/Overview.tsx"));
        const modules = new Set<string>();
        if (overview) {
          modules.add(overview.fileName);
          for (const name of overview.imports) if (!chunks.find((chunk) => chunk.fileName === name)?.isEntry) modules.add(name);
        }
        const fonts = Object.keys(bundle).filter((name) => /barlow-condensed-latin-700-normal.*\.woff2$|barlow-latin-400-normal.*\.woff2$/.test(name));
        const tags = [
          ...[...modules].filter((name) => !html.includes(name)).map((name) => `<link rel="modulepreload" crossorigin href="/${name}">`),
          ...fonts.map((name) => `<link rel="preload" as="font" type="font/woff2" crossorigin href="/${name}">`),
        ];
        return html.replace("</head>", `    ${tags.join("\n    ")}\n  </head>`);
      },
    },
  };
}

export default defineConfig({
  plugins: [react(), preloadFirstView(), appShell()],
  build: {
    outDir,
    emptyOutDir: true,
    target: "es2023",
    cssTarget: ["chrome123", "edge123", "firefox128", "safari17.5"],
    sourcemap: false,
  },
  server: { proxy: { "/api": "http://127.0.0.1:8350" } },
  preview: { proxy: { "/api": "http://127.0.0.1:8350" } },
});
