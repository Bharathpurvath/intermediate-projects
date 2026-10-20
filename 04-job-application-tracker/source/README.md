# Project 4 — Next Chapter

A full-stack job application tracker with private accounts, application stages, dashboard counts, search, editing, quick status changes, and CSV export.

## Run on Windows

Open PowerShell in this folder and start the API:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8003
```

Open a second PowerShell window and start the website:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5176. API documentation: http://127.0.0.1:8003/docs. SQLite stores records in `backend/applications.db`; set `DATABASE_URL` in `backend/.env` to use PostgreSQL instead.

## Features

- Create a private account and sign in.
- Track company, job title, status, location, work arrangement, salary range, listing link, date, and notes.
- Move each application through Saved, Applied, Interviewing, Offer, and Rejected.
- See totals, active applications, interviews, and a response rate.
- Search and filter your application list; export visible rows to CSV.
- Each account can only see and manage its own applications.

Keep `backend/.env` private. For a public deployment, use HTTPS and set a production secret.
