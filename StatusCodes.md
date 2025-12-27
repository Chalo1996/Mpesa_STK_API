# Status Codes

This file documents the internal gateway status codes exposed by this service. Internal codes start from 0 and map to external systems (e.g., Safaricom/Daraja).

Last generated: 2025-12-27 16:17:24Z

Notes:

- `status_code` / `status_message` are returned to integrators.
- `status_message` typically comes from the stored `default_message` below (or the upstream message when no default is stored).

| internal_code | external_system | external_code | status_message | is_success |
| ---: | --- | --- | --- | :---: |
| 0 | safaricom | 0 | Success | yes |
| 1 | safaricom | 400.002.05 | Invalid Request Payload | no |
| 2 | safaricom | 400.003.01 | Invalid Access Token | no |
| 3 | safaricom | 400.003.02 | Bad Request | no |
| 4 | safaricom | 404.001.04 | Invalid Authentication Header | no |
| 5 | safaricom | 404.003.01 | Resource not found | no |
| 6 | safaricom | 500.003.02 | Error Occurred: Spike Arrest Violation | no |
| 7 | safaricom | 500.003.03 | Error Occurred: Quota Violation | no |
| 8 | safaricom | 500.003.1001 | _(varies; from upstream)_ | no |
| 9 | safaricom | 1001 | Unable to lock subscriber, a transaction is already in process for the current subscriber. | no |
| 10 | safaricom | 1025 | An error occurred while sending push request due to system error on the partner platform. | no |
| 11 | safaricom | 1032 | The request was canceled by the user. | no |
| 12 | safaricom | 1037 | Timeout | no |
| 13 | safaricom | 1050 | The User already has a standing order with the same name on their profile. | no |
| 14 | safaricom | 1051 | Bad request | no |
| 15 | safaricom | 2001 | The initiator information is invalid. | no |
| 16 | safaricom | 4102 | Merchant KYC Fail | no |
| 17 | safaricom | 4104 | Missing Nominated Number | no |
| 18 | safaricom | 4201 | USSD Network Error | no |
| 19 | safaricom | 4203 | USSD Exception Error | no |
