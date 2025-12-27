# Mobile Money (Django)

This project is a Django + Django REST Framework API that demonstrates Mobile Money integration (Safaricom M-Pesa) for:

- STK Push initiation (Lipa Na M-Pesa Online)
- Receiving STK callbacks and errors
- Registering C2B Confirmation/Validation URLs
- Receiving C2B Confirmation/Validation callbacks
- Viewing stored transactions

The codebase is organized in a service-oriented way:

- **C2B** (STK Push + C2B callbacks) — existing service
- **B2C** (bulk payouts) — available (bulk create)
- **B2B** (bulk business payments) — available (bulk create)
- **QR** (Daraja QR generation) — available
- **Ratiba** (standing orders) — available
- **Maintainer** (OAuth client management) — available

The API is designed for local development and sandbox testing. It supports using **ngrok** so Safaricom can reach your local callback endpoints.

## Tech Stack

- Django
- Django REST Framework
- PostgreSQL (optional) or SQLite (default for tests / dev fallback)

## Quick Start (Local)

If you are using Linux/macOS, you can use the Makefile targets:

```bash
cat Makefile
```

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create your environment file:

```bash
cp .env.example .env
```

Then update `.env` with your real credentials and URLs.

Run migrations and start the server:

```bash
make migrations
make run
```

Manual equivalent:

```bash
python manage.py migrate
python manage.py runserver 8000
```

## Bootstrap Superuser (UI-Friendly)

In production you typically need a way to create the _first_ admin account.

This repo supports a guarded bootstrap endpoint + SPA page:

- Set `BOOTSTRAP_SUPERUSER_TOKEN` in the server environment.
- Open the dashboard route `/bootstrap/superuser` and submit:
  - the same bootstrap token
  - username + password (+ optional email)

Security notes:

- The endpoint only works when **no superuser exists**.
- If `BOOTSTRAP_SUPERUSER_TOKEN` is not set, the endpoint is disabled.

## Configuration (.env)

All configuration is read from `.env` (loaded via `python-dotenv`). Use `.env.example` as a template.

Key variables:

- `CONSUMER_KEY`, `CONSUMER_SECRET`, `TOKEN_URL`
- `LIPA_NA_MPESA_ONLINE_URL` (STK push endpoint)
- `REGISTER_URL` (C2B register URL endpoint)
- `BUSINESS_SHORTCODE` and `LIPA_NA_MPESA_PASSKEY` (STK password generation)
- `C2B_SHORTCODE` (for C2B URL registration; sandbox commonly uses `600000`)
- `STK_CALLBACK_URL`, `CONFIRMATION_URL`, `VALIDATION_URL`
- `MPESA_QR_CODE_URL` (M-Pesa QR code generation endpoint)
- `MPESA_RATIBA_URL` (M-Pesa Ratiba standing order endpoint)

Note on credentials provisioning:

- This project can **store and use** per-business Daraja credentials/shortcodes, but it cannot create Safaricom consumer keys/secrets/passkeys for you.
- Merchants must create/obtain credentials in the Safaricom Daraja portal, then configure them in the maintainer onboarding UI.
- Safaricom Daraja portal: <https://developer.safaricom.co.ke/>

## Security

### OAuth2 (Third-Party Gateway)

Third-party developers should use **OAuth2 client_credentials** and call protected endpoints with:

- `Authorization: Bearer <access_token>`

Token endpoint:

- `POST /api/v1/oauth/token/`

Scopes (space-separated):

- `transactions:read`
- `c2b:write`
- `qr:write`
- `ratiba:write`
- `b2c:write`
- `b2b:write`

Protected “gateway” endpoints require an OAuth2 token with the appropriate scope.

### Staff Session (Dashboard)

The React dashboard can also operate many endpoints via **Django staff session auth**.

Staff-only endpoints include:

- `GET /api/v1/access/token` (Safaricom token helper)
- `POST /api/v1/c2b/register` (register callback URLs)
- `GET /api/v1/qr/history` and `GET /api/v1/qr/<id>`
- `GET /api/v1/ratiba/history` and `GET /api/v1/ratiba/<id>`
- `GET /api/v1/b2b/bulk` and `GET /api/v1/b2b/bulk/<batch_id>`
- `GET /api/v1/b2c/bulk` and `GET /api/v1/b2c/bulk/<batch_id>`

Callback endpoints are intentionally **not** authenticated (Safaricom must call them).

### Rate Limiting

Protected endpoints are rate-limited per IP (see `INTERNAL_RATE_LIMIT_*` in `.env.example`).

## Ngrok (Local Callback Testing)

Safaricom needs a public HTTPS URL to reach your callbacks. This repo includes `ngrok.py` to tunnel your local Django server.

1. Start Django:

```bash
make run
```

Manual equivalent:

```bash
python manage.py runserver 8000
```

1. Start ngrok:

```bash
python ngrok.py
```

1. Update `.env` to use the ngrok domain:

- `STK_CALLBACK_URL=https://<ngrok-host>/api/v1/stk/callback`
- `CONFIRMATION_URL=https://<ngrok-host>/api/v1/c2b/confirmation`
- `VALIDATION_URL=https://<ngrok-host>/api/v1/c2b/validation`
- Add the host to `DJANGO_ALLOWED_HOSTS` (host only, no scheme), e.g. `abcd.ngrok-free.app`

After updating `.env`, restart Django.

## Endpoints

```text
GET  /api/v1/auth/csrf
GET  /api/v1/auth/me
POST /api/v1/auth/login
POST /api/v1/auth/logout

POST /api/v1/bootstrap/superuser        # guarded; first-superuser bootstrap only

GET  /api/v1/access/token               # staff-only (session)
POST /api/v1/online/lipa                # legacy alias of /api/v1/c2b/stk/push
POST /api/v1/c2b/register               # staff-only (session)
POST /api/v1/c2b/confirmation
POST /api/v1/c2b/validation
POST /api/v1/stk/callback
POST /api/v1/stk/error
GET  /api/v1/transactions/all
GET  /api/v1/transactions/completed

# OAuth2 (third-party gateway)
POST /api/v1/oauth/token/

GET  /api/v1/admin/logs/calls
GET  /api/v1/admin/logs/callbacks
GET  /api/v1/admin/logs/stk-errors

# Service-style prefixes (aliases / new services)
POST /api/v1/c2b/stk/push               # recommended STK push endpoint
POST /api/v1/c2b/stk/callback
POST /api/v1/c2b/stk/error
POST /api/v1/c2b/register
POST /api/v1/c2b/confirmation
POST /api/v1/c2b/validation
GET  /api/v1/c2b/transactions/all
GET  /api/v1/c2b/transactions/completed

POST /api/v1/b2c/bulk
GET  /api/v1/b2c/bulk
GET  /api/v1/b2c/bulk/<batch_id>

POST /api/v1/b2b/bulk
GET  /api/v1/b2b/bulk
GET  /api/v1/b2b/bulk/<batch_id>

POST /api/v1/qr/generate
GET  /api/v1/qr/history
GET  /api/v1/qr/<qr_id>

POST /api/v1/ratiba/create
POST /api/v1/ratiba/callback
GET  /api/v1/ratiba/history
GET  /api/v1/ratiba/<order_id>

# Maintainer (superuser)
GET  /api/v1/maintainer/clients
POST /api/v1/maintainer/clients
POST /api/v1/maintainer/clients/<client_id>/rotate-secret
POST /api/v1/maintainer/clients/<client_id>/revoke
```

## Usage Guide

See `USAGE.md` for:

- Getting an OAuth2 access token (client_credentials) and scopes
- Sample curl requests
- ngrok workflow tips and troubleshooting

## Tests

Run the test suite:

```bash
python manage.py test
```

## Dashboard (React)

This repo includes a small React dashboard in `frontend/` for calling the existing API endpoints.

The dashboard uses **Django session auth** (staff-only) rather than a shared API key.

1. Start Django (port 8000):

```bash
make run
```

1. Create a Django admin user (staff):

```bash
make superuser
```

1. Start the dashboard (port 5173):

```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:5173` and log in using the Django admin username/password.

If you get CSRF errors during login, ensure your `.env` includes:

```dotenv
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

## Author

Emmanuel Chalo  
[LinkedIn](https://www.linkedin.com/in/emmanuel-chalo-211336183)  
[email](mailto:emusyoka759@gmail.com)
