# Project 5 — Bugboard

A full-stack issue tracker with private accounts, issue reports, severity, workflow status, module and assignee fields, search, filters, dashboard counts, and CSV export.

## Run on Windows

In PowerShell, start the API:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8004
```

In another PowerShell window, start the website:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5177. API docs: http://127.0.0.1:8004/docs. SQLite creates `backend/bugs.db` automatically. To use PostgreSQL, set `DATABASE_URL` in `backend/.env`.

## Included

- Private registration and sign-in.
- Report, edit, and delete issues with description and date.
- Set Critical, High, Medium, or Low priority.
- Track Open, In Progress, Resolved, and Closed workflow states.
- Assign an issue to a person and group it by module.
- Search, filter, view dashboard counts, and export results to CSV.

Keep `backend/.env` private. Use HTTPS and a production secret for public deployment.
