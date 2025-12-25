# Mpesa STK Push API (Django)

This project is a Django + Django REST Framework API that demonstrates M-Pesa integration for:

- STK Push initiation (Lipa Na M-Pesa Online)
- Receiving STK callbacks and errors
- Registering C2B Confirmation/Validation URLs
- Receiving C2B Confirmation/Validation callbacks
- Viewing stored transactions

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

## Configuration (.env)

All configuration is read from `.env` (loaded via `python-dotenv`). Use `.env.example` as a template.

Key variables:

- `CONSUMER_KEY`, `CONSUMER_SECRET`, `TOKEN_URL`
- `LIPA_NA_MPESA_ONLINE_URL` (STK push endpoint)
- `REGISTER_URL` (C2B register URL endpoint)
- `BUSINESS_SHORTCODE` and `LIPA_NA_MPESA_PASSKEY` (STK password generation)
- `C2B_SHORTCODE` (for C2B URL registration; sandbox commonly uses `600000`)
- `STK_CALLBACK_URL`, `CONFIRMATION_URL`, `VALIDATION_URL`

## Security

### Internal API Key

The following endpoints are protected and require an API key header:

- `GET /api/v1/access/token`
- `POST /api/v1/online/lipa`
- `POST /api/v1/c2b/register`
- `GET /api/v1/transactions/all`
- `GET /api/v1/transactions/completed`

Send the key using either:

- `X-API-Key: <your key>` (recommended)
- or `Authorization: Bearer <your key>`

Callback endpoints are intentionally **not** protected by this key (Safaricom must call them).

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

2. Start ngrok:

```bash
python ngrok.py
```

3. Update `.env` to use the ngrok domain:

- `STK_CALLBACK_URL=https://<ngrok-host>/api/v1/stk/callback`
- `CONFIRMATION_URL=https://<ngrok-host>/api/v1/c2b/confirmation`
- `VALIDATION_URL=https://<ngrok-host>/api/v1/c2b/validation`
- Add the host to `DJANGO_ALLOWED_HOSTS` (host only, no scheme), e.g. `abcd.ngrok-free.app`

After updating `.env`, restart Django.

## Endpoints

```text
GET  /api/v1/access/token
POST /api/v1/online/lipa
POST /api/v1/c2b/register
POST /api/v1/c2b/confirmation
POST /api/v1/c2b/validation
POST /api/v1/stk/callback
POST /api/v1/stk/error
GET  /api/v1/transactions/all
GET  /api/v1/transactions/completed
```

## Usage Guide

See `USAGE.md` for:

- Generating an API key
- Sample curl requests
- ngrok workflow tips and troubleshooting

## Tests

Run the test suite:

```bash
python manage.py test
```

## Author

Emmanuel Chalo  
[LinkedIn](https://www.linkedin.com/in/emmanuel-chalo-211336183)  
[email](mailto:emusyoka759@gmail.com)
