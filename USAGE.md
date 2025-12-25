# Usage

This file contains copy/paste commands for common tasks when running this project locally.

## 1) Create an API key

The API uses an internal API key to protect non-callback endpoints.

Generate a strong key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set it in your `.env`:

```dotenv
INTERNAL_API_KEY=<paste-generated-key>
```

Send it with requests:

- `X-API-Key: <your key>` (recommended)
- or `Authorization: Bearer <your key>`

## 2) Start the app

```bash
source .venv/bin/activate
make migrations
make run
```

Manual equivalent:

```bash
python manage.py migrate
python manage.py runserver 8000
```

## 2b) Create a superuser (admin)

```bash
source .venv/bin/activate
make superuser
```

Manual equivalent:

```bash
python manage.py createsuperuser
```

## 3) Use ngrok for public callbacks

Safaricom must be able to reach your callback endpoints over HTTPS.

Start ngrok:

```bash
source .venv/bin/activate
python ngrok.py
```

Copy the public URL printed by ngrok, e.g.:

- `https://abcd-1234.ngrok-free.app`

Update your `.env` (host only in `DJANGO_ALLOWED_HOSTS`, no `https://`):

```dotenv
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,abcd-1234.ngrok-free.app
DJANGO_CSRF_TRUSTED_ORIGINS=https://abcd-1234.ngrok-free.app

STK_CALLBACK_URL=https://abcd-1234.ngrok-free.app/api/v1/stk/callback
CONFIRMATION_URL=https://abcd-1234.ngrok-free.app/api/v1/c2b/confirmation
VALIDATION_URL=https://abcd-1234.ngrok-free.app/api/v1/c2b/validation
```

Restart Django after editing `.env`.

## 4) Register C2B URLs (Sandbox)

This calls _your local API_, which then calls Safaricom’s C2B register endpoint.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/c2b/register \
  -H "X-API-Key: <your INTERNAL_API_KEY>"
```

Notes:

- Sandbox C2B registration typically uses `C2B_SHORTCODE=600000`.
- If you get a "Duplicate notification info" message, Safaricom already has URLs registered for that shortcode. The endpoint is treated as idempotent.

## 5) Initiate an STK Push

Minimal request:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/online/lipa \
  -H "X-API-Key: <your INTERNAL_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"amount": 1, "phone_number": "2547XXXXXXXX"}'
```

If you see `Bad Request - Invalid PartyA`, set `PARTY_A` in `.env` or pass it explicitly:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/online/lipa \
  -H "X-API-Key: <your INTERNAL_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"amount": 1, "phone_number": "2547XXXXXXXX", "party_a": "2547XXXXXXXX"}'
```

Recommended `.env` defaults for STK:

```dotenv
PARTY_A=2547XXXXXXXX
PHONE_NUMBER=2547XXXXXXXX
ACCOUNT_REFERENCE=TEST-001
```

## 6) List transactions

All transactions:

```bash
curl -X GET http://127.0.0.1:8000/api/v1/transactions/all \
  -H "X-API-Key: <your INTERNAL_API_KEY>"
```

Completed transactions:

```bash
curl -X GET http://127.0.0.1:8000/api/v1/transactions/completed \
  -H "X-API-Key: <your INTERNAL_API_KEY>"
```

## 7) Quick callback sanity checks (via ngrok)

If ngrok is running and `.env` points to your ngrok domain, you can manually POST to your callback endpoints:

Validation:

```bash
curl -i -X POST https://<ngrok-host>/api/v1/c2b/validation \
  -H "Content-Type: application/json" \
  -d '{}'
```

Confirmation:

```bash
curl -i -X POST https://<ngrok-host>/api/v1/c2b/confirmation \
  -H "Content-Type: application/json" \
  -d '{"TransID":"T1","TransAmount":1,"MSISDN":"254700000000","TransTime":"20251225120000"}'
```

## 8) Run tests

```bash
source .venv/bin/activate
python manage.py test
```

## Troubleshooting

### curl: SSL wrong version number

Use `http://127.0.0.1:8000/...` when calling your local Django server (it’s HTTP by default). Use `https://...` only for ngrok URLs.

### DisallowedHost / Invalid HTTP_HOST header

Make sure `DJANGO_ALLOWED_HOSTS` contains the ngrok host _without_ `https://`, e.g.:

- `DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,abcd-1234.ngrok-free.app`
