/* DOM-only parser. It does not fetch Reddit endpoints, read cookies or click controls. */
(() => {
  "use strict";
  const hosts = new Set(["www.reddit.com", "old.reddit.com", "reddit.com"]);
  const text = (value, max = 40000) => String(value || "").trim().slice(0, max);
  function redditUrl(value, base = "https://www.reddit.com") {
    try {
      const url = new URL(value, base);
      return url.protocol === "https:" && hosts.has(url.hostname) && !url.username ? url : null;
    } catch { return null; }
  }
  function permalink(value, base) {
    const url = redditUrl(value, base);
    if (!url) return null;
    const match = url.pathname.match(/^\/r\/([\w]{1,100})\/comments\/([a-z0-9]+)\/([^/]*)\/?(?:([a-z0-9]+)\/?)?$/i);
    return match ? {path: url.pathname, subreddit: match[1], id: match[2], commentId: match[4] || ""} : null;
  }
  function rootsOf(document) {
    const roots = [document, ...(document.shadowRoot ? [document.shadowRoot] : [])];
    for (let i = 0; i < roots.length && roots.length < 1000; i++) {
      for (const element of roots[i].querySelectorAll("*")) {
        if (element.shadowRoot) roots.push(element.shadowRoot);
      }
    }
    return roots;
  }
  const queryAll = (roots, selector) => roots.flatMap(root => [...root.querySelectorAll(selector)]);
  function rendered(node) {
    return !node.hidden && node.getClientRects().length > 0 && node.getAttribute("aria-hidden") !== "true";
  }
  function firstText(node, selectors) {
    for (const selector of selectors) {
      const found = node.querySelector(selector) || node.shadowRoot?.querySelector(selector);
      if (found) return text(found.innerText || found.textContent);
    }
    return "";
  }
  function attr(node, names) {
    for (const name of names) {
      const value = node.getAttribute(name);
      if (value !== null && value !== "") return value;
    }
    return "";
  }
  const flag = (node, name) => node.hasAttribute(name) && !["false", "0"].includes(node.getAttribute(name));
  function count(value) {
    const normalized = text(value).replace(/,/g, "").toLowerCase();
    const match = normalized.match(/^(-?\d+(?:\.\d+)?)\s*([km])?(?:\s|$)/);
    if (!match) return null;
    return Math.round(Number(match[1]) * (match[2] === "k" ? 1000 : match[2] === "m" ? 1000000 : 1));
  }
  function date(value) {
    if (!value) return "";
    const timestamp = Date.parse(value);
    return Number.isFinite(timestamp) ? new Date(timestamp).toISOString() : "";
  }
  function loginState(roots) {
    const positive = queryAll(roots, '[data-testid="user-menu"], #USER_DROPDOWN_ID, shreddit-user-dropdown, a[href*="/logout"], form[action*="/logout"], #header-bottom-right .user a[href*="/user/"]');
    if (positive.some(rendered)) return "logged_in";
    for (const node of queryAll(roots, "reddit-header, shreddit-app")) {
      if (["logged-in", "loggedin", "is-logged-in"].some(name => ["true", ""].includes(node.getAttribute(name)))) return "logged_in";
    }
    const login = queryAll(roots, 'a[href*="/login"], a[href*="/account/login"], [data-testid="login-button"], #login-button');
    return login.some(rendered) ? "logged_out" : "unknown";
  }
  function mediaUrls(node, base) {
    const urls = [];
    const roots = rootsOf(node);
    for (const media of queryAll(roots, "img, video, source, a[href]")) {
      const value = media.currentSrc || media.getAttribute("src") || media.getAttribute("href");
      try {
        const url = new URL(value, base);
        if (/^https?:$/.test(url.protocol) &&
            (media.tagName === "VIDEO" || media.tagName === "SOURCE" ||
             (/\.(?:jpe?g|png|gif|webp|mp4|webm)$/i.test(url.pathname) && !/avatar|icon|emoji|award/i.test(value)))) urls.push(url.href);
      } catch { /* Invalid or browser-local media URL. */ }
    }
    return [...new Set(urls)].slice(0, 50);
  }
  function parsePost(node, pageUrl) {
    let info = permalink(attr(node, ["permalink"]), pageUrl);
    if (!info) {
      for (const anchor of node.querySelectorAll('a.comments, a[data-click-id="comments"], a[href*="/comments/"]')) {
        info = permalink(anchor.getAttribute("href"), pageUrl);
        if (info && !info.commentId) break;
      }
    }
    if (!info || info.commentId) return null;
    const title = text(attr(node, ["post-title"]) || firstText(node, ['[slot="title"]', "h1", "h2", "h3", "a.title"]), 2000);
    if (!title) return null;
    const media = mediaUrls(node, pageUrl);
    const body = firstText(node, ['[slot="text-body"]', '[slot="post-body"]', '.entry > .expando .usertext-body .md', '[data-click-id="text"]']);
    const time = node.querySelector("time[datetime]");
    const url = attr(node, ["content-href", "data-url"]) || node.querySelector("a.title")?.getAttribute("href") || `https://www.reddit.com${info.path}`;
    let absoluteUrl = "";
    try { const parsed = new URL(url, pageUrl); if (/^https?:$/.test(parsed.protocol)) absoluteUrl = parsed.href; } catch { /* Missing URL. */ }
    return {
      id: info.id, subreddit: info.subreddit, permalink: info.path, title,
      author: text(attr(node, ["author", "data-author"]) || firstText(node, ["a.author", 'a[href*="/user/"]']), 100),
      created_utc: date(attr(node, ["created-timestamp"]) || time?.getAttribute("datetime")),
      url: absoluteUrl, score: count(attr(node, ["score", "data-score"]) || firstText(node, [".score.unvoted", '[data-testid="post-score"]'])),
      num_comments: count(attr(node, ["comment-count"]) || firstText(node, ["a.comments", '[data-testid="comment-count"]'])),
      selftext: body, post_type: /video/i.test(attr(node, ["post-type"])) ? "video" :
        /image|gallery/i.test(attr(node, ["post-type"])) ? "image" : body ? "text" : media.length ? "image" : "link",
      is_nsfw: flag(node, "nsfw") || node.classList.contains("over18"),
      is_spoiler: flag(node, "spoiler"), flair: firstText(node, [".linkflairlabel", '[slot="post-flair"]']),
      media_urls: media, observed_at: new Date().toISOString(), source: "Browser-Collector"
    };
  }
  function parseComment(node, pageUrl) {
    const post = permalink(pageUrl, pageUrl);
    if (!post) return null;
    const fullname = attr(node, ["thingid", "comment-id", "data-fullname", "id"]);
    const commentId = fullname.replace(/^t1_/, "");
    if (!/^[a-z0-9]+$/i.test(commentId)) return null;
    const body = firstText(node, [':scope > [slot="comment"]', ':scope > .entry > .usertext .md', '[data-testid="comment"]', ':scope > .comment-body']);
    if (!body) return null;
    const parent = node.parentElement?.closest("shreddit-comment, .thing.comment");
    let depth = Number(attr(node, ["depth"]));
    if (!Number.isFinite(depth)) depth = 0;
    if (!node.hasAttribute("depth")) {
      depth = 0;
      for (let ancestor = parent; ancestor; ancestor = ancestor.parentElement?.closest("shreddit-comment, .thing.comment")) depth++;
    }
    const time = node.querySelector(":scope > .entry time, :scope > time");
    return {
      comment_id: commentId, post_id: post.id, subreddit: post.subreddit,
      post_permalink: `/r/${post.subreddit}/comments/${post.id}/${post.path.split("/")[5] || ""}/`,
      parent_id: attr(node, ["parent-id", "parentid"]) || (parent ? attr(parent, ["thingid", "data-fullname"]) : `t3_${post.id}`),
      author: text(attr(node, ["author"]) || firstText(node, [":scope > .entry a.author", '[slot="authorName"]']), 100),
      body, score: count(attr(node, ["score"]) || firstText(node, [":scope > .entry .score.unvoted"])),
      created_utc: date(attr(node, ["created-timestamp"]) || time?.getAttribute("datetime")),
      depth, is_submitter: flag(node, "is-op"), observed_at: new Date().toISOString()
    };
  }
  function allowedPage(value) {
    const url = redditUrl(value);
    return Boolean(url && (/^\/(?:r|user|u)\//.test(url.pathname) || /^\/(?:search\/?|$)/.test(url.pathname)));
  }
  function extract(document, pageUrl) {
    if (!allowedPage(pageUrl)) return {login: "unknown", posts: [], comments: [], error: "Open a Reddit feed, public profile, or post page."};
    const roots = rootsOf(document);
    const nodes = queryAll(roots, "shreddit-post, .thing.link, [data-testid=post-container]").filter(rendered);
    const posts = nodes.map(node => parsePost(node, pageUrl)).filter(Boolean);
    const comments = queryAll(roots, "shreddit-comment, .thing.comment").filter(rendered).map(node => parseComment(node, pageUrl)).filter(Boolean);
    const headings = queryAll(roots, "h1, h2").map(node => text(node.textContent, 300)).join(" ");
    const blocked = !posts.length && /blocked by network security|you.?ve been blocked|verify you are human|whoa there|robot check/i.test(headings);
    return {login: blocked ? "blocked" : loginState(roots), posts, comments, page_url: pageUrl};
  }
  function matches(record, rules = {}) {
    const subreddits = text(rules.subreddits).toLowerCase().split(",").map(s => s.trim().replace(/^r\//, "")).filter(Boolean);
    const keywords = text(rules.keywords).toLowerCase().split(",").map(s => s.trim()).filter(Boolean);
    return (!subreddits.length || subreddits.includes((record.subreddit || "").toLowerCase())) &&
      (!keywords.length || keywords.some(word => `${record.title || ""} ${record.selftext || ""} ${record.body || ""}`.toLowerCase().includes(word))) &&
      (!rules.minScore || (record.score !== null && Number(record.score) >= Number(rules.minScore)));
  }
  function csv(records, fields) {
    const cell = value => {
      let result = typeof value === "object" && value !== null ? JSON.stringify(value) : String(value ?? "");
      if (/^[=+\-@\t\r]/.test(result)) result = "'" + result;
      return `"${result.replace(/"/g, '""')}"`;
    };
    return fields.map(cell).join(",") + "\r\n" + records.map(row => fields.map(field => cell(row[field])).join(",")).join("\r\n");
  }
  const api = {extract, parsePost, parseComment, permalink, allowedPage, count, matches, csv};
  globalThis.BrowserCollector = api;
  if (typeof module !== "undefined") module.exports = api;
})();
