# Mpesa STK Push Notification API Implementation

## Frameworks Used:

- Django Rest Framework

---

## Configuration and Installation:

### Installation:

```bash
sudo apt install python3-pip
python3 -m pip install django
pip install djangorestframework
pip install markdown  # Markdown support for the browsable API
pip install django-filter
```

### Configuration

Add 'rest_framework' to your INSTALLED_APPS in settings.py:

```json
INSTALLED_APPS = [
    ...
    'rest_framework',
]
```

### APIs Implemented

```json
api/v1/access/token [name='get_mpesa_access_token']
api/v1/online/lipa [name='lipa_na_mpesa']
api/v1/c2b/register [name='register_mpesa_validation']
api/v1/c2b/confirmation[name='confirmation']
api/v1/c2b/validation [name='validation']
api/v1/stk/callback [name='stk_callback']
api/v1/stk/error [name='stk_error']
api/v1/transactions/all [name='get_all_transactions']
api/v1/transactions/completed [name='get_completed_transactions']
```

Usage:

1. Make Migrations:

```
python manage.py makemigrations
python manage.py migrate
```

2. Create Super User:

```
python manage.py createsuperuser
```

3. Run Server:

```
python manage.py runserver
```

4. Example API Call:

```
http://127.0.0.1:8000/api/v1/online/lipa
```

This will send a push notification to the registered phone number.

Author:
[Emmanuel Chalo](https://www.linkedin.com/in/emmanuel-chalo-211336183)
