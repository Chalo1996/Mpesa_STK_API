# Mpesa STK Push Notification API implementation
---
---
### Frameworks used: Django Rest_Framework
---

### Configuration and Installation:
- Installation:
---
```
sudo apt install python3-pip
python3 -m pip install django
pip install djangorestframework
pip install markdown # Markdown support for the browsable API.
pip install django-filter
```
- Configuration:
```
Add 'rest_framework' to your INSTALLED_APPS setting:
```
```
INSTALLED_APPS = [
    ...
    'rest_framework',
]
```

### APIs implemented:
```
api/v1/ access/token [name='get_mpesa_access_token']
api/v1/ online/lipa [name='lipa_na_mpesa']
api/v1/ c2b/register [name='register_mpesa_validation']
api/v1/ c2b/confirmation [name='confirmation']
api/v1/ c2b/validation [name='validation']
api/v1/ c2b/callback [name='call_back'] 
```

### Usage:
- Make migrations:
- ```
  make migrations
- Create Super User:
- ```
  make superuser
- Run Server:
- ```
  make server
- Example:
- ```
  http://127.0.0.1:8000/api/v1/online/lipa
*Will send a push notification to theregistered number.*

## Author:
__Emmanuel Chalo [linkedin](https://www.linkedin.com/in/emmanuel-chalo-211336183 "LinkedIn")__ 
