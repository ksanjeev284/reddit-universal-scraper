# Browser Collector Companion

A free browser-page collector for Chrome and Edge. It works independently, or sends collected records to the local Reddit Scraper Suite. No Reddit API credentials or paid proxy subscription are needed for this page-capture mode. Use it only for content you are authorized to collect; a logged-in account does not grant scraping permission under [Reddit's rules](https://support.reddithelp.com/hc/en-us/articles/360043512931-Don-t-break-the-site).

## Install

1. Open `chrome://extensions` in Chrome, or `edge://extensions` in Edge.
2. Turn on **Developer mode**, select **Load unpacked**, and choose this folder (the folder containing `manifest.json`). If using the ZIP release, extract it first and choose the extracted folder.
3. Pin **Browser Collector Companion** to the toolbar.
4. Reload any Reddit tabs already open when you installed it.

No build step is required. Store publication is pending. After source updates, click **Reload** on its extension card and reload Reddit tabs. Store listing assets and review notes are in [`../store/listing.md`](../store/listing.md); the public policy is in [`../docs/privacy-policy.md`](../docs/privacy-policy.md) and an offline copy opens from **Privacy & permissions** in the panel.

## Standalone collection

1. Sign in to Reddit in the same browser profile. Open a feed, subreddit, public user profile, search results, or a post on `www.reddit.com` or `old.reddit.com`.
2. Click the extension. Optionally set comma-separated subreddit names and keywords, a minimum score, and post/comment limits. Keywords match any term. Unknown scores are excluded when a minimum score is set.
3. Select **Capture this page** for one capture, or **Start capture** to keep collecting newly loaded content while you browse. Scroll normally and open posts to load their comments. Capture continues after closing the extension panel and resumes when that same tab navigates to another supported Reddit page.
4. Select **Stop** when finished. JSON, posts CSV and comments CSV exports work without the Python application.

The collector detects visible account/login controls. If Reddit's layout does not expose a login indicator, check **I'm signed in to Reddit in this browser** after verifying your own session. An explicit logged-out page or access challenge stops capture. Closing the Reddit tab or restarting the browser stops the session; collected records remain stored locally.

Limits apply to new records in each capture session. Existing records are deduplicated and their loaded metadata can be updated. The extension keeps up to 10,000 posts / 20,000 comments, with an 8 MB payload ceiling; export or send the collection, then clear it to make room.

## Connect to the application

In the repository, run these commands using your Python environment:

```powershell
python main.py --api
```

In a second terminal:

```powershell
python main.py --bridge-token
```

Open the extension's **Connect to the scraper app** section. Set the app address to `http://127.0.0.1:8000`, paste the pairing token, and select **Connect / test**. Allow the requested optional localhost access. Then select **Send collection to app**. Keep the panel open while sending. Tokens are stored in the extension's local settings, not sent to Reddit or included in exports.

The app validates every batch, deduplicates IDs and saves records into SQLite and the existing `data/r_<subreddit>/posts.csv` / `comments.csv` files. Imported data works with dashboard search, analytics and API queries. Refresh the dashboard's source list after import. Media links are preserved in `data/browser-imports/*.json`; this mode does not download media files automatically. Existing app records are preserved rather than replaced with potentially less complete page metadata.

If sending fails after a partial import, retry: app imports are idempotent and the local collection is retained. The import API accepts at most 500 records / 2 MB per request; the extension sends batches of up to 100 records. The pairing secret is generated at `data/.browser_bridge_token`, or can be set with `BROWSER_BRIDGE_TOKEN` in the app environment. Treat it as a local write credential.

### Import without running the API

Export JSON and use:

```powershell
python main.py --import-browser "C:\path\browser-collector-export.json"
```

You can also upload the JSON in the dashboard's **Integrations** tab. File imports accept up to 20 MB / 10,000 records. CSV exports are intended for spreadsheets; use JSON to preserve all fields for app import.

## Proxy support

The Python scraper still supports `PROXY_URL`, `--proxy`, stable `PROXY_COUNTRY` / `--proxy-country`, and `PROXY_SESSION_ID` / `--proxy-session` for supported ScrapingAnt URLs. The extension uses the browser's existing network/proxy configuration; it does not change the browser-wide proxy or need a paid provider. Make sure localhost bypasses your browser proxy if app pairing fails. The Python app's proxy settings do not automatically configure the browser.

## What is collected

Loaded post titles, bodies, authors, scores, timestamps when exposed, subreddit names, permalinks, loaded comment text/parent IDs, and media links. Some layouts omit metadata; missing scores stay `null` in the extension and become zero when imported into the app's existing numeric schema. Loaded images and accessible video links are recorded; hidden media, unloaded comments, deleted content and complete historical archives cannot be guaranteed.

The extension reads rendered page DOM. It does not call hidden Reddit APIs, automatically navigate/scroll, click “more comments,” bypass challenges, read/export authentication cookies, or collect private message/chat pages. This page collector supplements the approved OAuth scraper; it does not change Reddit's authorization requirements or future API migration requirements. Clear local records and remove exported/app copies when retention or deletion obligations require it.

## Permissions and testing

The extension reads only the declared Reddit domains. Storage keeps the collection locally; Downloads creates exports. Localhost host access is optional and requested only when connecting the app. There is no Cookies, browser Proxy, Web Request or all-sites permission, no remote executable code, and no analytics service.

The repository includes DOM fixture tests, background-worker tests and an isolated unpacked-extension test. Run them with Node and Playwright installed. Install Python test dependencies using `pip install -r requirements-dev.txt`:

```powershell
node extension/tests/background.mjs
node extension/tests/run.mjs
node extension/tests/installed.mjs
python -m unittest discover -s tests -v
```

The browser tests use locally fulfilled modern/old Reddit fixtures, not a live account. `run.mjs` uses installed Edge by default. `installed.mjs` supports Chromium, or set `BROWSER_CHANNEL=msedge` to use Edge. A local Chrome or Edge login still needs to be verified in your own browser. Page selectors may need updates when Reddit changes its UI.
