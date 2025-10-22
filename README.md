# Airline Customer Service Bot

A demo, stateful airline customer-service chatbot built with FastAPI (backend), a simple NLU (SentenceTransformers + rules), a workflow engine, and a Streamlit frontend. The system uses a local SQLite database (`airline_bot.db`) and a mock airline API to simulate bookings, cancellations, changes, seat upgrades, and policy lookups.

This repository is intended as a developer demo / prototype — it is not production-ready. It shows how to combine NLU, workflow state, recommendations, and a UI for conversational customer service flows.

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick start (local development)](#quick-start-local-development)
- [Demo](#demo)
- [API Endpoints](#api-endpoints)
- [Example conversation flows](#example-conversation-flows)
- [Database](#database)
- [Troubleshooting & notes](#troubleshooting--notes)
- [Recommended improvements](#recommended-improvements)
- [License](#license)

---

## Features

- Stateful multi-turn workflows:
  - Book a flight (collects origin, destination, date, passenger name)
  - Check booking status
  - Cancel bookings (with confirmation & policy text)
  - Change flight date (with validation & change fee)
  - Seat upgrade flow (shows available seats, applies upgrade)
- NLU module:
  - SentenceTransformer embeddings + cosine similarity for intent classification
  - Rule-based overrides and lightweight entity extraction (booking IDs, flight numbers, dates, origin/destination)
- Recommendations engine:
  - Policy lookups and upsell suggestions (seat upgrades, add-on services)
- Simple Streamlit chat UI with quick actions, booking list, and analytics
- SQLite persistence for bookings, messages, workflows, feedback, policies, and recommendations

---

## Architecture

- `app.py` — Streamlit frontend (chat UI, bookings view, analytics, feedback)
- `main.py` — FastAPI backend (REST API, startup sequence, message endpoint)
- `nlu.py` — NLU module (SentenceTransformers model + rules)
- `workflow.py` — Workflow engine (manages multi-turn conversation states, validation, handlers)
- `airline_api.py` — Mock airline backend (CRUD against SQLite, in-memory seat availability)
- `recommendations.py` — Recommendation engine (policy & add-ons)
- `database.py` — Initializes `airline_bot.db` and seeds sample data
- `cache.py` — In-memory TTL cache used by the workflow engine
- `setup.bat` / `restart_windows.bat` — Windows helper scripts (developer convenience)


---

## Prerequisites

- Python 3.9+ recommended
- Git (to clone the repo)
- For CPU-based SentenceTransformers you will likely need `torch` installed. On some systems you can use a CPU-only wheel to avoid GPU dependencies.

---

## Quick start (local development)

1. Clone the repository:
   ```bash
   git clone https://github.com/naveenadevi/Airline-bot.git
   cd Airline-bot
   ```

2. Create and activate a virtual environment:
   - macOS / Linux:
     ```bash
     python -m venv venv
     source venv/bin/activate
     ```
   - Windows (PowerShell):
     ```powershell
     python -m venv venv
     venv\Scripts\Activate.ps1
     ```
   - Windows (cmd):
     ```cmd
     python -m venv venv
     call venv\Scripts\activate
     ```

3. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```

5. Initialize the database (creates `airline_bot.db` and seeds sample data):
   ```bash
   python database.py
   ```
   You should see "Database initialized at ..." printed.

6. Start the backend server:
   - Using uvicorn:
     ```bash
     uvicorn main:app --reload --host 0.0.0.0 --port 8000
     ```
  
7. Start the Streamlit frontend (in a new terminal, with the venv activated):
   ```bash
    python -m venv venv
    venv\Scripts\activate
   pip install -r requirements.txt
   streamlit run app.py

   ```
   - The app will open in your browser at the default Streamlit address (usually `http://localhost:8501`).

8. Interact:
   - Use the chat interface to try sample commands:
    - USER: I want to file a complaint
    - USER: My bag is damaged
    - USER: My bag is missing
    - USER: Any discounts available?
    - USER: How much is a ticket?
    - USER: Flight schedule information
    - USER: Travel insurance options
    - USER: Can I fly if I'm sick?
    - USER: What items are prohibited?
    - USER: Can I bring my guitar?
    - USER: Check my booking BK001


---
## Demo
https://github.com/naveenadevi/Airline-bot/releases
---

## API Endpoints

While the frontend communicates with the backend, you can also interact directly:

- Health:
  - GET `/` — returns basic service status

- Chat:
  - POST `/api/message`
    - Payload:
      ```json
      {
        "user_id": "user123",
        "session_id": "your-session-id",
        "message": "I want to cancel my booking BK001"
      }
      ```
    - Response includes: `response`, `intent`, `confidence`, `recommendations`, `timestamp`

- Feedback:
  - POST `/api/feedback`
    - Payload:
      ```json
      {
        "user_id": "user123",
        "session_id": "session-id",
        "message_id": 1,
        "rating": 5,
        "comment": "Great help!"
      }
      ```

- Bookings:
  - GET `/api/bookings/{user_id}` — returns bookings for the user

- Analytics:
  - GET `/api/analytics` — aggregated metrics (total messages, sessions, intent distribution, avg confidence, feedback stats)

- FastAPI auto-generated docs:
  - Visit `http://localhost:8000/docs` for the OpenAPI/Swagger UI

---

## Example conversation flows

- Check a booking:
  - User: "Check booking BK001"
  - Backend NLU -> intent `check_status`, entities `{ booking_id: BK001 }`
  - Workflow -> fetch booking from DB and return booking details + recommendations

- Cancel a booking (multi-turn):
  - User: "I want to cancel my flight"
  - Workflow asks: "Which booking would you like to cancel?"
  - User: "Cancel BK002"
  - Workflow: shows cancellation policy and asks to confirm
  - User: "Yes"
  - Workflow: calls mock airline API to cancel, updates DB, returns confirmation and refund amount

- Book a flight (multi-turn):
  - User: "I want to book a flight"
  - Workflow asks for origin, destination, date, passenger name
  - User provides details (all at once or in steps)
  - NLU extracts entities, workflow validates, and creates a booking via mock airline API

---

## Database

- File: `airline_bot.db` (SQLite)
- Created and seeded by `database.py`
- Main tables:
  - `users`, `bookings`, `messages`, `workflow_states`, `feedback`, `recommendations`, `policies`, `cache`

Notes:
- Dates are stored as TEXT (ISO format `YYYY-MM-DD` expected).
- Foreign key enforcement is not explicitly set; if needed, enable PRAGMA foreign_keys in connections.

---

## Troubleshooting & notes

- Torch/CUDA: If you do not have CUDA, install a CPU-only wheel for `torch` to avoid GPU-related issues.
- SQLite concurrency: SQLite works well for development but can lock under heavy concurrent writes. For production, use PostgreSQL or another client-server DB.
- Windows scripts: `setup.bat` and `restart_windows.bat` are convenience scripts for Windows. `restart_windows.bat` uses `taskkill /F /IM python.exe` which will terminate all Python processes — be careful.
- Hard-coded validations: `workflow.validate_date` has a minimum year check (2025) — update to use dynamic rules if you plan to reuse code later.
- Security: This demo does not implement authentication or rate limiting — do not expose the service publicly without proper security.

---

## Recommended improvements (next steps)

- Move heavy ML model loading to a background worker or microservice to reduce backend startup time.
- Add authentication for APIs and rate limiting.
- Replace SQLite with PostgreSQL for concurrent usage and stronger data integrity.
- Add unit and integration tests for NLU and workflow transitions.
- Convert Windows-only scripts to cross-platform shell scripts (bash) or use a Makefile / invoke tasks.

---


## License

This project is provided as a demo. Add a license if you want to share/distribute under specific terms (e.g., MIT).

---

Thank you — this README was added to describe the project, how to run it locally, and important notes about dependencies.

