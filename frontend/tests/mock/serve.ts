/*
 * Dev/preview stand-in for the FastAPI server: serves the built dashboard
 * exactly like app.py ("/" → index.html, "/assets/*") and answers /api/v1
 * from the in-memory mock. Run: node tests/mock/serve.ts
 *   MOCK_PORT (default 8350), MOCK_ROLE (commander | beta_tester | friend | none)
 *   MOCK_GZIP=1 compresses static files (FastAPI's StaticFiles does not; for comparison only)
 */
import { createServer } from "node:http";
import { gzipSync } from "node:zlib";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { createMockApi } from "./api.ts";

const port = Number(process.env.MOCK_PORT ?? 8350);
const role = process.env.MOCK_ROLE ?? "commander";
const staticDir = fileURLToPath(new URL("../../../backend/ncc_server/static/", import.meta.url));
const mock = createMockApi({ session: role === "none" ? null : (role as "commander") });
const types: Record<string, string> = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2", ".woff": "font/woff", ".webmanifest": "application/manifest+json", ".json": "application/json" };

createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", `http://localhost:${port}`);
  if (url.pathname.startsWith("/api/")) {
    const chunks: Buffer[] = [];
    for await (const chunk of req) chunks.push(chunk as Buffer);
    const headers = Object.fromEntries(Object.entries(req.headers).map(([key, value]) => [key, String(value)]));
    const contentType = headers["content-type"] ?? "";
    const result = mock.handle({ method: req.method ?? "GET", url: url.pathname + url.search, headers, body: contentType.includes("json") ? Buffer.concat(chunks).toString("utf8") : null });
    res.writeHead(result.status, { "Content-Type": result.contentType ?? "application/json", "Cache-Control": "no-store" });
    res.end(result.body ?? (result.json === undefined ? "" : JSON.stringify(result.json)));
    return;
  }
  const file = url.pathname === "/" ? "index.html" : url.pathname.startsWith("/assets/") ? normalize(url.pathname.slice(1)) : null;
  if (!file || file.includes("..")) { res.writeHead(404, { "Content-Type": "application/json" }); res.end('{"detail":"Not Found"}'); return; }
  try {
    let data = await readFile(join(staticDir, file));
    const headers: Record<string, string> = { "Content-Type": types[extname(file)] ?? "application/octet-stream", "Cache-Control": file.startsWith("assets/") && !file.endsWith("sw.js") ? "public, max-age=31536000, immutable" : "no-cache" };
    if (process.env.MOCK_GZIP && /\.(js|css|html|svg|webmanifest)$/.test(file) && String(req.headers["accept-encoding"] ?? "").includes("gzip")) {
      data = gzipSync(data);
      headers["Content-Encoding"] = "gzip";
    }
    res.writeHead(200, headers);
    res.end(data);
  } catch {
    res.writeHead(404, { "Content-Type": "application/json" });
    res.end('{"detail":"Not Found"}');
  }
}).listen(port, () => console.log(`NCC mock server on http://127.0.0.1:${port} (session: ${role})`));
