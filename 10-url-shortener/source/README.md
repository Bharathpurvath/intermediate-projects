# Little Link — URL Shortener

A responsive URL shortener with private accounts, optional custom codes and expiration, click tracking, a seven-day activity chart, and copy/delete controls.

## Run on Windows

Double-click `Start Project.bat`. It opens the website and starts the frontend and API in separate PowerShell windows. Keep both windows open while using the app.

- Website: http://127.0.0.1:5182
- API health: http://127.0.0.1:8009/api/health
- API docs: http://127.0.0.1:8009/docs

Create an account to begin. The generated short addresses point to this computer while the app runs locally. To share working links publicly, the API must later be deployed online.

## Technology

- React and Vite frontend
- FastAPI and SQLite
- JWT sessions and Argon2 password hashing
- Custom aliases, expiration, HTTP redirects, and click analytics
