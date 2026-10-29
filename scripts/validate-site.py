"""Validate the static assets and distinct product images before publication."""
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import re

root = Path(__file__).resolve().parents[1]


class Assets(HTMLParser):
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key not in ('src', 'href') or not value:
                continue
            if value.startswith(('#', 'https:', 'http:', 'mailto:')):
                continue
            path = root / urlsplit(value).path
            if not path.is_file() or not path.stat().st_size:
                raise SystemExit(f'Missing or empty asset: {value}')


pages = sorted(root.glob('*.html'))
if len(pages) != 11:
    raise SystemExit('Expected eight store pages and three policy pages')
for page in pages:
    Assets().feed(page.read_text())
app = (root / 'app.js').read_text()
images = re.findall(r"image:'([^']+)'", app)
if len(images) != len(set(images)) or len(images) < 6:
    raise SystemExit('Expected distinct product images')
digests = set()
for name in images + ['assets/campaign-dark.png']:
    path = root / name
    if not path.is_file() or not path.stat().st_size:
        raise SystemExit(f'Missing product image: {name}')
    digest = sha256(path.read_bytes()).hexdigest()
    if digest in digests:
        raise SystemExit(f'Duplicate image content: {name}')
    digests.add(digest)
for stylesheet in (root / 'style.css', root / 'cinema.css', root / 'typography.css', root / 'intro.css', root / 'motion.css'):
    for name in re.findall(r"url\(['\"]?([^'\")]+)", stylesheet.read_text()):
        if not name.startswith(('data:', 'https:', 'http:')):
            if not (root / name).is_file():
                raise SystemExit(f'Missing stylesheet asset: {name}')
print('KENNY eleven pages, static assets and distinct images verified')

# Every translated source phrase must be present in both non-English dictionaries.
import json
zh = json.loads((root / "translations.json").read_text())
ms = json.loads((root / "translations-ms.json").read_text())
if set(zh) != set(ms) or not all(isinstance(v, str) and v.strip() for v in ms.values()):
    raise SystemExit("Chinese and Malay translation coverage differs")
print(f"Three-language dictionaries verified: {len(zh)} phrases per translated language")
