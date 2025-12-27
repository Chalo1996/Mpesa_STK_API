# Mobile Money Dashboard (React)

This is a small React dashboard used to operate and inspect the Django backend in this repo.

## Run (dev)

1. Start the Django backend (port 8000):

```bash
make run
```

2. Create a Django admin user:

```bash
make superuser
```

If you need a UI-friendly way to create the _first_ superuser (e.g. production bootstrap), the dashboard includes a hidden route:

- `/bootstrap/superuser`

This requires the backend env var `BOOTSTRAP_SUPERUSER_TOKEN` and will only work if no superuser exists.

3. Start the dashboard (port 5173):

```bash
npm install
npm run dev
```

Open `http://localhost:5173`.

## Authentication modes

The frontend supports two distinct auth modes:

1. **Developer portal (OAuth2 Bearer token)**

- Used for third-party/gateway calls (create actions like STK Push, QR generate, Ratiba create, B2B/B2C bulk).
- The app sends `Authorization: Bearer <token>` when a token is available.

2. **Staff session (Django login + CSRF)**

- Used for staff-only pages/endpoints (history/list/detail, maintainer client management).
- This relies on browser cookies and CSRF tokens.

## Developer portal: store an access token

You can provide a token in either of these ways:

- **UI**: open the Access Token page and paste/save an access token.
- **Env**: set `VITE_OAUTH_ACCESS_TOKEN`.

The UI stores the token under localStorage key `oauth_access_token`.

## Developer portal: get a token from the UI

The Access Token page includes a small form to request a token from the backend token endpoint:

- `POST /api/v1/oauth/token/` (grant type `client_credentials`)
- Inputs: `client_id`, `client_secret`, `scope`

Notes:

- `client_secret` is treated as sensitive: it is not persisted and is cleared from the form after a successful token fetch.
- Scopes are space-separated (example: `transactions:read c2b:write qr:write`).

## Backend URL / proxy

Vite proxies `/api/*` to `http://127.0.0.1:8000` for local development.

If you run the backend on a different origin (host/port), configure your Vite dev server proxy or update the API base URL in the frontend config so calls reach the Django server.

## CSRF

If login fails with CSRF errors, set this in the backend `.env`:

```dotenv
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```
