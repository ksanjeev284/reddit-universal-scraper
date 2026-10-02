import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {createRequire} from "node:module";
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const browser = await chromium.launch({channel: process.env.BROWSER_CHANNEL || "msedge", headless: true});
let passed = 0;
async function test(name, fn) { await fn(); passed++; console.log(`PASS ${name}`); }
try {
  const page = await browser.newPage();
  // Tests fulfill synthetic Reddit pages locally; no Reddit requests or accounts are used.
  await page.route("**/*", route => route.fulfill({contentType: "text/html", body: "<html><body></body></html>"}));
  await page.goto("https://www.reddit.com/r/python/comments/abc123/automation/");
  const script = await fs.readFile(path.join(root, "collector.js"), "utf8");
  for (const fixture of ["modern", "old"]) {
    await page.setContent(await fs.readFile(path.join(root, "tests/fixtures", `${fixture}.html`), "utf8"));
    await page.evaluate(script);
    const report = await page.evaluate(() => BrowserCollector.extract(document, location.href));
    await test(`${fixture}: logged-in detection and rendered posts`, () => {
      assert.equal(report.login, "logged_in"); assert.equal(report.posts.length, 1);
      assert.equal(report.posts[0].id, "abc123"); assert.equal(report.posts[0].title, "Automation with Python");
    });
    await test(`${fixture}: comments, nesting, parent IDs`, () => {
      assert.equal(report.comments.length, 2); assert.equal(report.comments[0].parent_id, "t3_abc123");
      assert.equal(report.comments[1].parent_id, "t1_def456"); assert.equal(report.comments[1].depth, 1);
      assert.equal(report.comments[0].post_permalink, "/r/python/comments/abc123/automation/");
    });
    if (fixture === "modern") await test("media links deduplicated", () => assert.deepEqual(report.posts[0].media_urls, ["https://i.redd.it/test.png"]));
  }
  await test("logged-out detection", async () => {
    await page.setContent('<a href="/login/">Log In</a>');
    assert.equal(await page.evaluate(() => BrowserCollector.extract(document, location.href).login), "logged_out");
  });
  await test("access challenge detection", async () => {
    await page.setContent('<h1>You’ve been blocked by network security</h1>');
    assert.equal(await page.evaluate(() => BrowserCollector.extract(document, location.href).login), "blocked");
  });
  await test("unsupported/private pages rejected", async () => {
    assert.equal(await page.evaluate(() => BrowserCollector.allowedPage("https://www.reddit.com/message/inbox")), false);
    assert.equal(await page.evaluate(() => BrowserCollector.allowedPage("https://www.reddit.com.evil/r/python")), false);
  });
  await test("filters and abbreviated scores", async () => {
    const result = await page.evaluate(() => ({score: BrowserCollector.count("1.2k"),
      matched: BrowserCollector.matches({subreddit: "Python", title: "Automation guide", score: 42}, {subreddits: "r/python", keywords: "automation, data", minScore: 40}),
      skipped: BrowserCollector.matches({subreddit: "other", title: "Automation guide", score: 42}, {subreddits: "python"})}));
    assert.equal(result.score, 1200); assert.equal(result.matched, true); assert.equal(result.skipped, false);
  });
  await test("CSV escaping and formula protection", async () => {
    const csv = await page.evaluate(() => BrowserCollector.csv([{title: '=SUM(1,2)', body: 'line\n"quote"'}], ["title", "body"]));
    assert.ok(csv.includes("'=SUM")); assert.ok(csv.includes('""quote""'));
  });
  await test("open shadow-root parsing", async () => {
    await page.setContent('<div id="host"></div>');
    await page.evaluate(() => {
      document.getElementById("host").attachShadow({mode: "open"}).innerHTML = '<button data-testid="user-menu">Account</button><shreddit-post style="display:block" post-title="Shadow post" permalink="/r/python/comments/shadow/title/"></shreddit-post>';
      document.getElementById("host").shadowRoot.querySelector("shreddit-post").attachShadow({mode: "open"}).innerHTML = '<img src="https://i.redd.it/shadow.png">';
    });
    const report = await page.evaluate(() => BrowserCollector.extract(document, location.href));
    assert.equal(report.posts[0].id, "shadow"); assert.equal(report.login, "logged_in");
    assert.deepEqual(report.posts[0].media_urls, ["https://i.redd.it/shadow.png"]);
  });
  await test("minimal manifest permissions and complete package", async () => {
    const manifest = JSON.parse(await fs.readFile(path.join(root, "manifest.json"), "utf8"));
    assert.equal(manifest.manifest_version, 3);
    assert.ok(!manifest.permissions.includes("cookies")); assert.ok(!manifest.permissions.includes("proxy"));
    assert.ok(!manifest.permissions.includes("webRequest"));
    for (const file of [...manifest.content_scripts[0].js, manifest.background.service_worker, manifest.action.default_popup, "popup.js", "popup.css"]) {
      await fs.access(path.join(root, file));
    }
  });
  console.log(`${passed} browser checks passed.`);
} finally { await browser.close(); }
