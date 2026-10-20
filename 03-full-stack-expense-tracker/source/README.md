# Project 3 — Pocket Ledger

A full-stack personal expense tracker with private accounts, income and expense transactions, month filters, category filters, summary cards, six-month cashflow, category breakdown, and CSV export.

## Run on Windows

Open PowerShell in this folder. Start the API:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8002
```

Open a second PowerShell window and start the website:

```powershell
cd frontend
npm install
npm run dev
```

Then open http://localhost:5175. Interactive API documentation: http://127.0.0.1:8002/docs. SQLite data is created automatically in `backend/expenses.db`. PostgreSQL can be used by setting `DATABASE_URL` in `backend/.env`.

## Features

- Register and sign in; each account sees only its own records.
- Add, edit, and delete income or expenses.
- Filter records by month, type, category, and search term.
- See income, expenses, and net cashflow for the selected month.
- Compare the last six months and view spending by category.
- Export the selected month's transactions as CSV.

Never publish `.env` or a real production secret. Use HTTPS and replace the local secret before any public deployment.
