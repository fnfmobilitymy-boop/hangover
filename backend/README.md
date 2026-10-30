# KENNY commerce backend

For GitHub Actions deployment to a persistent Render service, follow [DEPLOYMENT.md](DEPLOYMENT.md).

FastAPI + SQLite, serving the storefront and a light lavender administration UI from the same origin. The application needs a persistent, writable filesystem and one running instance. GitHub Pages cannot execute it.

## Local startup

Use Python 3.12:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock
python -m backend.server
```

The default port is 3000. Storefront: `/`. Management: `/admin/`. Development OpenAPI: `/api/docs`. To change paths or port, set `KENNY_DATA_DIR` and `PORT`.

At first startup, the application creates `.data/bootstrap-token` with owner-only permissions. Open that file privately on the server and enter its contents on the administrator setup page along with your own email and a new password (at least 12 characters). Never commit or share this token. It is only accepted while no administrator exists. There is no default administrator password. The setup token can alternatively be supplied using the `KENNY_BOOTSTRAP_TOKEN` environment variable through secure hosting settings.

The database and uploads are ignored by Git and excluded from Docker build context. Development seeds contain seven concept products and 12 units per size. In `KENNY_ENV=production`, new databases seed sizes at **zero stock**; verify actual product details and set real stock before opening sales. Existing databases are never reset by startup.

## Features

- Customer registration, password login, logout, password change and persistent HTTP-only sessions. Passwords use salted scrypt; server stores only a hash of each session token. Registering never permits a role choice. Blocked customers lose sessions.
- Administrator bootstrap, protected management endpoints and audit records.
- Product creation/editing/activation, Chinese and Malay fields, image upload/re-encoding, size-specific stock and inventory CSV export. Product IDs stay stable; inactive products stay in historical orders.
- Server-side quotes in integer MYR cents. The server rejects client-supplied totals. Coupon eligibility, thresholds, per-customer limits and expiry are checked on the server.
- Transactional stock reservation, duplicate-line rejection and idempotent order creation. Unpaid orders expire after 30 minutes. A maintenance task sweeps once per minute; order/quote/dashboard reads also sweep. Cancellation restores reserved stock exactly once.
- Owned order history, tracking references, customer cancellation, refund requests, and administrator fulfilment transitions. A customer cannot read another customer's order.
- Member activation/deactivation, persistent wishlists, moderated reviews with verified-purchase status derived from completed paid orders.
- Customer messages with internal notes, newsletter opt-in records, real store locations, shipping rules, social profiles and store settings.
- Dashboard revenue, order states, top sellers and trends come from the database. Empty stores show zeros, not invented analytics.

## Payment and shipping boundary

**No live payment gateway is connected.** Checkout saves an unpaid order and does not request financial credentials. The administrator can record a verified offline payment and progress the order through preparing, shipped and completed states. Marking paid is a record of an external action, not a charge.

Similarly, approving a refund records an offline refund that the merchant must already have executed. It does not transfer money. Returned stock is not automatically restored; inspect returned goods and use an inventory adjustment with a reason. Paid orders use a refund request, not the unpaid cancellation endpoint.

Carrier names and tracking numbers can be entered and shown to the customer. Carrier API tracking, automatic shipping labels, email verification, forgotten-password email, transactional email and social OAuth are not connected. Newsletter records do not send campaigns. Publish verified legal text and business contact information before taking real customer orders.

## Frontend modes

`backend-client.js` detects `/api/health`. When the API is present, `app.js` loads the server catalogue, registration/login uses the server session, checkout requests a server quote and creates a database order, reviews are moderated, and messages/favourites use API storage. HTML served by this backend sets a required-backend flag so an unavailable API cannot silently fall back to local fake checkout.

On a static GitHub Pages deployment, the original labelled local demo remains usable. It is not connected to the private backend. For real service, deploy the frontend and backend together behind the same HTTPS origin; the container already serves both. No database password or administrator credential belongs in frontend files.

## Docker

```sh
docker build -t kenny-commerce .
docker compose up -d --build
```

The supplied Compose configuration binds only `127.0.0.1:3000` and is for local development. It keeps SQLite and uploads in the `kenny-data` named volume. Use your hosting provider's durable volume, not an ephemeral container filesystem.

Production settings:

- `KENNY_ENV=production`
- `KENNY_COOKIE_SECURE=1`
- `KENNY_ALLOWED_ORIGINS=https://your-public-store-domain.example`
- `KENNY_DATA_DIR=/data` with a persistent volume owned by container UID/GID 10001
- `KENNY_HOST=0.0.0.0`, `PORT=3000`

Run behind an HTTPS reverse proxy. The public origin setting is required when the proxy terminates TLS, because forwarded scheme/host headers are deliberately not trusted. Do not publish an insecure HTTP endpoint for customer login. Production startup refuses insecure-cookie settings; API documentation is disabled in production. The Docker process runs as an unprivileged user.

In this managed cloud environment, build with the inherited Docker proxy configuration and the CA bundle as a BuildKit secret:

```sh
docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -t kenny-commerce .
```

The optional CA mount is used only for dependency installation; it is not copied into the image. TLS verification remains enabled.

## Backups

```sh
python scripts/backup-database.py /secure/location/kenny-backup.sqlite3
```

The script uses SQLite's backup API, creates a mode-0600 destination and refuses to overwrite an existing backup. Back up uploads separately. Keep backups outside the public checkout and protect them as customer data. Verify restores on a separate database before replacing a live volume. Do not copy only the main database file while WAL writes are in progress.

## Verification

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Tests exercise CSRF and roles, ownership, concurrency/overselling, server pricing, coupon accounting, idempotency, stock release, expiry, offline payment/fulfilment/refund transitions, moderation, blocked sessions, persistence and static-file boundaries. They use temporary databases and fixture credentials only.

`node scripts/backend-browser-smoke.cjs` uses the cloud's supplied Playwright/Chromium against an **isolated** server at port 3021 and a temporary data directory. It initializes a test administrator, registers a customer, creates an order, records a test offline payment and visits all admin modules. Never point it at a production database. The separate static demo smoke check remains `npm run test:browser`.

Administration includes Chinese/English controls and light/dark appearance in the top toolbar, including on the login page. Preferences are saved in this browser separately from storefront settings. Changing language reloads the interface while keeping the server login session; save edits before switching. Theme changes apply immediately. Main text and form controls use larger type (16–17px or more), with responsive layouts and theme-aware tables, charts, forms and dialogs. Only interface copy is translated; product/customer data and editable values remain unchanged. After running the isolated backend browser fixture, `npm run test:admin-appearance` verifies both languages, all admin modules, appearance persistence and mobile layouts against the same isolated server.
