# Keepsake — File Management System

A responsive private file library. Sign up or sign in, upload files, search and filter your library, download a copy, or delete files you no longer need.

## Run on Windows

Double-click `Start Project.bat`. It opens the website and starts the API and frontend in separate PowerShell windows. Keep both windows open while using the app.

- Website: http://127.0.0.1:5181
- API health: http://127.0.0.1:8008/api/health
- API docs: http://127.0.0.1:8008/docs

Create an account to begin. Each account sees only its own files. Upload limit: 15 MB per file. Files are kept in `backend/storage` and file details are saved in `backend/files.db` on this computer. Blocked executable and script types cannot be uploaded.

## Technology

- React and Vite
- FastAPI
- SQLite and SQLAlchemy
- JWT sign-in tokens and Argon2 password hashing
- Multipart file uploads and per-account storage
- Responsive interface
