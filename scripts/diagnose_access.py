"""One anonymous legacy request to diagnose availability; never stores content."""
import json
import urllib.error
import urllib.request

url = "https://old.reddit.com/r/python/new.json?limit=1&raw_json=1"
request = urllib.request.Request(url, headers={"User-Agent": "reddit-universal-scraper/2.0 access-diagnostic"})
try:
    with urllib.request.urlopen(request, timeout=20) as response:
        content_type = response.headers.get("Content-Type", "")
        print(f"Legacy anonymous endpoint: HTTP {response.status}; {content_type}")
        if "json" in content_type:
            data = json.load(response)
            print(f"Post count: {len(data.get('data', {}).get('children', []))}")
except urllib.error.HTTPError as error:
    print(f"Legacy anonymous endpoint: HTTP {error.code}; {error.headers.get('Content-Type', '')}")
except urllib.error.URLError:
    print("Legacy anonymous endpoint: network connection failed")
