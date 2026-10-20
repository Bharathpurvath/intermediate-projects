# Project 7 — People Ops

A full-stack employee directory with accounts, role-based permissions, employee CRUD, department and status filters, search, and team access management.

## Run on Windows

Start the API in PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8006
```

In another PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5179. API docs: http://127.0.0.1:8006/docs. Employee records and workspace accounts are stored locally in `backend/employees.db`. To use PostgreSQL, set `DATABASE_URL` in `backend/.env`.

## Permissions

The first account registered becomes Admin. New accounts are Viewers by default. An Admin can change a team member to Editor or Admin in Team access. Admins and Editors can add, edit, and remove employee records; Viewers can view and search the directory.

Keep `backend/.env` private. Use HTTPS and a production secret for public deployment.
