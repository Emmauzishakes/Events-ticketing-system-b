# Event-Ticketing-System Backend API

A high-performance Django REST API powering the Event-Ticketing-System virtual platform. This backend handles automated Safaricom M-Pesa payments via the Daraja API, secure digital access pass generation, and live stream validation for Next.js frontend clients.

## Tech Stack
* **Language:** Python 3.10+
* **Framework:** Django 5.x, Django REST Framework (DRF)
* **Database:** SQLite (Development)
* **Integrations:** Safaricom Daraja API (M-Pesa Express / STK Push)
* **Security:** CORS Headers enabled for dedicated Next.js client access

---

## Core Features

1. **Automated M-Pesa Checkout:** Initiates STK push prompts directly to user devices.
2. **Asynchronous Callbacks:** Securely receives and processes Safaricom webhook responses to verify transaction success.
3. **Digital Pass Generation:** Automatically issues unique, cryptographically secure UUID tokens upon successful payment.
4. **Access Validation:** Validates ticket UUIDs against active events and serves hidden live stream URLs (e.g., Google Meet, YouTube Live) to authenticated users.

---

## Project Structure

The repository follows a clean, modular Django architecture separated into the global configuration and the primary `core` application.

```text
ticketing_system/
│
├── core/                       # Primary application module
│   ├── migrations/             # Database schema history
│   ├── admin.py                # Custom admin dashboard configurations
│   ├── models.py               # Data models (Event, Ticket, Payment)
│   ├── serializers.py          # DRF JSON transformers
│   ├── urls.py                 # Core API routing
│   └── views.py                # M-Pesa logic and endpoint controllers
│
├── ticketing_system/           # Global project configuration
│   ├── settings.py             # App settings, CORS, and Database config
│   ├── urls.py                 # Global routing
│   └── wsgi.py / asgi.py       # Web server gateways
│
├── .env                        # Environment variables (Ignored in Git)
├── .gitignore                  # Excluded files and directories
├── manage.py                   # Django CLI utility
└── requirements.txt            # Python dependency manifest