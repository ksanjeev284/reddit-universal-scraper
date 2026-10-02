/* Optional end-to-end load check in an isolated Chromium profile. */
import fs from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {createRequire} from "node:module";
import assert from "node:assert/strict";
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const profiles = path.join(root, "..", ".extension-test-profile");
await fs.mkdir(profiles, {recursive: true});
const profile = await fs.mkdtemp(path.join(profiles, "run-"));
const context = await chromium.launchPersistentContext(profile, {
  ...(process.env.BROWSER_CHANNEL ? {channel: process.env.BROWSER_CHANNEL} : {}), headless: true,
  args: [`--disable-extensions-except=${root}`, `--load-extension=${root}`]
});
try {
  let worker = context.serviceWorkers().find(worker => worker.url().startsWith("chrome-extension://"));
  if (!worker) worker = await context.waitForEvent("serviceworker", {timeout: 10000});
  const extensionId = new URL(worker.url()).host;
  const html = await fs.readFile(path.join(root, "tests/fixtures/modern.html"), "utf8");
  const reddit = await context.newPage();
  await reddit.route("**/*", route => route.fulfill({contentType: "text/html",
    body: route.request().url().includes("logged-out") ? '<a href="/login/">Log In</a>' : html}));
  await reddit.goto("https://www.reddit.com/r/python/comments/abc123/automation/");
  const popup = await context.newPage();
  await popup.goto(`chrome-extension://${extensionId}/popup.html`);
  // Start from the real extension context while the Reddit tab is active.
  await reddit.bringToFront();
  const capture = await popup.evaluate(() => chrome.runtime.sendMessage({type: "ONCE", settings: {
    appUrl: "http://127.0.0.1:8000", maxPosts: 10, maxComments: 20, includeComments: true
  }}));
  assert.equal(capture.ok, true, capture.error);
  assert.equal(capture.posts, 1); assert.equal(capture.comments, 2);
  const state = await popup.evaluate(() => chrome.runtime.sendMessage({type: "STATE"}));
  assert.equal(state.capture.running, false);
  await popup.bringToFront();
  await popup.reload();
  await popup.locator("#post-count").filter({hasText: "1"}).waitFor();
  const results = path.join(root, "..", ".test-results");
  await fs.mkdir(results, {recursive: true});
  await popup.locator("body").screenshot({path: path.join(results, "extension-popup.png")});
  console.log("PASS real MV3 load, content messaging, logged-in capture, persisted state and popup rendering");
  await reddit.bringToFront();
  const started = await popup.evaluate(() => chrome.runtime.sendMessage({type: "START", settings: {
    appUrl: "http://127.0.0.1:8000", maxPosts: 10, maxComments: 20, includeComments: true
  }}));
  assert.equal(started.ok, true, started.error);
  await popup.close();
  await reddit.evaluate(() => {
    const post = document.createElement("shreddit-post");
    post.setAttribute("post-title", "Dynamically loaded post");
    post.setAttribute("permalink", "/r/python/comments/dynamic/loaded/");
    document.body.append(post);
  });
  await reddit.waitForFunction(async () => {
    // The test polls from an extension context below; this delay only lets DOM observation run.
    return document.querySelectorAll("shreddit-post").length === 3;
  });
  await new Promise(resolve => setTimeout(resolve, 1800));
  const data = await worker.evaluate(() => chrome.storage.local.get("data"));
  assert.equal(data.data.posts.length, 2);
  console.log("PASS capture continues after closing the panel and observes newly loaded posts");
  await reddit.goto("https://www.reddit.com/r/python/?logged-out=1");
  await new Promise(resolve => setTimeout(resolve, 700));
  const stopped = await worker.evaluate(() => chrome.storage.session.get("capture"));
  assert.equal(stopped.capture.running, false);
  assert.match(stopped.capture.message, /Log in/);
  console.log("PASS ordinary navigation resumes the session and logout stops capture");
} finally { await context.close(); }
