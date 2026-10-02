(() => {
  "use strict";
  let running = false;
  let timer = null;
  let observer = null;
  let lastScan = 0;
  async function scan() {
    if (!running) return;
    lastScan = Date.now();
    try {
      const report = BrowserCollector.extract(document, location.href);
      const result = await chrome.runtime.sendMessage({type: "REPORT", report});
      if (!result?.ok || !result.running) stop();
    } catch { stop(); }
  }
  function schedule() {
    if (!running || timer) return;
    timer = setTimeout(() => { timer = null; scan(); }, Math.max(1500 - (Date.now() - lastScan), 100));
  }
  function stop() {
    running = false;
    clearTimeout(timer);
    timer = null;
    observer?.disconnect();
    observer = null;
    window.removeEventListener("scroll", schedule);
  }
  async function start() {
    stop();
    running = true;
    observer = new MutationObserver(schedule);
    observer.observe(document.documentElement, {childList: true, subtree: true, attributes: true,
      attributeFilter: ["score", "comment-count", "author", "hidden"]});
    window.addEventListener("scroll", schedule, {passive: true});
    await scan();
  }
  chrome.runtime.onMessage.addListener((message, sender, reply) => {
    if (sender.id !== chrome.runtime.id) return;
    if (message.type === "PAGE_INFO") reply(BrowserCollector.extract(document, location.href));
    else if (message.type === "START") { start().then(() => reply({ok: true})); return true; }
    else if (message.type === "STOP") { stop(); reply({ok: true}); }
    else if (message.type === "ONCE") {
      stop(); running = true;
      scan().then(() => { stop(); reply({ok: true}); });
      return true;
    }
  });
  // A session resumes in the same tab after ordinary Reddit navigation, not after browser restart.
  chrome.runtime.sendMessage({type: "CAPTURE_RULES"}).then(result => {
    if (result?.active) start();
  }).catch(() => {});
  window.addEventListener("pagehide", stop, {once: true});
})();
