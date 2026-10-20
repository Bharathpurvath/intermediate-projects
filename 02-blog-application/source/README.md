# Margin — a personal blog

A responsive full-stack blog with public reading, keyword search, account registration, and author-only post creation, editing, and deletion.

## Start the backend (Windows)

Open PowerShell in this folder and run:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8001
```

The API and interactive documentation are at http://127.0.0.1:8001 and http://127.0.0.1:8001/docs. SQLite is created automatically on first start. PostgreSQL can be configured using `DATABASE_URL` in `backend/.env`.

## Start the website

In a second PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5174. The frontend uses port 5174 so it can run beside Project 1.

## Security notes

Passwords are stored as Argon2 hashes. Login sessions use signed tokens. Never publish `.env` or a real production secret. Set a new `SECRET_KEY` and use HTTPS before public deployment.
