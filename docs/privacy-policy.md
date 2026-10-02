# Browser Collector Companion privacy policy

Effective date: October 2, 2026. Applies to extension version 1.0.0.

Browser Collector Companion has one purpose: help you collect loaded Reddit posts and comments while browsing, then export those records or send them to your own application on the same computer. It is an independent open-source project maintained in [reddit-universal-scraper](https://github.com/ksanjeev284/reddit-universal-scraper), and is not affiliated with Reddit or Google.

## Information handled

When you select **Start capture** or **Capture this page**, the extension reads rendered content on supported Reddit pages. It collects loaded post titles and bodies, comment text, author usernames, subreddit names, post/comment identifiers, permalinks, external/media links, scores, timestamps, and other displayed post metadata. Text may include personal information that its authors published. Capture records observation times and the current supported Reddit page URL for session status. It does not access your general browser history or track activity on other websites.

The extension stores your collection filters, limits, login confirmation, and optional local application address. If you pair the application, it stores the pairing token you enter; the token is a credential for your local app, not a Reddit password. Only trusted extension pages and its service worker can read the saved collection and settings.

It checks visible Reddit account/login controls to determine whether capture can start. It does not read passwords, authentication cookies, private messages or chats. It does not collect posts when installed or opened without a capture action. A running capture session continues in the selected tab after you close the popup and resumes after supported Reddit navigation. **Stop**, closing that tab, reaching session limits, an explicit logged-out/challenge page, or restarting the browser ends capture.

## Use, storage, and sharing

Information is used only to filter, deduplicate, preview, export, and optionally import your collection into your own local application. Collections and settings use this browser profile's local extension storage, not Chrome Storage Sync. Session state uses temporary browser session storage. The extension does not add a separate encryption layer to local storage or exported files; protect your device and exported records accordingly.

The developer does not receive your collection or pairing credentials. There are no analytics, advertisements, data sales, or remote collection servers. No collected information is used for advertising, creditworthiness, or lending. The use of information received from Google APIs adheres to the Chrome Web Store User Data Policy, including the Limited Use requirements.

**Export JSON / Posts CSV / Comments CSV** saves files to a location you choose. Files may contain usernames and personal information from captured text. You control any subsequent sharing of those files.

**Connect / test** sends your pairing token to `/bridge/status` on the local app address you enter. **Send collection to app** sends that token and collected records to `/bridge/import` at the same address. This feature is optional and requires additional localhost permission. Destinations are restricted to `http://127.0.0.1` or `http://localhost` on your computer; redirects are rejected and browser cookies are omitted. HTTP is used only for this same-computer connection. The companion app stores received records in its local database, CSV files and import snapshots. Pairing does not automatically send future captures; each transfer requires the send action.

Opening the optional support link takes you to GitHub, which has its own privacy policy. Do not post private collections, tokens, or account credentials in public support issues. Normal Reddit browsing is governed separately by Reddit's policies.

## Retention and your controls

Collected records remain until you select **Clear local collection**, uninstall the extension, or delete this browser profile's extension data. Storage is capped at 10,000 posts, 20,000 comments and approximately 8 MB of collection data. Existing records can be updated during later captures. Settings and the pairing token remain after clearing the collection. Select **Forget pairing token** to remove the saved token; filters may be edited in the popup. Uninstalling removes the extension's local data, but does not remove exported files or app copies.

Delete exported files and the companion app's database, CSV records and import snapshots separately when required. The extension cannot remotely delete files you have shared. To revoke optional localhost access, use the browser's extension site-access controls or uninstall the extension.

## Permissions

- **Reddit site access** on `www.reddit.com`, `old.reddit.com`, and `reddit.com`: read rendered supported pages during a user-started capture and maintain the selected tab's session. No all-sites permission.
- **storage**: save your collection and settings locally and keep temporary session state.
- **downloads**: create the JSON/CSV exports you request.
- **Optional localhost site access**: authenticate and send records to your own local application when you choose to connect. No remote app destinations.

There are no cookies, browser history, proxy, webRequest, debugger, advertising or remotely hosted executable-code permissions. The extension does not change your browser proxy settings.

## Changes and contact

Changes to data handling will be disclosed in an updated policy and in the extension before the new handling starts. For support or privacy questions, contact the maintainer through [the repository issue tracker](https://github.com/ksanjeev284/reddit-universal-scraper/issues). Describe the concern without including personal records or credentials. Because the developer has no collection server or copy of your local records, deletion of those records is performed through the controls above.
