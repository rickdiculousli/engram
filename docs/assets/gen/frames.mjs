// frames.mjs <svg> <outprefix> [dark|light] [times] [reduce]: PNG frames of an animated SVG, to check it by eye.
// Each frame freezes every CSS animation at t seconds and writes <outprefix>-<t>.png, on GitHub's page colour for
// the scheme; `reduce` renders the prefers-reduced-motion picture once instead. Needs Playwright with a Chromium
// (`npx playwright install chromium`); a global install works too.
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");

const [svg, out, scheme = "dark", times = "0,2,4,6,8", reduce] = process.argv.slice(2);
if (!svg || !out) { console.error("usage: node frames.mjs <svg> <outprefix> [dark|light] [times] [reduce]"); process.exit(2); }
const src = readFileSync(svg, "utf8");
const [, vw, vh] = src.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
const w = 960, h = Math.ceil((w * +vh) / +vw), bg = scheme === "light" ? "#ffffff" : "#0d1117";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2,
                                     reducedMotion: reduce ? "reduce" : "no-preference" });
await page.setContent(`<html><body style="margin:0;background:${bg}">${src.replace("<svg ", `<svg style="display:block;width:${w}px;height:${h}px" `)}</body></html>`);
for (const t of reduce ? ["reduce"] : times.split(",")) {
  if (!reduce) await page.evaluate((s) => document.getAnimations().forEach((a) => { a.pause(); a.currentTime = s * 1000; }), +t);
  await page.screenshot({ path: `${out}-${t}.png` });
}
await browser.close();
