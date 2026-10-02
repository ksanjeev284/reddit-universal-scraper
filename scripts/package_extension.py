"""Create a browser-ready, unpackable ZIP with no developer dependencies."""
import hashlib
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
extension = root / "extension"
files = ["manifest.json", "background.js", "collector.js", "content.js", "popup.html", "popup.css", "popup.js", "privacy.html", "privacy.css", "README.md",
         *[f"icons/icon{size}.png" for size in (16, 32, 48, 128)]]
for filename in files:
    if not (extension / filename).is_file():
        raise SystemExit(f"Missing extension file: {filename}")
destination = root / "dist" / "browser-collector-extension.zip"
destination.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
    for filename in files:
        archive.write(extension / filename, filename)
    archive.write(root / "LICENSE", "LICENSE")
with zipfile.ZipFile(destination) as archive:
    if archive.testzip() is not None:
        raise SystemExit("Extension ZIP verification failed.")
print(destination)
print(f"SHA256: {hashlib.sha256(destination.read_bytes()).hexdigest()}")
