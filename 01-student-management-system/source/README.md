# Student Management System

A first full-stack project with a React frontend and a FastAPI + SQL database backend. It supports creating, listing, searching, editing, and deleting student records.

## Run the backend (PowerShell terminal 1)

```powershell
cd "C:\Users\bhara\OneDrive\Documents\Intermediate Projects\01 Student Management System\backend"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

The backend starts at `http://127.0.0.1:8000`. Its interactive API guide is at `http://127.0.0.1:8000/docs`.

The starter uses SQLite automatically, so you can run it without installing a database server. It is still a real SQL database and saves records in `backend/students.db`. When you are ready to use PostgreSQL, install PostgreSQL, copy `.env.example` to `.env`, and set `DATABASE_URL` to your local PostgreSQL connection string.

## Run the frontend (PowerShell terminal 2)

```powershell
cd "C:\Users\bhara\OneDrive\Documents\Intermediate Projects\01 Student Management System\frontend"
npm install
npm run dev
```

Open the local address Vite prints (usually `http://localhost:5173`). Keep both terminals running while you use the app.

## Main features

- Add and edit students with name, email, course, and study year
- Search the list by name, email, or course
- Delete a record after a confirmation prompt
- Save data in SQL through the FastAPI backend

## Project folders

- `frontend/` — React user interface
- `backend/` — FastAPI API and SQL database