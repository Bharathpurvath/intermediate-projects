# BrightTest — Online Examination System

A responsive exam app with timed multiple-choice tests, saved answers, automatic scoring, and reviewable explanations.

## Start it on Windows

Double-click `Start Project.bat`. It opens the frontend in your browser and starts the frontend and API in two PowerShell windows. Keep both windows running while using the app.

- App: http://127.0.0.1:5180
- API health: http://127.0.0.1:8007/api/health
- API documentation: http://127.0.0.1:8007/docs

The first account you register is the administrator. It can take the included Web Fundamentals exam, make new exams, and publish or remove exams. Accounts created afterwards are students. Exams, accounts, and results are saved in `backend/exams.db` on this computer.

## Technology

- React and Vite frontend
- FastAPI API
- SQLite database
- Argon2 password hashing and JWT login tokens
- Responsive dark interface
