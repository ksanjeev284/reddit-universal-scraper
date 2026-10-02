"use strict";
const fields = ["subreddits", "keywords", "minScore", "maxPosts", "maxComments", "includeComments", "loginConfirmed", "appUrl", "bridgeToken"];
const element = id => document.getElementById(id);
let busy = false;
function settings() {
  return Object.fromEntries(fields.map(id => [id, element(id).type === "checkbox" ? element(id).checked :
    element(id).type === "number" ? Number(element(id).value) : element(id).value]));
}
function notice(message, kind = "") { element("status").textContent = message; element("status").className = kind; }
async function send(type, extra = {}) {
  const result = await chrome.runtime.sendMessage({type, ...extra});
  if (!result?.ok) throw new Error(result?.error || "The extension did not respond. Reload it and try again.");
  return result;
}
async function refresh(initial = false) {
  const result = await send("STATE");
  element("post-count").textContent = result.posts.toLocaleString();
  element("comment-count").textContent = result.comments.toLocaleString();
  if (initial) {
    for (const id of fields) {
      if (element(id).type === "checkbox") element(id).checked = Boolean(result.settings[id]);
      else element(id).value = result.settings[id] ?? "";
    }
    if (result.capture?.message) notice(result.capture.message);
  } else if (!busy && result.capture?.running) notice(result.capture.message, "success");
  element("mode").textContent = result.lastSync ? "App connected" : "Standalone";
  element("preview").replaceChildren(...result.preview.map(post => {
    const item = document.createElement("li");
    item.textContent = post.title;
    const subreddit = document.createElement("small");
    subreddit.textContent = `r/${post.subreddit}`;
    item.append(subreddit);
    return item;
  }));
  if (result.lastSync) element("sync-status").textContent = `Last send: ${result.lastSync.posts_added} new posts, ${result.lastSync.comments_added} new comments. Repeated sends are deduplicated.`;
}
async function act(operation) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("button").forEach(button => { button.disabled = true; });
  try { await operation(); await refresh(); }
  catch (error) { notice(error.message, "error"); }
  finally { busy = false; document.querySelectorAll("button").forEach(button => { button.disabled = false; }); }
}
element("start").addEventListener("click", () => act(async () => {
  const result = await send("START", {settings: settings()}); notice(result.capture.message, "success");
}));
element("once").addEventListener("click", () => act(async () => {
  const result = await send("ONCE", {settings: settings()}); notice(result.capture.message, "success");
}));
element("stop").addEventListener("click", () => act(async () => { await send("STOP"); notice("Capture stopped. Your collection is saved locally."); }));
for (const format of ["json", "posts", "comments"]) element(`export-${format}`).addEventListener("click", () => act(async () => {
  await send("EXPORT", {format}); notice("Export opened in the browser’s download dialog.", "success");
}));
element("clear").addEventListener("click", () => act(async () => {
  if (window.confirm("Clear the collection stored in this extension? Exported files and app data will remain.")) {
    await send("CLEAR"); notice("Local collection cleared.");
  }
}));
element("connect").addEventListener("click", () => {
  let url;
  try {
    url = new URL(element("appUrl").value);
    if (url.protocol !== "http:" || !["localhost", "127.0.0.1"].includes(url.hostname)) throw new Error();
  } catch { notice("Use http://127.0.0.1:8000 or another local app port.", "error"); return; }
  // Request optional localhost permission directly within the user's click.
  const permission = chrome.permissions.request({origins: [`http://${url.hostname}/*`]});
  act(async () => {
    if (!await permission) throw new Error("Local app permission was not granted.");
    await send("CONNECT", {settings: settings()}); notice("Connected to the local scraper app.", "success");
  });
});
element("sync").addEventListener("click", () => act(async () => {
  notice("Sending collection to the app… Keep this panel open until it finishes.");
  const result = await send("SYNC", {settings: settings()});
  notice(`App imported ${result.posts_added} new posts and ${result.comments_added} new comments; ${result.duplicates} duplicates skipped.`, "success");
}));
element("disconnect").addEventListener("click", () => act(async () => {
  element("bridgeToken").value = "";
  await send("FORGET_PAIRING");
  notice("Pairing token removed. Your collection and app copies remain on this device.");
}));
fields.forEach(id => element(id).addEventListener("change", () => {
  send("SAVE_SETTINGS", {settings: settings()}).catch(error => notice(error.message, "error"));
}));
refresh(true).catch(error => notice(error.message, "error"));
setInterval(() => { if (!busy) refresh().catch(() => {}); }, 2000);
