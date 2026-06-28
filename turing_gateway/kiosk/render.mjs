import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const W = 1440, H = 2560, TOTAL = 660;          // 660 frames @ 30fps = 22s loop — PORTRAIT (1440×2560)
const FRAMES_DIR = path.join(DIR, 'frames');

// Point CHROME_PATH at a Chromium/Chrome binary, or leave unset to let
// Playwright use its own managed browser (run `npx playwright install chromium`).
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || undefined,
  args: ['--use-gl=swiftshader', '--no-sandbox', '--hide-scrollbars'],
});
const page = await browser.newPage({ viewport: { width: W, height: H } });

console.log(`Rendering ${TOTAL} frames at ${W}x${H}...`);
const t0 = Date.now();
for (let f = 0; f < TOTAL; f++) {
  const url = `file://${path.join(DIR, 'memex_brain.html')}?w=${W}&h=${H}&frame=${f}&total=${TOTAL}`;
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction('window.__READY__ === true', { timeout: 10000 });
  const name = String(f).padStart(4, '0');
  await page.screenshot({ path: path.join(FRAMES_DIR, `f${name}.jpg`), type: 'jpeg', quality: 95, clip: { x: 0, y: 0, width: W, height: H } });
  if (f % 30 === 0) console.log(`  frame ${f}/${TOTAL}  (${((Date.now()-t0)/1000).toFixed(1)}s)`);
}
console.log(`Done in ${((Date.now()-t0)/1000).toFixed(1)}s`);
await browser.close();
