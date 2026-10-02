/* Generates original vector icons and screenshots of the real extension UI.
 * Uses an isolated test browser and synthetic data; never opens a user profile. */
import fs from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
import {fileURLToPath} from "node:url";
import {createRequire} from "node:module";
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const extension = path.join(root, "extension");
const store = path.join(root, "store");
const launch = {channel: process.env.BROWSER_CHANNEL || "msedge", headless: true};
await fs.mkdir(store, {recursive: true});
const svg = await fs.readFile(path.join(extension, "icons/source.svg"), "utf8");
const browser = await chromium.launch(launch);
try {
  const page = await browser.newPage();
  for (const size of [16, 32, 48, 128]) {
    await page.setViewportSize({width: size, height: size});
    await page.setContent(`<style>html,body{margin:0;width:100%;height:100%;background:transparent}svg{width:100%;height:100%;display:block}</style>${svg}`);
    await page.screenshot({path: path.join(extension, `icons/icon${size}.png`), omitBackground: true});
  }
  await page.setViewportSize({width: 440, height: 280});
  await page.setContent(`<style>*{box-sizing:border-box}body{margin:0;font-family:system-ui;background:#fff5ef;color:#202733;padding:28px}svg{width:64px;height:64px}h1{font-size:27px;letter-spacing:-1px;line-height:1.15;margin:8px 0}p{font-size:15px;line-height:1.5;margin:12px 0}.badge{font-size:10px;letter-spacing:1px;color:#963312;font-weight:700}</style>${svg}<h1>Browser Collector<br>Companion</h1><p>Capture loaded Reddit content.<br>Export locally. Connect your app.</p><div class="badge">USER-STARTED · LOCAL STORAGE</div>`);
  await page.screenshot({path: path.join(store, "promo-440x280.png")});
} finally { await browser.close(); }

const profiles = path.join(root, ".extension-test-profile");
await fs.mkdir(profiles, {recursive: true});
const profile = await fs.mkdtemp(path.join(profiles, "store-"));
const context = await chromium.launchPersistentContext(profile, {...launch, viewport: {width: 1280, height: 800},
  args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]});
try {
  let worker = context.serviceWorkers().find(worker => worker.url().startsWith("chrome-extension://"));
  if (!worker) worker = await context.waitForEvent("serviceworker", {timeout: 10000});
  const extensionId = new URL(worker.url()).host;
  const origin = `chrome-extension://${extensionId}`;
  const reddit = await context.newPage();
  const html = await fs.readFile(path.join(extension, "tests/fixtures/modern.html"), "utf8");
  await reddit.route("**/*", route => route.fulfill({contentType: "text/html", body: html}));
  await reddit.goto("https://www.reddit.com/r/python/comments/abc123/automation/");
  const popup = await context.newPage();
  await popup.goto(`${origin}/popup.html`);
  await reddit.bringToFront();
  const capture = await popup.evaluate(() => chrome.runtime.sendMessage({type: "ONCE", settings: {
    appUrl: "http://127.0.0.1:8000", maxPosts: 500, maxComments: 2000, includeComments: true
  }}));
  assert.equal(capture.ok, true, capture.error);
  assert.equal(capture.posts, 1); assert.equal(capture.comments, 2);
  await popup.reload();
  await popup.locator("#post-count").filter({hasText: "1"}).waitFor();
  const presentation = await context.newPage();
  await presentation.goto(`${origin}/privacy.html`);
  for (const mode of ["capture", "app"]) {
    await presentation.evaluate(({origin, mode}) => {
      document.body.replaceChildren();
      document.body.style.cssText = "margin:0;width:1280px;height:800px;background:#fff5ef;color:#202733;padding:60px 70px;font-family:system-ui;overflow:hidden";
      const copy = document.createElement("div");
      copy.style.cssText = "width:560px;position:absolute;top:100px;left:70px";
      const logo = document.createElement("img"); logo.src = `${origin}/icons/icon128.png`; logo.width = 100; logo.height = 100;
      const heading = document.createElement("h1"); heading.style.cssText = "font-size:52px;letter-spacing:-2px;line-height:1.08;margin:22px 0";
      heading.textContent = mode === "capture" ? "Your Reddit browsing, organized." : "Standalone capture. Optional app connection.";
      const description = document.createElement("p"); description.style.cssText = "font-size:21px;line-height:1.6;width:520px";
      description.textContent = mode === "capture" ? "Collect loaded posts and comments when you choose. Filter by subreddit, keywords and score. Export JSON or CSV to your device." : "Send your collection to your own localhost app for search and analysis. Pair with a token. No remote collection server.";
      const note = document.createElement("p"); note.style.cssText = "font-size:13px;color:#667085;margin-top:40px;line-height:1.7";
      note.textContent = "Browser Collector Companion · Real extension UI with example data. Independent project; not affiliated with Reddit or Google. Collect only content you are authorized to use.";
      copy.append(logo, heading, description, note);
      const frame = document.createElement("iframe"); frame.id = "ui"; frame.src = `${origin}/popup.html`;
      frame.style.cssText = "position:absolute;left:790px;top:40px;border:1px solid #e5e7eb;border-radius:16px;width:440px;height:1200px;transform-origin:top left;box-shadow:0 14px 38px #20273318";
      document.body.append(copy, frame);
    }, {origin, mode});
    const frame = presentation.frameLocator("#ui");
    await frame.locator("#post-count").filter({hasText: "1"}).waitFor();
    if (mode === "app") await frame.locator("details").evaluate(node => { node.open = true; });
    const height = await frame.locator("body").evaluate(node => node.scrollHeight);
    await presentation.locator("#ui").evaluate((node, height) => {
      node.style.height = `${height}px`;
      node.style.transform = `scale(${Math.min(.82, 720 / height)})`;
      if (height > 1200) node.style.left = "820px";
    }, height);
    await presentation.screenshot({path: path.join(store, `screenshot-${mode}-1280x800.png`)});
  }
  await popup.goto(`${origin}/privacy.html`);
  await popup.locator("h1").filter({hasText: "Privacy"}).waitFor();
  console.log("Store assets generated: 4 icons, 2 real-UI screenshots, 440x280 promo; privacy page verified.");
} finally { await context.close(); }
