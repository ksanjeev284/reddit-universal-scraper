# Chrome Web Store listing and review preparation

Version: 1.0.0. These fields describe the submitted extension, not a guarantee of store or Reddit approval.

## Listing fields

**Name:** Browser Collector Companion

**Summary:** Collect loaded Reddit posts and comments while browsing, export locally, or connect to your local scraper app.

**Category:** Productivity (choose the closest productivity/tools category offered by the dashboard).

**Language:** English

**Homepage:** https://github.com/ksanjeev284/reddit-universal-scraper

**Support:** https://github.com/ksanjeev284/reddit-universal-scraper/issues

**Privacy policy:** https://github.com/ksanjeev284/reddit-universal-scraper/blob/main/docs/privacy-policy.md

**Detailed description:**

Browser Collector Companion helps you organize loaded Reddit posts and comments while you browse. Start capture from the extension panel, browse normally in the selected tab, then export your collection as JSON, posts CSV or comments CSV. Standalone capture and exports are free and do not require the Python application or paid API credentials.

Capture saves loaded post/comment text, author usernames, subreddit names, identifiers, links, scores, timestamps and displayed metadata locally in this browser profile. It records the supported Reddit page URL and observation times for capture status. The developer does not receive your collection. There is no analytics service, advertising or remote collection server.

Features:
- Capture this page once, or keep collecting newly loaded content in the selected tab after closing the popup.
- Filter by subreddit, keywords and minimum score; set limits and include or exclude loaded comments.
- Deduplicate records, preview collected titles, export locally, and clear the local collection.
- Optionally pair the open-source Reddit Scraper Suite on the same computer with a token, then send records for local search and analysis. Localhost access is requested only for this feature.

Sign in to Reddit in your browser before starting. If the page does not expose a login indicator, confirm your session in the panel. Capture stops on an explicit logged-out page or access challenge. Scroll normally and open posts to load content: this extension does not automatically navigate, scroll, open hidden comments, or bypass access restrictions. Missing metadata and unloaded/deleted content cannot be recovered. It captures page content and media links, not a complete historical archive or automatic media download.

The extension does not read Reddit passwords, cookies, private messages or chats, and does not access your general browser history. JSON/CSV exports and optional app copies may contain personal information published by post/comment authors. Clear extension records, exported files and app copies separately when needed. The optional pairing token can be removed from the panel. Your existing browser proxy configuration remains in effect.

Independent open-source project; not affiliated with or endorsed by Reddit or Google. Collect only content you are authorized to use. Signing in and installing the extension do not grant permission to scrape Reddit or reuse others' content. See the privacy policy for data handling, retention and permissions.

## Privacy practices answers

**Single purpose:** Capture and organize loaded Reddit posts/comments during user-started browsing sessions for local export or optional import into the user's same-computer application.

**storage justification:** Save the user's collected records, filters and optional localhost pairing settings in chrome.storage.local; maintain temporary capture state in chrome.storage.session. Nothing uses storage.sync.

**downloads justification:** Create the JSON, posts CSV and comments CSV files requested by the user through the export buttons.

**Reddit host permission justification:** Read supported rendered Reddit pages when the user starts capture and resume that session in the selected tab after navigation. The three exact HTTPS hosts cover current Reddit, old Reddit and the bare domain. No all-sites or general history access.

**Optional localhost host permission justification:** Connect / test authenticates a same-computer app at /bridge/status; Send collection to app imports records at /bridge/import. The user supplies the local address and pairing token and explicitly requests permission. Destinations are restricted to HTTP localhost or 127.0.0.1, with no redirects or browser credentials.

**Remote code:** No. All executable logic is packaged readable JavaScript. There are no external scripts, eval, remote WASM, or remote configurations containing logic. The localhost bridge transfers JSON data only.

**Data categories:** Disclose locally handled data even though no developer server receives it. Select Website content (post/comment text and metadata), Personally identifiable information (author usernames), Web history (supported Reddit URLs used for the chosen capture session, not general history), and Authentication information (user-entered local app pairing token, not Reddit cookies/passwords). Do not declare "no user data collected." If the dashboard wording differs, map to these actual practices. No payment, location, general keystroke/click tracking or private-communication functionality exists.

**Certifications:** Actual behavior supports no selling/transferring data to third parties outside approved use cases, no unrelated use, and no creditworthiness/lending use. Owner must review declarations and final submission. Link the public privacy policy; do not promise separate encryption of local storage or claim zero data handling.

## Reviewer instructions

1. Install and reload a Reddit tab. Sign in using a reviewer-owned Reddit account; no publisher credentials or cookies are needed or provided.
2. Visit a feed or public post on www.reddit.com or old.reddit.com. Open the extension. Select Capture this page. If there is no visible login indicator, first confirm the signed-in session using the checkbox. Observe the counters and collected title preview.
3. Export JSON or CSV using the panel. Choose Start capture, close the popup, then browse/scroll normally in that selected tab. Open the panel again to see newly loaded records. Stop and Clear local collection.
4. Read Privacy & permissions from the panel. Main capture/export functionality works without the companion app. The optional integration requires the open-source Python app: pip install -r requirements.txt, python main.py --api, then in another terminal python main.py --bridge-token. Connect using http://127.0.0.1:8000 and the generated token; allow localhost access and Send collection to app. Do not reuse a publisher account or persistent credential.
5. Fixture-based automated tests and the synthetic example data used in listing screenshots are in extension/tests. Real-site layout changes may require selector updates. Store images show the actual extension UI; app screenshot does not claim an active pairing.

## Files and checks

- Upload package: dist/browser-collector-extension.zip (run python scripts/package_extension.py).
- Icon: extension/icons/icon128.png, original artwork without Reddit/Google branding.
- Screenshots: store/screenshot-capture-1280x800.png and store/screenshot-app-1280x800.png (real UI with labeled example data).
- Small promo: store/promo-440x280.png.
- Source assets: extension/icons/source.svg and scripts/create_store_assets.mjs. Run with Node/Playwright and installed Edge, or set BROWSER_CHANNEL and PLAYWRIGHT_MODULE.
- Verify the public privacy/support links after pushing. Confirm publisher email verification, developer registration, 2-Step Verification, any trader declaration and distribution settings in the owner's dashboard. Never invent publisher identity/contact details or claim these checks passed without seeing the dashboard.
- Run Python unit tests, background tests, DOM fixtures and the unpacked MV3 integration test. These prove fixture behavior, not live Reddit authorization or guaranteed review approval.
- Review official policies: https://developer.chrome.com/docs/webstore/program-policies/policies, https://developer.chrome.com/docs/webstore/program-policies/user-data-faq and https://developer.chrome.com/docs/webstore/images.

## Submission status

Prepared locally. Upload and dashboard validation must be verified separately. No review approval or publication is claimed by this file.
