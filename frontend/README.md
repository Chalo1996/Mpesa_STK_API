# Mpesa Dashboard (React)

This is a small React dashboard used to operate and inspect the Django backend in this repo.

## Auth

The dashboard uses **Django session auth** (staff-only). You must create a Django admin/superuser and log in from the dashboard.

## Run (dev)

1. Start the Django backend (port 8000):

```bash
make run
```

2. Create a Django admin user:

```bash
make superuser
```

3. Start the dashboard (port 5173):

```bash
npm install
npm run dev
```

Open `http://localhost:5173` and log in.

## CSRF

If login fails with CSRF errors, set this in the backend `.env`:

```dotenv
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

## API proxy

Vite proxies `/api/*` to `http://127.0.0.1:8000` for local development.
