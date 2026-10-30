from __future__ import annotations
import asyncio
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SIZES = list(range(38, 46))
COOKIE = 'kenny_session'


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password):
    salt = secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ':' + value


def password_matches(password, stored):
    salt, expected = stored.split(':')
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(value, expected)


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Credentials(Model):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=256)

    @field_validator('email')
    @classmethod
    def email_address(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Enter a valid email address')
        return value


class Registration(Credentials):
    name: str = Field(min_length=2, max_length=100)
    accepted_terms: Literal[True]
    adult: Literal[True]


class Bootstrap(Registration):
    bootstrap_token: str = Field(min_length=20, max_length=200)


class Product(Model):
    id: str = Field(pattern=r'^[a-z0-9][a-z0-9-]{1,59}$')
    name: str = Field(min_length=2, max_length=100)
    category: Literal['Running', 'Lifestyle', 'Training', 'Outdoor']
    audience: Literal['Unisex', 'Men', 'Women', 'Kids'] = 'Unisex'
    color: str = Field(max_length=100)
    price_cents: int = Field(ge=100, le=10000000)
    original_price_cents: int | None = Field(default=None, ge=100, le=10000000)
    description: str = Field(min_length=5, max_length=3000)
    badge: str = Field(default='', max_length=60)
    image: str = Field(pattern=r'^(assets|uploads)/[A-Za-z0-9_-]+\.(png|jpg|jpeg|webp)$')
    bg: str = Field(default='#e2eaf0', pattern=r'^#[a-fA-F0-9]{6}$')
    active: bool = True
    outlet: bool = False
    translations: dict = Field(default_factory=dict)

    @field_validator('translations')
    @classmethod
    def localized_fields(cls, value):
        if set(value) - {'zh', 'ms'}:
            raise ValueError('Supported translations: zh, ms')
        for fields in value.values():
            if not isinstance(fields, dict) or set(fields) - {'name', 'description', 'color', 'badge'}:
                raise ValueError('Invalid translated product fields')
            if any(not isinstance(v, str) or len(v) > 3000 for v in fields.values()):
                raise ValueError('Invalid translation value')
        return value


class Stock(Model):
    size: int = Field(ge=15, le=55)
    quantity: int = Field(ge=0, le=100000)
    note: str = Field(min_length=3, max_length=300)


class CartLine(Model):
    id: str = Field(max_length=60)
    size: int = Field(ge=15, le=55)
    qty: int = Field(ge=1, le=10)


class Quote(Model):
    items: list[CartLine] = Field(min_length=1, max_length=30)
    coupon: str = Field(default='', max_length=30)


class OrderInput(Quote):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    phone: str = Field(min_length=7, max_length=30)
    address: str = Field(min_length=8, max_length=500)
    postcode: str = Field(pattern=r'^\d{5}$')
    payment: Literal['manual'] = 'manual'
    idempotency_key: str = Field(min_length=16, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')


class Coupon(Model):
    code: str = Field(pattern=r'^[A-Z0-9_-]{3,30}$')
    percent: int = Field(ge=1, le=80)
    minimum_cents: int = Field(default=0, ge=0)
    max_uses: int = Field(default=100, ge=1, le=100000)
    per_customer: int = Field(default=1, ge=1, le=1000)
    active: bool = True
    expires_at: str | None = None

    @field_validator('expires_at')
    @classmethod
    def expiry(cls, value):
        if value:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                raise ValueError('Expiry must include timezone')
            return dt.astimezone(timezone.utc).isoformat()
        return value


class OrderAction(Model):
    action: Literal['mark_paid', 'process', 'ship', 'complete', 'cancel', 'approve_refund', 'decline_refund']
    note: str = Field(min_length=3, max_length=1000)
    tracking_number: str = Field(default='', max_length=120)
    carrier: str = Field(default='', max_length=100)


class Message(Model):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    topic: str = Field(default='General', max_length=100)
    message: str = Field(min_length=5, max_length=4000)


class Subscription(Model):
    email: str = Field(min_length=5, max_length=254)



class Review(Model):
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=5, max_length=1000)


class Reason(Model):
    reason: str = Field(min_length=5, max_length=1000)


class Wishlist(Model):
    ids: list[str] = Field(max_length=100)


class AccountState(Model):
    active: bool


class Note(Model):
    note: str = Field(min_length=1, max_length=1000)
    status: Literal['unread', 'in_progress', 'resolved']


class Moderation(Model):
    status: Literal['published', 'rejected', 'pending']


class Store(Model):
    id: str = Field(pattern=r'^[a-z0-9-]{2,50}$')
    name: str = Field(min_length=2, max_length=120)
    city: str = Field(min_length=2, max_length=80)
    address: str = Field(min_length=5, max_length=400)
    hours: str = Field(default='', max_length=200)
    map_url: str = Field(default='', max_length=500)
    active: bool = True

    @field_validator('map_url')
    @classmethod
    def map_link(cls, value):
        if value and not re.fullmatch(r'https://[^\s<>"\']+', value):
            raise ValueError('Map URL must use HTTPS')
        return value


class Settings(Model):
    store_name: str = Field(min_length=2, max_length=80)
    shipping_cents: int = Field(ge=0, le=100000)
    free_shipping_cents: int = Field(ge=0, le=10000000)
    social_links: dict = Field(default_factory=dict)
    support_email: str = Field(default='', max_length=254)
    stores: list[Store] = Field(default_factory=list, max_length=30)

    @field_validator('social_links')
    @classmethod
    def links(cls, value):
        if set(value) - {'facebook', 'instagram', 'tiktok', 'threads', 'telegram'}:
            raise ValueError('Invalid social platform')
        if any(not isinstance(v, str) or len(v) > 500 or (v and not re.fullmatch(r'https://[^\s<>"\']+', v)) for v in value.values()):
            raise ValueError('Social URLs must use HTTPS')
        return value


class PasswordChange(Model):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


def create_app(data_dir=None, secure_cookie=None):
    directory = Path(data_dir or os.environ.get('KENNY_DATA_DIR', ROOT / '.data'))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    uploads = directory / 'uploads'
    uploads.mkdir(mode=0o700, exist_ok=True)
    database = directory / 'kenny.sqlite3'
    secure = secure_cookie if secure_cookie is not None else os.environ.get('KENNY_COOKIE_SECURE') == '1'
    production = os.environ.get('KENNY_ENV') == 'production'
    if production and not secure:
        raise RuntimeError('Production requires KENNY_COOKIE_SECURE=1 and an HTTPS reverse proxy')
    allowed_origins = set(filter(None, os.environ.get('KENNY_ALLOWED_ORIGINS', '').split(',')))
    # Render supplies the exact public HTTPS origin behind its TLS proxy.
    render_origin = os.environ.get('RENDER_EXTERNAL_URL', '').rstrip('/')
    if re.fullmatch(r'https://[a-zA-Z0-9.-]+(?::[0-9]+)?', render_origin):
        allowed_origins.add(render_origin)
    bootstrap_path = directory / 'bootstrap-token'
    if not bootstrap_path.exists():
        fd = os.open(bootstrap_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(secrets.token_urlsafe(32))

    @contextmanager
    def db(write=False):
        conn = sqlite3.connect(database, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        try:
            if write:
                conn.execute('BEGIN IMMEDIATE')
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    with db() as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'customer',active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),csrf TEXT NOT NULL,expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY,data TEXT NOT NULL,active INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS variants(product_id TEXT REFERENCES products(id),size INTEGER NOT NULL,stock INTEGER NOT NULL CHECK(stock>=0),PRIMARY KEY(product_id,size));
        CREATE TABLE IF NOT EXISTS coupons(code TEXT PRIMARY KEY,data TEXT NOT NULL,uses INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),status TEXT NOT NULL,payment_status TEXT NOT NULL,total_cents INTEGER NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,idempotency_key TEXT NOT NULL,payload_hash TEXT NOT NULL,UNIQUE(user_id,idempotency_key));
        CREATE TABLE IF NOT EXISTS order_items(order_id TEXT REFERENCES orders(id),product_id TEXT,size INTEGER,qty INTEGER,price_cents INTEGER,name TEXT,image TEXT);
        CREATE TABLE IF NOT EXISTS order_events(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id TEXT REFERENCES orders(id),status TEXT NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),data TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'unread',note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,product_id TEXT REFERENCES products(id),user_id TEXT REFERENCES users(id),rating INTEGER NOT NULL,text TEXT NOT NULL,status TEXT NOT NULL,verified INTEGER NOT NULL,created_at TEXT NOT NULL,UNIQUE(product_id,user_id));
        CREATE TABLE IF NOT EXISTS wishlists(user_id TEXT REFERENCES users(id),product_id TEXT REFERENCES products(id),PRIMARY KEY(user_id,product_id));
        CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT,action TEXT NOT NULL,target TEXT NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS subscribers(email TEXT PRIMARY KEY,created_at TEXT NOT NULL);
        ''')
        if not conn.execute('SELECT 1 FROM products LIMIT 1').fetchone():
            zh = json.loads((ROOT / 'translations.json').read_text())
            ms = json.loads((ROOT / 'translations-ms.json').read_text())
            for item in json.loads((ROOT / 'backend/seed.json').read_text()):
                item['price_cents'] = round(item.pop('price') * 100)
                item['original_price_cents'] = round(item.pop('originalPrice') * 100) if item.get('originalPrice') else None
                item['audience'] = item.get('audience', 'Unisex')
                sizes = item.pop('sizes', DEFAULT_SIZES)
                item['active'] = True
                item['translations'] = {lang: {key: dictionary.get(item.get(key, ''), item.get(key, '')) for key in ['name', 'description', 'color', 'badge']} for lang, dictionary in [('zh', zh), ('ms', ms)]}
                clean = Product.model_validate({k: v for k, v in item.items() if k in Product.model_fields}).model_dump()
                conn.execute('INSERT INTO products VALUES(?,?,?,?,?)', (item['id'], json.dumps(clean), 1, stamp(), stamp()))
                conn.executemany('INSERT INTO variants VALUES(?,?,?)', [(item['id'], size, 0 if production else 12) for size in sizes])
            coupon = Coupon(code='KENNY10', percent=10, max_uses=1000).model_dump()
            conn.execute('INSERT OR IGNORE INTO coupons(code,data) VALUES(?,?)', ('KENNY10', json.dumps(coupon)))
        conn.execute('INSERT OR IGNORE INTO settings VALUES(1,?)', (json.dumps({'store_name': 'KENNY', 'shipping_cents': 1500, 'free_shipping_cents': 50000, 'social_links': {}, 'support_email': ''}),))
    try:
        database.chmod(0o600)
    except OSError:
        pass

    def audit(conn, actor, action, target, note=''):
        conn.execute('INSERT INTO audit(actor,action,target,note,created_at) VALUES(?,?,?,?,?)', (actor, action, target, note, stamp()))

    def event(conn, order_id, status, note):
        conn.execute('INSERT INTO order_events(order_id,status,note,created_at) VALUES(?,?,?,?)', (order_id, status, note, stamp()))

    def release(conn, row, status, note):
        if row['status'] in ('cancelled', 'expired', 'refunded'):
            return
        for item in conn.execute('SELECT * FROM order_items WHERE order_id=?', (row['id'],)):
            conn.execute('UPDATE variants SET stock=stock+? WHERE product_id=? AND size=?', (item['qty'], item['product_id'], item['size']))
        data = json.loads(row['data'])
        if data.get('coupon'):
            conn.execute('UPDATE coupons SET uses=MAX(0,uses-1) WHERE code=?', (data['coupon'],))
        conn.execute('UPDATE orders SET status=?,updated_at=? WHERE id=?', (status, stamp(), row['id']))
        event(conn, row['id'], status, note)

    def expire(conn):
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(timespec='seconds')
        for row in conn.execute("SELECT * FROM orders WHERE status='pending_payment' AND created_at<?", (cutoff,)).fetchall():
            release(conn, row, 'expired', 'Unpaid reservation expired after 30 minutes')
        conn.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))

    @asynccontextmanager
    async def lifespan(app):
        async def sweep():
            while True:
                await asyncio.sleep(60)
                await asyncio.to_thread(sweep_once)
        def sweep_once():
            with db(True) as conn:
                expire(conn)
        task = asyncio.create_task(sweep())
        yield
        task.cancel()

    app = FastAPI(title='KENNY Commerce API', version='1.0.0', lifespan=lifespan, docs_url=None if production else '/api/docs', openapi_url=None if production else '/api/openapi.json')
    app.state.database = database
    app.state.data_dir = directory
    rate_lock = Lock()
    rates = {}
    dummy_hash = password_hash('not-a-real-account-password')

    def limit(request, kind, count=12, window=600):
        key = (request.client.host if request.client else 'unknown', kind)
        now = time.time()
        with rate_lock:
            if len(rates) > 5000:
                for entry in list(rates):
                    rates[entry] = [t for t in rates[entry] if now-t < 3600]
                    if not rates[entry]:
                        del rates[entry]
            values = [t for t in rates.get(key, []) if now-t < window]
            if len(values) >= count:
                raise HTTPException(429, 'Too many attempts. Please try again later.')
            rates[key] = values + [now]

    @app.middleware('http')
    async def request_policy(request, call_next):
        if request.method in ('POST', 'PUT', 'PATCH'):
            size = request.headers.get('content-length')
            if not size or not size.isdigit():
                return JSONResponse({'detail': 'Content-Length is required'}, 411)
            maximum = 8 * 1024 * 1024 if request.url.path == '/api/admin/uploads' else 131072
            if int(size) > maximum:
                return JSONResponse({'detail': 'Request body too large'}, 413)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.url.path.startswith(('/api/', '/admin')):
            response.headers['Cache-Control'] = 'no-store'
        return response

    def current_session(request):
        raw = request.cookies.get(COOKIE, '')
        with db() as conn:
            row = conn.execute('SELECT s.*,u.role,u.active,u.name,u.email FROM sessions s LEFT JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?', (digest(raw), time.time())).fetchone() if raw else None
        return dict(row) if row and (not row['user_id'] or row['active']) else None

    def csrf(request):
        session = current_session(request)
        if not session or not hmac.compare_digest(session['csrf'], request.headers.get('x-csrf-token', '')):
            raise HTTPException(403, 'Refresh the page and try again (CSRF token required)')
        origin = request.headers.get('origin')
        base = str(request.base_url).rstrip('/')
        if origin and origin != base and origin not in allowed_origins:
            raise HTTPException(403, 'Origin not allowed')
        if request.headers.get('sec-fetch-site') == 'cross-site' and origin not in allowed_origins:
            raise HTTPException(403, 'Cross-site request blocked')
        return session

    def user(request, admin=False, mutation=False):
        session = csrf(request) if mutation else current_session(request)
        if not session or not session['user_id']:
            raise HTTPException(401, 'Please log in')
        if admin and session['role'] != 'admin':
            raise HTTPException(403, 'Administrator access required')
        return session

    def public_user(row):
        return {'id': row['user_id'] if 'user_id' in row else row['id'], 'name': row['name'], 'email': row['email'], 'role': row['role']} if row and (row.get('user_id') if isinstance(row, dict) and 'user_id' in row else True) else None

    def set_session(request, response, user_id=None):
        token, token_csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(32)
        with db(True) as conn:
            old = request.cookies.get(COOKIE)
            if old:
                conn.execute('DELETE FROM sessions WHERE token=?', (digest(old),))
            conn.execute('INSERT INTO sessions VALUES(?,?,?,?)', (digest(token), user_id, token_csrf, time.time()+7*86400))
            row = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone() if user_id else None
        response.set_cookie(COOKIE, token, max_age=7*86400, httponly=True, secure=secure, samesite='lax', path='/')
        return {'user': public_user(dict(row)) if row else None, 'csrf': token_csrf}

    def settings(conn):
        return json.loads(conn.execute('SELECT data FROM settings WHERE id=1').fetchone()[0])

    def product_out(conn, row, admin=False):
        data = json.loads(row['data'])
        variants = [dict(v) for v in conn.execute('SELECT size,stock FROM variants WHERE product_id=? ORDER BY size', (row['id'],))]
        data.update(price=data['price_cents']/100, originalPrice=(data.get('original_price_cents') or 0)/100, filter='none', tone=data['bg'], sizes=[v['size'] for v in variants], stock={str(v['size']): v['stock'] for v in variants})
        if admin:
            data.update(created_at=row['created_at'], updated_at=row['updated_at'], total_stock=sum(v['stock'] for v in variants))
        return data

    def quote(conn, payload, user_id):
        seen = set()
        lines, subtotal = [], 0
        for item in payload.items:
            key = (item.id, item.size)
            if key in seen:
                raise HTTPException(400, 'Duplicate product/size lines are not allowed')
            seen.add(key)
            row = conn.execute('SELECT p.*,v.stock FROM products p JOIN variants v ON v.product_id=p.id WHERE p.id=? AND v.size=? AND p.active=1', key).fetchone()
            if not row or row['stock'] < item.qty:
                raise HTTPException(409, 'A selected size is unavailable or has insufficient stock')
            data = json.loads(row['data'])
            subtotal += data['price_cents'] * item.qty
            lines.append({'id': item.id, 'size': item.size, 'qty': item.qty, 'price_cents': data['price_cents'], 'name': data['name'], 'image': data['image']})
        code = payload.coupon.strip().upper()
        discount = 0
        if code:
            coupon_row = conn.execute('SELECT * FROM coupons WHERE code=?', (code,)).fetchone()
            if not coupon_row:
                raise HTTPException(400, 'Coupon is not valid')
            coupon = json.loads(coupon_row['data'])
            used = conn.execute("SELECT count(*) FROM orders WHERE user_id=? AND json_extract(data,'$.coupon')=? AND status NOT IN ('cancelled','expired','refunded')", (user_id, code)).fetchone()[0]
            if not coupon['active'] or coupon_row['uses'] >= coupon['max_uses'] or used >= coupon['per_customer'] or subtotal < coupon['minimum_cents'] or (coupon.get('expires_at') and coupon['expires_at'] <= stamp()):
                raise HTTPException(400, 'Coupon is expired, used or ineligible')
            discount = (subtotal * coupon['percent'] + 50) // 100
        config = settings(conn)
        shipping = 0 if subtotal-discount >= config['free_shipping_cents'] else config['shipping_cents']
        return {'items': lines, 'currency': 'MYR', 'subtotal_cents': subtotal, 'discount_cents': discount, 'shipping_cents': shipping, 'total_cents': subtotal-discount+shipping, 'coupon': code}

    def order_out(conn, row, include_contact=False):
        data = json.loads(row['data'])
        result = {'id': row['id'], 'status': row['status'], 'payment_status': row['payment_status'], 'total_cents': row['total_cents'], 'currency': 'MYR', 'created_at': row['created_at'], 'updated_at': row['updated_at'], 'items': [dict(v) for v in conn.execute('SELECT product_id AS id,size,qty,price_cents,name,image FROM order_items WHERE order_id=?', (row['id'],))], 'events': [dict(v) for v in conn.execute('SELECT status,note,created_at FROM order_events WHERE order_id=? ORDER BY id', (row['id'],))]}
        for field in ['subtotal_cents', 'discount_cents', 'shipping_cents', 'coupon', 'tracking_number', 'carrier', 'refund_reason']:
            if field in data:
                result[field] = data[field]
        if include_contact:
            result['customer'] = data['customer']
        return result

    @app.get('/api/health')
    def health():
        with db() as conn:
            conn.execute('SELECT 1')
        return {'service': 'kenny-api', 'status': 'ok', 'payments': 'manual_only'}

    @app.get('/api/auth/session')
    def session(request: Request, response: Response):
        existing = current_session(request)
        return {'user': public_user(existing), 'csrf': existing['csrf']} if existing else set_session(request, response)

    @app.get('/api/setup/status')
    def setup_status():
        with db() as conn:
            required = not conn.execute("SELECT 1 FROM users WHERE role='admin'").fetchone()
        return {'required': required}

    @app.post('/api/setup')
    def bootstrap(payload: Bootstrap, request: Request, response: Response):
        csrf(request)
        limit(request, 'bootstrap', 5, 600)
        expected = os.environ.get('KENNY_BOOTSTRAP_TOKEN') or bootstrap_path.read_text().strip()
        if not hmac.compare_digest(payload.bootstrap_token, expected):
            raise HTTPException(403, 'Invalid setup token')
        with db(True) as conn:
            if conn.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
                raise HTTPException(409, 'Setup is already complete')
            uid = str(uuid.uuid4())
            try:
                conn.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)', (uid, payload.email, payload.name.strip(), password_hash(payload.password), 'admin', 1, stamp()))
            except sqlite3.IntegrityError:
                raise HTTPException(409, 'That email is already registered')
            audit(conn, uid, 'setup', uid)
        return set_session(request, response, uid)

    @app.post('/api/auth/register')
    def register(payload: Registration, request: Request, response: Response):
        csrf(request)
        limit(request, 'register', 5, 3600)
        uid = str(uuid.uuid4())
        with db(True) as conn:
            try:
                conn.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)', (uid, payload.email, payload.name.strip(), password_hash(payload.password), 'customer', 1, stamp()))
            except sqlite3.IntegrityError:
                raise HTTPException(409, 'That email is already registered')
            audit(conn, uid, 'register', uid)
        return set_session(request, response, uid)

    @app.post('/api/auth/login')
    def login(payload: Credentials, request: Request, response: Response):
        csrf(request)
        limit(request, 'login')
        with db() as conn:
            row = conn.execute('SELECT * FROM users WHERE email=?', (payload.email,)).fetchone()
        valid = password_matches(payload.password, row['password'] if row else dummy_hash)
        if not row or not valid or not row['active']:
            raise HTTPException(401, 'Email or password is incorrect')
        return set_session(request, response, row['id'])

    @app.post('/api/auth/logout')
    def logout(request: Request, response: Response):
        csrf(request)
        return set_session(request, response)

    @app.post('/api/auth/password')
    def change_password(payload: PasswordChange, request: Request):
        actor = user(request, mutation=True)
        with db(True) as conn:
            row = conn.execute('SELECT password FROM users WHERE id=?', (actor['user_id'],)).fetchone()
            if not password_matches(payload.current_password, row['password']):
                raise HTTPException(400, 'Current password is incorrect')
            conn.execute('UPDATE users SET password=? WHERE id=?', (password_hash(payload.new_password), actor['user_id']))
            conn.execute('DELETE FROM sessions WHERE user_id=? AND token<>?', (actor['user_id'], actor['token']))
            audit(conn, actor['user_id'], 'password_changed', actor['user_id'])
        return {'ok': True}

    @app.get('/api/products')
    def products():
        with db() as conn:
            return {'products': [product_out(conn, row) for row in conn.execute('SELECT * FROM products WHERE active=1 ORDER BY created_at,id').fetchall()]}

    @app.get('/api/settings')
    def public_settings():
        with db() as conn:
            return settings(conn)

    @app.post('/api/checkout/quote')
    def checkout_quote(payload: Quote, request: Request):
        actor = user(request, mutation=True)
        with db(True) as conn:
            expire(conn)
            return quote(conn, payload, actor['user_id'])

    @app.post('/api/orders')
    def place_order(payload: OrderInput, request: Request):
        actor = user(request, mutation=True)
        limit(request, 'order', 30, 600)
        payload_hash = digest(json.dumps(payload.model_dump(), sort_keys=True))
        with db(True) as conn:
            expire(conn)
            prior = conn.execute('SELECT * FROM orders WHERE user_id=? AND idempotency_key=?', (actor['user_id'], payload.idempotency_key)).fetchone()
            if prior:
                if prior['payload_hash'] != payload_hash:
                    raise HTTPException(409, 'This checkout key was already used for another order')
                return order_out(conn, prior, True)
            calculation = quote(conn, payload, actor['user_id'])
            oid = 'KNY-' + datetime.now(timezone.utc).strftime('%y%m%d') + '-' + secrets.token_hex(4).upper()
            data = {**calculation, 'customer': {k: getattr(payload, k) for k in ['name', 'email', 'phone', 'address', 'postcode']}, 'payment': 'manual'}
            conn.execute('INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?)', (oid, actor['user_id'], 'pending_payment', 'unpaid', calculation['total_cents'], json.dumps(data), stamp(), stamp(), payload.idempotency_key, payload_hash))
            for line in calculation['items']:
                changed = conn.execute('UPDATE variants SET stock=stock-? WHERE product_id=? AND size=? AND stock>=?', (line['qty'], line['id'], line['size'], line['qty'])).rowcount
                if not changed:
                    raise HTTPException(409, 'Stock changed; please refresh your bag')
                conn.execute('INSERT INTO order_items VALUES(?,?,?,?,?,?,?)', (oid, line['id'], line['size'], line['qty'], line['price_cents'], line['name'], line['image']))
            if calculation['coupon']:
                conn.execute('UPDATE coupons SET uses=uses+1 WHERE code=?', (calculation['coupon'],))
            event(conn, oid, 'pending_payment', 'Order received. No payment collected. Stock held for 30 minutes.')
            audit(conn, actor['user_id'], 'order_created', oid)
            return order_out(conn, conn.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone(), True)

    @app.get('/api/orders')
    def my_orders(request: Request):
        actor = user(request)
        with db(True) as conn:
            expire(conn)
            return {'orders': [order_out(conn, row) for row in conn.execute('SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 100', (actor['user_id'],)).fetchall()]}

    def owned_order(conn, oid, uid):
        row = conn.execute('SELECT * FROM orders WHERE id=? AND user_id=?', (oid, uid)).fetchone()
        if not row:
            raise HTTPException(404, 'Order not found')
        return row

    @app.get('/api/orders/{oid}')
    def order_detail(oid: str, request: Request):
        actor = user(request)
        with db(True) as conn:
            expire(conn)
            return order_out(conn, owned_order(conn, oid, actor['user_id']), True)

    @app.post('/api/orders/{oid}/cancel')
    def cancel_order(oid: str, request: Request):
        actor = user(request, mutation=True)
        with db(True) as conn:
            row = owned_order(conn, oid, actor['user_id'])
            if row['status'] != 'pending_payment':
                raise HTTPException(409, 'Only unpaid orders can be cancelled directly')
            release(conn, row, 'cancelled', 'Cancelled by customer')
            audit(conn, actor['user_id'], 'order_cancelled', oid)
        return {'ok': True}

    @app.post('/api/orders/{oid}/refund-request')
    def request_refund(oid: str, payload: Reason, request: Request):
        actor = user(request, mutation=True)
        with db(True) as conn:
            row = owned_order(conn, oid, actor['user_id'])
            if row['payment_status'] != 'paid' or row['status'] not in ('paid', 'processing', 'shipped', 'completed'):
                raise HTTPException(409, 'This order is not eligible for a refund request')
            data = json.loads(row['data'])
            data.update(refund_reason=payload.reason, status_before_refund=row['status'])
            conn.execute("UPDATE orders SET status='refund_requested',data=?,updated_at=? WHERE id=?", (json.dumps(data), stamp(), oid))
            event(conn, oid, 'refund_requested', 'Customer requested a refund')
        return {'ok': True}

    @app.get('/api/wishlist')
    def get_wishlist(request: Request):
        actor = user(request)
        with db() as conn:
            return {'ids': [r[0] for r in conn.execute('SELECT product_id FROM wishlists WHERE user_id=?', (actor['user_id'],))]}

    @app.put('/api/wishlist')
    def put_wishlist(payload: Wishlist, request: Request):
        actor = user(request, mutation=True)
        with db(True) as conn:
            for pid in payload.ids:
                if not conn.execute('SELECT 1 FROM products WHERE id=?', (pid,)).fetchone():
                    raise HTTPException(400, 'Unknown product')
            conn.execute('DELETE FROM wishlists WHERE user_id=?', (actor['user_id'],))
            conn.executemany('INSERT OR IGNORE INTO wishlists VALUES(?,?)', [(actor['user_id'], pid) for pid in payload.ids])
        return {'ok': True}

    @app.post('/api/contact')
    def contact(payload: Message, request: Request):
        csrf(request)
        limit(request, 'contact', 10, 3600)
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', payload.email):
            raise HTTPException(400, 'Enter a valid email address')
        mid = str(uuid.uuid4())
        with db(True) as conn:
            session = current_session(request)
            conn.execute('INSERT INTO messages(id,user_id,data,created_at) VALUES(?,?,?,?)', (mid, session['user_id'], json.dumps(payload.model_dump()), stamp()))
        return {'id': mid, 'message': 'Message saved. Email delivery is not connected.'}

    @app.post('/api/newsletter')
    def newsletter(payload: Subscription, request: Request):
        csrf(request)
        limit(request, 'newsletter', 5, 3600)
        email = payload.email.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise HTTPException(400, 'Enter a valid email address')
        with db(True) as conn:
            conn.execute('INSERT OR IGNORE INTO subscribers VALUES(?,?)', (email, stamp()))
        return {'ok': True, 'notice': 'Subscription saved. No email has been sent.'}

    @app.get('/api/admin/subscribers')
    def subscribers(request: Request):
        user(request, admin=True)
        with db() as conn:
            return {'subscribers': [dict(r) for r in conn.execute('SELECT email,created_at FROM subscribers ORDER BY created_at DESC LIMIT 500')]}

    @app.get('/api/products/{pid}/reviews')
    def reviews(pid: str):
        with db() as conn:
            return {'reviews': [dict(r) for r in conn.execute("SELECT r.id,u.name,r.rating,r.text,r.verified,r.created_at FROM reviews r JOIN users u ON u.id=r.user_id WHERE product_id=? AND status='published' ORDER BY r.created_at DESC LIMIT 100", (pid,))]}

    @app.post('/api/products/{pid}/reviews')
    def add_review(pid: str, payload: Review, request: Request):
        actor = user(request, mutation=True)
        with db(True) as conn:
            if not conn.execute('SELECT 1 FROM products WHERE id=?', (pid,)).fetchone():
                raise HTTPException(404, 'Product not found')
            verified = bool(conn.execute("SELECT 1 FROM orders o JOIN order_items i ON i.order_id=o.id WHERE o.user_id=? AND i.product_id=? AND o.status='completed' AND o.payment_status='paid'", (actor['user_id'], pid)).fetchone())
            try:
                conn.execute('INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?)', (str(uuid.uuid4()), pid, actor['user_id'], payload.rating, payload.text, 'pending', int(verified), stamp()))
            except sqlite3.IntegrityError:
                raise HTTPException(409, 'You have already reviewed this product')
        return {'status': 'pending', 'message': 'Review submitted for moderation'}

    @app.get('/api/admin/dashboard')
    def dashboard(request: Request, days: int = 30):
        user(request, admin=True)
        days = days if days in (7, 30, 90) else 30
        since = (datetime.now(timezone.utc)-timedelta(days=days)).isoformat(timespec='seconds')
        with db(True) as conn:
            expire(conn)
            totals = dict(conn.execute("SELECT COUNT(*) AS orders,COALESCE(SUM(CASE WHEN payment_status='paid' THEN total_cents ELSE 0 END),0) AS paid_revenue_cents,COALESCE(SUM(CASE WHEN status='pending_payment' THEN 1 ELSE 0 END),0) AS pending,COALESCE(SUM(CASE WHEN status='refund_requested' THEN 1 ELSE 0 END),0) AS refund_requests FROM orders WHERE created_at>=?", (since,)).fetchone())
            totals.update(customers=conn.execute("SELECT count(*) FROM users WHERE role='customer'").fetchone()[0], products=conn.execute('SELECT count(*) FROM products WHERE active=1').fetchone()[0], low_stock=conn.execute('SELECT count(*) FROM variants WHERE stock<=3').fetchone()[0], unread_messages=conn.execute("SELECT count(*) FROM messages WHERE status='unread'").fetchone()[0])
            trend = [dict(r) for r in conn.execute("SELECT substr(created_at,1,10) AS day,count(*) AS orders,COALESCE(sum(CASE WHEN payment_status='paid' THEN total_cents ELSE 0 END),0) AS revenue_cents FROM orders WHERE created_at>=? GROUP BY day ORDER BY day", (since,))]
            statuses = [dict(r) for r in conn.execute('SELECT status,count(*) AS count FROM orders WHERE created_at>=? GROUP BY status', (since,))]
            top = [dict(r) for r in conn.execute("SELECT i.name,sum(i.qty) AS quantity,sum(i.qty*i.price_cents) AS revenue_cents FROM order_items i JOIN orders o ON o.id=i.order_id WHERE o.payment_status='paid' AND o.created_at>=? GROUP BY i.product_id ORDER BY quantity DESC LIMIT 5", (since,))]
            recent = [order_out(conn, row, True) for row in conn.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT 6').fetchall()]
        return {'totals': totals, 'trend': trend, 'statuses': statuses, 'top_products': top, 'recent_orders': recent, 'days': days, 'currency': 'MYR'}

    @app.get('/api/admin/products')
    def admin_products(request: Request):
        user(request, admin=True)
        with db() as conn:
            return {'products': [product_out(conn, row, True) for row in conn.execute('SELECT * FROM products ORDER BY created_at,id').fetchall()]}

    @app.put('/api/admin/products/{pid}')
    def save_product(pid: str, payload: Product, request: Request):
        actor = user(request, admin=True, mutation=True)
        if pid != payload.id:
            raise HTTPException(400, 'Product ID cannot change')
        image_path = ROOT / payload.image if payload.image.startswith('assets/') else directory / payload.image
        if not image_path.is_file():
            raise HTTPException(400, 'Upload the product image first')
        if payload.original_price_cents and payload.original_price_cents < payload.price_cents:
            raise HTTPException(400, 'Original price must not be lower than sale price')
        with db(True) as conn:
            conn.execute('INSERT INTO products VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,active=excluded.active,updated_at=excluded.updated_at', (pid, json.dumps(payload.model_dump()), int(payload.active), stamp(), stamp()))
            audit(conn, actor['user_id'], 'product_saved', pid)
        return {'ok': True}

    @app.put('/api/admin/products/{pid}/stock')
    def update_stock(pid: str, payload: Stock, request: Request):
        actor = user(request, admin=True, mutation=True)
        with db(True) as conn:
            if not conn.execute('SELECT 1 FROM products WHERE id=?', (pid,)).fetchone():
                raise HTTPException(404, 'Product not found')
            conn.execute('INSERT INTO variants VALUES(?,?,?) ON CONFLICT(product_id,size) DO UPDATE SET stock=excluded.stock', (pid, payload.size, payload.quantity))
            audit(conn, actor['user_id'], 'stock_adjustment', pid, f'EU {payload.size}: {payload.quantity}; {payload.note}')
        return {'ok': True}

    @app.post('/api/admin/uploads')
    async def upload(request: Request):
        actor = user(request, admin=True, mutation=True)
        if request.headers.get('content-type', '').split(';')[0] not in ('image/png', 'image/jpeg', 'image/webp'):
            raise HTTPException(400, 'Only PNG, JPEG and WebP images are accepted')
        body = await request.body()
        if len(body) > 8*1024*1024:
            raise HTTPException(413, 'Image too large')
        try:
            with Image.open(io.BytesIO(body)) as image:
                if image.width*image.height > 20000000 or image.format not in ('PNG', 'JPEG', 'WEBP'):
                    raise ValueError('Unsupported image')
                image.load()
                image.thumbnail((2000, 2000))
                filename = uuid.uuid4().hex + '.webp'
                image.convert('RGB').save(uploads / filename, 'WEBP', quality=88)
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise HTTPException(400, 'Invalid or oversized image')
        with db(True) as conn:
            audit(conn, actor['user_id'], 'image_uploaded', filename)
        return {'path': 'uploads/' + filename}

    @app.get('/api/admin/orders')
    def admin_orders(request: Request, status: str = '', q: str = ''):
        user(request, admin=True)
        with db(True) as conn:
            expire(conn)
            rows = conn.execute('SELECT * FROM orders WHERE (?=\'\' OR status=?) AND (?=\'\' OR id LIKE ? OR json_extract(data,\'$.customer.email\') LIKE ?) ORDER BY created_at DESC LIMIT 200', (status, status, q, '%'+q[:100]+'%', '%'+q[:100]+'%')).fetchall()
            return {'orders': [order_out(conn, row, True) for row in rows]}

    @app.post('/api/admin/orders/{oid}/action')
    def order_action(oid: str, payload: OrderAction, request: Request):
        actor = user(request, admin=True, mutation=True)
        with db(True) as conn:
            expire(conn)
            row = conn.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
            if not row:
                raise HTTPException(404, 'Order not found')
            data, status = json.loads(row['data']), row['status']
            transitions = {'mark_paid': ('pending_payment', 'paid'), 'process': ('paid', 'processing'), 'ship': ('processing', 'shipped'), 'complete': ('shipped', 'completed')}
            if payload.action in transitions:
                expected, target = transitions[payload.action]
                if status != expected:
                    raise HTTPException(409, 'Invalid order status transition')
                if payload.action == 'ship':
                    if not payload.tracking_number or not payload.carrier:
                        raise HTTPException(400, 'Carrier and tracking number are required')
                    data.update(tracking_number=payload.tracking_number, carrier=payload.carrier)
                conn.execute('UPDATE orders SET status=?,payment_status=?,data=?,updated_at=? WHERE id=?', (target, 'paid', json.dumps(data), stamp(), oid))
                event(conn, oid, target, payload.note)
            elif payload.action == 'cancel':
                if status != 'pending_payment':
                    raise HTTPException(409, 'Paid orders require the refund workflow')
                release(conn, row, 'cancelled', payload.note)
            elif payload.action == 'approve_refund':
                if status != 'refund_requested' or row['payment_status'] != 'paid':
                    raise HTTPException(409, 'No eligible refund request')
                conn.execute("UPDATE orders SET payment_status='refunded',status='refunded',updated_at=? WHERE id=?", (stamp(), oid))
                event(conn, oid, 'refunded', 'Offline refund recorded: '+payload.note)
            elif payload.action == 'decline_refund':
                if status != 'refund_requested':
                    raise HTTPException(409, 'No refund request')
                target = data.get('status_before_refund', 'paid')
                conn.execute('UPDATE orders SET status=?,updated_at=? WHERE id=?', (target, stamp(), oid))
                event(conn, oid, target, 'Refund request declined: '+payload.note)
            audit(conn, actor['user_id'], payload.action, oid, payload.note)
        return {'ok': True, 'notice': 'This records an offline action; no payment or refund transfer is executed.'}

    @app.get('/api/admin/customers')
    def customers(request: Request):
        user(request, admin=True)
        with db() as conn:
            return {'customers': [dict(r) for r in conn.execute("SELECT u.id,u.name,u.email,u.active,u.created_at,count(o.id) AS order_count,COALESCE(sum(CASE WHEN o.payment_status='paid' THEN o.total_cents ELSE 0 END),0) AS spend_cents FROM users u LEFT JOIN orders o ON o.user_id=u.id WHERE u.role='customer' GROUP BY u.id ORDER BY u.created_at DESC LIMIT 500")]}

    @app.put('/api/admin/customers/{uid}')
    def customer_state(uid: str, payload: AccountState, request: Request):
        actor = user(request, admin=True, mutation=True)
        with db(True) as conn:
            if not conn.execute("UPDATE users SET active=? WHERE id=? AND role='customer'", (int(payload.active), uid)).rowcount:
                raise HTTPException(404, 'Customer not found')
            if not payload.active:
                conn.execute('DELETE FROM sessions WHERE user_id=?', (uid,))
            audit(conn, actor['user_id'], 'customer_status', uid, str(payload.active))
        return {'ok': True}

    @app.get('/api/admin/coupons')
    def coupons(request: Request):
        user(request, admin=True)
        with db() as conn:
            return {'coupons': [{**json.loads(r['data']), 'uses': r['uses']} for r in conn.execute('SELECT * FROM coupons ORDER BY code')]}

    @app.put('/api/admin/coupons/{code}')
    def save_coupon(code: str, payload: Coupon, request: Request):
        actor = user(request, admin=True, mutation=True)
        if code != payload.code:
            raise HTTPException(400, 'Code does not match')
        with db(True) as conn:
            conn.execute('INSERT INTO coupons(code,data) VALUES(?,?) ON CONFLICT(code) DO UPDATE SET data=excluded.data', (code, json.dumps(payload.model_dump())))
            audit(conn, actor['user_id'], 'coupon_saved', code)
        return {'ok': True}

    @app.get('/api/admin/messages')
    def messages(request: Request):
        user(request, admin=True)
        with db() as conn:
            return {'messages': [{**dict(r), 'data': json.loads(r['data'])} for r in conn.execute('SELECT * FROM messages ORDER BY created_at DESC LIMIT 200')]}

    @app.put('/api/admin/messages/{mid}')
    def message_update(mid: str, payload: Note, request: Request):
        actor = user(request, admin=True, mutation=True)
        with db(True) as conn:
            if not conn.execute('UPDATE messages SET status=?,note=? WHERE id=?', (payload.status, payload.note, mid)).rowcount:
                raise HTTPException(404, 'Message not found')
            audit(conn, actor['user_id'], 'message_updated', mid)
        return {'ok': True, 'notice': 'Internal note saved. No email was sent.'}

    @app.get('/api/admin/reviews')
    def admin_reviews(request: Request):
        user(request, admin=True)
        with db() as conn:
            return {'reviews': [dict(r) for r in conn.execute('SELECT r.*,u.name,p.data AS product_data FROM reviews r JOIN users u ON u.id=r.user_id JOIN products p ON p.id=r.product_id ORDER BY r.created_at DESC LIMIT 200')]}

    @app.put('/api/admin/reviews/{rid}')
    def moderate(rid: str, payload: Moderation, request: Request):
        actor = user(request, admin=True, mutation=True)
        with db(True) as conn:
            if not conn.execute('UPDATE reviews SET status=? WHERE id=?', (payload.status, rid)).rowcount:
                raise HTTPException(404, 'Review not found')
            audit(conn, actor['user_id'], 'review_moderated', rid, payload.status)
        return {'ok': True}

    @app.put('/api/admin/settings')
    def update_settings(payload: Settings, request: Request):
        actor = user(request, admin=True, mutation=True)
        with db(True) as conn:
            conn.execute('UPDATE settings SET data=? WHERE id=1', (json.dumps(payload.model_dump()),))
            audit(conn, actor['user_id'], 'settings_updated', 'store')
        return {'ok': True}

    @app.get('/api/admin/audit')
    def audit_log(request: Request):
        user(request, admin=True)
        with db() as conn:
            return {'events': [dict(r) for r in conn.execute('SELECT a.*,u.name AS actor_name FROM audit a LEFT JOIN users u ON u.id=a.actor ORDER BY a.id DESC LIMIT 200')]}

    @app.get('/{path:path}')
    def website(path: str):
        if path.startswith('api/'):
            raise HTTPException(404, 'API endpoint not found')
        if path in ('admin', 'admin/'):
            return FileResponse(ROOT / 'admin/index.html')
        if path.startswith('admin/'):
            name = path.removeprefix('admin/')
            if name not in ('app.js', 'style.css'):
                raise HTTPException(404)
            return FileResponse(ROOT / 'admin' / name)
        if path.startswith('uploads/'):
            name = path.removeprefix('uploads/')
            if not re.fullmatch(r'[a-f0-9]{32}\.webp', name) or not (uploads / name).is_file():
                raise HTTPException(404)
            return FileResponse(uploads / name)
        if path.startswith('assets/'):
            target = (ROOT / path).resolve()
            if target.parent != (ROOT / 'assets').resolve() or not target.is_file() or target.suffix not in ('.png', '.jpg', '.jpeg', '.webp', '.ttf', '.woff2'):
                raise HTTPException(404)
            return FileResponse(target)
        path = path or 'index.html'
        target = ROOT / path
        allowed_files = {p.name for p in ROOT.iterdir() if p.is_file() and p.suffix in ('.html', '.css', '.js')}
        if path not in allowed_files:
            raise HTTPException(404)
        if target.suffix == '.html':
            return HTMLResponse(target.read_text().replace('<head>', '<head><script>window.KENNY_BACKEND_REQUIRED=true</script>', 1), headers={'Cache-Control': 'no-cache'})
        return FileResponse(target)

    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_app(), host=os.environ.get('KENNY_HOST', '127.0.0.1'), port=int(os.environ.get('PORT', '3000')), proxy_headers=False)
