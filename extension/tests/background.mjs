import assert from "node:assert/strict";
import fs from "node:fs/promises";
import vm from "node:vm";
import path from "node:path";
import {fileURLToPath} from "node:url";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = await fs.readFile(path.join(root, "background.js"), "utf8");
const parser = await fs.readFile(path.join(root, "collector.js"), "utf8");
let listener, report;
const local = {}, session = {};
const requests = [], downloads = [];
const popupSender = {id: "extension-test", url: "chrome-extension://extension-test/popup.html"};
const contentSender = {id: "extension-test", tab: {id: 10, url: "https://www.reddit.com/r/python/"}, url: "https://www.reddit.com/r/python/"};
const post = {id: "abc123", title: "Automation", subreddit: "python", permalink: "/r/python/comments/abc123/title/", score: 20, media_urls: []};
const rules = {subreddits: "python", keywords: "automation", maxPosts: 2, maxComments: 0,
  includeComments: false, appUrl: "http://127.0.0.1:8000", bridgeToken: "test-token-at-least-24-characters", loginConfirmed: false};
const storage = data => ({get: async keys => Object.fromEntries((typeof keys === "string" ? [keys] : keys).map(key => [key, structuredClone(data[key])])),
  set: async input => Object.assign(data, structuredClone(input)), setAccessLevel: async () => {}});
const chrome = {
  storage: {local: storage(local), session: storage(session)},
  runtime: {id: "extension-test", getURL: suffix => `chrome-extension://extension-test/${suffix}`,
    onInstalled: {addListener() {}}, onMessage: {addListener(fn) { listener = fn; }}},
  permissions: {contains: async () => true}, downloads: {download: async options => { downloads.push(options); return 1; }},
  tabs: {query: async () => [{id: 10, url: contentSender.url}], onRemoved: {addListener() {}},
    sendMessage: async (id, message) => {
      if (message.type === "PAGE_INFO") return report;
      if (["START", "ONCE"].includes(message.type)) return messageTo({type: "REPORT", report}, contentSender);
      return {ok: true};
    }}
};
const context = vm.createContext({console, chrome, URL, TextEncoder, AbortSignal, setTimeout, clearTimeout,
  fetch: async (url, options) => {
    requests.push({url, options});
    return {ok: true, json: async () => url.endsWith("/status") ? {status: "ready"} : {posts_added: 1, comments_added: 0, duplicates: 0}};
  }});
context.importScripts = () => vm.runInContext(parser, context);
vm.runInContext(source, context);
function messageTo(message, sender = popupSender) {
  return new Promise(resolve => { listener(message, sender, resolve); });
}
let count = 0;
async function test(name, fn) { await fn(); count++; console.log(`PASS ${name}`); }
report = {login: "logged_in", page_url: contentSender.url, posts: [post], comments: []};
await test("start captures and persists data without worker deadlock", async () => {
  const result = await messageTo({type: "START", settings: rules});
  assert.equal(result.ok, true); assert.equal(result.posts, 1); assert.equal(result.capture.running, true);
  assert.ok(!JSON.stringify(session).includes(rules.bridgeToken), "Pairing token must not enter capture session rules");
});
await test("duplicate reports update without duplicate records", async () => {
  await messageTo({type: "REPORT", report}, contentSender);
  assert.equal(local.data.posts.length, 1); assert.equal(session.capture.addedPosts, 1);
});
await test("wrong tab cannot write data", async () => {
  await messageTo({type: "REPORT", report: {...report, posts: [{...post, id: "other"}]}}, {...contentSender, tab: {id: 99}});
  assert.equal(local.data.posts.length, 1);
});
await test("content scripts cannot read pairing settings", async () => {
  const result = await messageTo({type: "STATE"}, contentSender);
  assert.equal(result.ok, false); assert.ok(!JSON.stringify(result).includes(rules.bridgeToken));
  const active = await messageTo({type: "CAPTURE_RULES"}, contentSender);
  assert.equal(active.active, true); assert.ok(!JSON.stringify(active).includes(rules.bridgeToken));
});
await test("new-post limit stops capture", async () => {
  await messageTo({type: "REPORT", report: {...report, posts: [{...post, id: "two"}]}}, contentSender);
  assert.equal(local.data.posts.length, 2); assert.equal(session.capture.running, false);
});
await test("logged-out pages cannot start capture", async () => {
  report.login = "logged_out";
  const result = await messageTo({type: "START", settings: {...rules, loginConfirmed: true}});
  assert.equal(result.ok, false); assert.match(result.error, /Log in/);
  report.login = "logged_in";
});
await test("challenge pauses capture", async () => {
  await messageTo({type: "START", settings: {...rules, maxPosts: 10}});
  await messageTo({type: "REPORT", report: {...report, login: "blocked"}}, contentSender);
  assert.equal(session.capture.running, false); assert.match(session.capture.message, /challenge/);
});
await test("pairing rejects a remote app destination", async () => {
  const result = await messageTo({type: "CONNECT", settings: {...rules, appUrl: "https://evil.test"}});
  assert.equal(result.ok, false); assert.equal(requests.length, 0);
});
await test("bridge request uses token, omits browser credentials and disallows redirects", async () => {
  const result = await messageTo({type: "CONNECT", settings: rules});
  assert.equal(result.ok, true);
  assert.equal(requests[0].options.credentials, "omit"); assert.equal(requests[0].options.redirect, "error");
  assert.equal(requests[0].options.headers.Authorization, `Bearer ${rules.bridgeToken}`);
});
await test("sync sends portable batches and leaves local data intact", async () => {
  const result = await messageTo({type: "SYNC", settings: rules});
  assert.equal(result.ok, true); assert.equal(local.data.posts.length, 2);
  const payload = JSON.parse(requests.at(-1).options.body);
  assert.equal(payload.schema_version, 1); assert.equal(payload.posts.length, 2);
  assert.ok(!JSON.stringify(payload).includes(rules.bridgeToken));
});
await test("standalone exports do not require app requests", async () => {
  const before = requests.length;
  const result = await messageTo({type: "EXPORT", format: "json"});
  assert.equal(result.ok, true); assert.equal(requests.length, before);
  assert.ok(downloads[0].url.startsWith("data:application/json"));
});
await test("clear stops capture and empties only local collection", async () => {
  const result = await messageTo({type: "CLEAR"});
  assert.equal(result.posts, 0); assert.equal(result.comments, 0);
  assert.equal(local.settings.bridgeToken, rules.bridgeToken);
});
await test("forget pairing removes saved and legacy session credentials", async () => {
  session.capture.rules.bridgeToken = rules.bridgeToken;
  const result = await messageTo({type: "FORGET_PAIRING"});
  assert.equal(result.ok, true);
  assert.equal(local.settings.bridgeToken, "");
  assert.ok(!JSON.stringify(session).includes(rules.bridgeToken));
});
console.log(`${count} background checks passed.`);
