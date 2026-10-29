"""Validate the static assets and distinct product images before publication."""
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]


class Assets(HTMLParser):
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key not in ('src', 'href') or not value:
                continue
            if value.startswith(('#', 'https:', 'http:', 'mailto:')):
                continue
            path = root / value
            if not path.is_file() or not path.stat().st_size:
                raise SystemExit(f'Missing or empty asset: {value}')


Assets().feed((root / 'index.html').read_text())
app = (root / 'app.js').read_text()
images = re.findall(r"image:'([^']+)'", app)
if len(images) != 6 or len(set(images)) != 6:
    raise SystemExit('Expected six independent product images')
digests = set()
for name in images + ['assets/hero-shoe.png']:
    path = root / name
    if not path.is_file() or not path.stat().st_size:
        raise SystemExit(f'Missing product image: {name}')
    digest = sha256(path.read_bytes()).hexdigest()
    if digest in digests:
        raise SystemExit(f'Duplicate image content: {name}')
    digests.add(digest)
for stylesheet in (root / 'style.css',):
    for name in re.findall(r"url\(['\"]?([^'\")]+)", stylesheet.read_text()):
        if not name.startswith(('data:', 'https:', 'http:')):
            if not (root / name).is_file():
                raise SystemExit(f'Missing stylesheet asset: {name}')
print('KENNY static assets and seven distinct images verified')
