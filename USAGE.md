# Mobile Money – Usage

This file contains copy/paste commands for common tasks when running this project locally.

## Dashboard (admin/staff session)

The React dashboard uses **Django session auth** (staff-only).

1. Start Django:

```bash
source .venv/bin/activate
make migrations
make run
```

2. Create a staff user (superuser):

```bash
source .venv/bin/activate
make superuser
```

3. Start the dashboard:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and log in with your Django admin username/password.

If you cannot run `createsuperuser` (e.g. production bootstrap), use the guarded UI bootstrap flow described in `README.md`.

If you see CSRF errors, add this to `.env`:

```dotenv
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

## API gateway auth (OAuth2)

Third-party access is OAuth2-only.

To call protected endpoints from curl/Postman, you need:

- `client_id`
- `client_secret`
- requested scopes (space-separated)

You can create OAuth clients using the Maintainer page in the dashboard (superuser-only).

### Get an OAuth2 access token (client_credentials)

Request an access token:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/oauth/token/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=<CLIENT_ID>" \
  -d "client_secret=<CLIENT_SECRET>" \
  -d "scope=transactions:read c2b:write qr:write ratiba:write b2c:write b2b:write"
```

Use the returned token for API calls:

```bash
export ACCESS_TOKEN='<paste access_token here>'
```

Scope mapping (high level):

- STK push: `c2b:write`
- Transactions: `transactions:read`
- QR generate: `qr:write`
- Ratiba create: `ratiba:write`
- B2C bulk create: `b2c:write`
- B2B bulk create: `b2b:write`

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

This endpoint is **staff-only** (session auth). The easiest way is to log into the dashboard and use the UI.

If you want to do it with curl, do a session login first (CSRF + cookie jar), then call the register endpoint:

```bash
csrf=$(curl -s -c cookies.txt http://127.0.0.1:8000/api/v1/auth/csrf | python -c 'import sys,json; print(json.load(sys.stdin)["csrfToken"])')

curl -s -b cookies.txt -c cookies.txt \
  -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $csrf" \
  -H "Referer: http://127.0.0.1:8000" \
  -d '{"username":"<STAFF_USERNAME>","password":"<STAFF_PASSWORD>"}'
```

```bash
curl -X POST http://127.0.0.1:8000/api/v1/c2b/register \
  -b cookies.txt -c cookies.txt
```

Notes:

- Sandbox C2B registration typically uses `C2B_SHORTCODE=600000`.
- If you get a "Duplicate notification info" message, Safaricom already has URLs registered for that shortcode. The endpoint is treated as idempotent.

## 5) Initiate an STK Push

Minimal request:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/c2b/stk/push \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": 1, "phone_number": "2547XXXXXXXX"}'
```

If you see `Bad Request - Invalid PartyA`, set `PARTY_A` in `.env` or pass it explicitly:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/c2b/stk/push \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": 1, "phone_number": "2547XXXXXXXX", "party_a": "2547XXXXXXXX"}'
```

Recommended `.env` defaults for STK:

```dotenv
PARTY_A=2547XXXXXXXX
PHONE_NUMBER=2547XXXXXXXX
ACCOUNT_REFERENCE=TEST-001
```

Multi-tenant usage notes:

- You can optionally pass a `shortcode` in the request body to use a stored per-business shortcode/passkey and default callback URL.
- You can also override the callback URL per request via `callback_url`.

Example with per-business shortcode:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/c2b/stk/push \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": 1, "phone_number": "2547XXXXXXXX", "shortcode": "174379", "account_reference": "ORDER-123", "callback_url": "https://<your-public-host>/api/v1/c2b/stk/callback"}'
```

## 6) List transactions

All transactions:

```bash
curl -X GET http://127.0.0.1:8000/api/v1/transactions/all \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Completed transactions:

```bash
curl -X GET http://127.0.0.1:8000/api/v1/transactions/completed \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Filter by business:

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/transactions/all?business_id=<BUSINESS_UUID>" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

## 6b) Generate a QR Code

```bash
curl -X POST http://127.0.0.1:8000/api/v1/qr/generate \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"MerchantName":"My Shop","RefNo":"INV-001","Amount":1,"TrxCode":"BG"}'
```

## 6c) Create a Ratiba Standing Order

Notes:

- `CallBackURL` must be a **publicly reachable URL** that Safaricom can POST to.
- Use the built-in callback endpoint: `POST /api/v1/ratiba/callback`.
- Correlation: this app matches callbacks to orders primarily via `AccountReference`, so make it unique per standing order.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ratiba/create \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "StandingOrderName":"Test Standing Order",
    "StartDate":"20240905",
    "EndDate":"20250905",
    "BusinessShortCode":"174379",
    "TransactionType":"Standing Order Customer Pay Bill",
    "ReceiverPartyIdentifierType":"4",
    "Amount":"4500",
    "PartyA":"254708374149",
    "CallBackURL":"https://<your-public-host>/api/v1/ratiba/callback",
    "AccountReference":"Test-001",
    "TransactionDesc":"Test",
    "Frequency":"2"
  }'
```

## 6d) Create B2C/B2B bulk batches

Notes:

- `business_id` is required for both B2C and B2B bulk create.
- Create a Business in the dashboard onboarding UI (or Django admin) and use its UUID as `business_id`.

B2C:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/b2c/bulk \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"business_id":"<BUSINESS_UUID>","reference":"BATCH-001","items":[{"recipient":"254700000000","amount":"1"}]}'
```

B2B:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/b2b/bulk \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"business_id":"<BUSINESS_UUID>","reference":"B2B-001","items":[{"recipient":"ACCT-001","amount":"1"}]}'
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

Ratiba callback:

```bash
curl -i -X POST https://<ngrok-host>/api/v1/ratiba/callback \
  -H "Content-Type: application/json" \
  -d '{"AccountReference":"Test-001","ResultCode":0,"ResultDesc":"Accepted"}'

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
