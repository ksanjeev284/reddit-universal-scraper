# Reddit access setup (checked October 2, 2026)

The direct Python scraper uses the official OAuth Data API. For free browser-page capture and standalone exports, see [the browser extension guide](../extension/README.md). The legacy anonymous `.json` route can return HTML even with HTTP 200. Third-party mirrors are not a reliable API replacement.

## Setup

1. Obtain explicit Reddit approval for your app and intended use. Credentials alone do not establish approval. [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy).
2. Copy `.env.example` to `.env` if you do not already have that file. Keep existing proxy/notification settings as needed. Set `REDDIT_USER_AGENT` with your actual app identifier, version and Reddit username.
3. Set `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` for application-only read access. For user-authorized read access, also supply `REDDIT_REFRESH_TOKEN` from the authorized app's OAuth flow with `read` scope. Alternatively set `REDDIT_ACCESS_TOKEN`; a standalone bearer token cannot renew itself. Do not put secrets into command arguments or commit `.env`.
4. Run `python main.py python --check-access`. It fetches at most one listing post and saves no content. Then try `python main.py python --mode history --limit 10 --dry-run`.
5. Run normal jobs after the check succeeds. Docker needs `--env-file .env`; Compose loads `.env` for the scraper and dashboard. Environment values take precedence over the local file.

For the local virtual environment on Windows, replace `python` with `.venv\Scripts\python.exe`.

## Reliability and limitations

- A client's listing/comment requests and OAuth renewals share a lock and rate limiter. Default pacing is 60 requests/minute. Reddit's documented OAuth allowance is 100 queries/minute per client ID, averaged over ten minutes; response headers and your granted limits take precedence. Separate jobs/processes share that allowance and do not share an in-memory limiter. [Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki).
- HTTP 401 triggers one token renewal when client credentials are present. Persistent 401, 403 and 404 produce immediate actionable errors. Rate limits and temporary server/network failures use bounded retries and honor server retry delays.
- Unexpected HTML or malformed listings fail explicitly. Failed runs return `status: failed` and an error; sync jobs record the failure, and CLI exits are nonzero. Posts collected before a later API failure are preserved.
- Listings expose limited recent history. A requested limit is an upper bound, not a guarantee of a complete archive. Comment counts include only the loaded comment tree; `more` placeholders and deeper branches are not expanded.
- Media requests use a separate session with no OAuth bearer headers. TLS verification remains enabled. Optional proxies retain a stable route; they do not grant API access.
- API approval does not remove obligations around retention, commercial use, deletion or exports. Stop using and remove deleted content from local data, media, database copies, exports and backups as required by your agreement. This update does not implement automatic deletion reconciliation. [Reddit deletion requirements](https://support.reddithelp.com/hc/en-us/articles/24656943463828-What-happens-when-I-delete-my-data).

## Upcoming migration

Reddit's October announcement says new public API access requests stop October 31, 2026; access removal for unregistered or unresponsive apps begins January 12, 2027; remaining public API access closes in March 2027. This OAuth update supports currently approved Data API access and is not a Devvit migration. Register your app and establish which Developer Platform capabilities support your use case before relying on this transport long term. [Official migration announcement](https://www.reddit.com/r/redditdev/comments/1wubcvf/moving_data_api_apps_to_the_developer_platform/), [app registration](https://developers.reddit.com/app-registration).

## Tests

Run `python -m unittest discover -s tests -v`. The regression suite uses simulated API responses; it needs no Reddit credentials and does not scrape Reddit.
