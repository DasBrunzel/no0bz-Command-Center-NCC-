/* Renders the PWA PNG icons from the SVG sources: node tests/tools/make-icons.ts */
import { readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const dir = new URL("../../public/assets/icons/", import.meta.url);
const jobs: Array<[string, string, number]> = [
  ["icon.svg", "icon-192.png", 192],
  ["icon.svg", "icon-512.png", 512],
  ["maskable.svg", "maskable-512.png", 512],
];
const browser = await chromium.launch();
for (const [source, target, size] of jobs) {
  const page = await browser.newPage({ viewport: { width: size, height: size }, deviceScaleFactor: 1 });
  const svg = readFileSync(new URL(source, dir), "utf8");
  await page.setContent(`<html><body style="margin:0;background:transparent">${svg.replace("<svg ", `<svg width="${size}" height="${size}" `)}</body></html>`);
  await page.screenshot({ path: new URL(target, dir).pathname.replace(/^\/([A-Za-z]:)/, "$1"), omitBackground: true });
  await page.close();
}
await browser.close();
console.log("icons written");
