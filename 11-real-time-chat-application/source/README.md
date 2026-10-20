# Goodtalk — Real Time Chat Application

A private account-based direct messaging app. Goodtalk uses WebSockets for live message delivery and typing indicators, stores conversation history in SQLite, and shows member presence.

## Run on Windows

Double-click `Start Project.bat`. It opens the website and starts the API and frontend in separate PowerShell windows. Keep both windows open while chatting.

- Website: http://127.0.0.1:5183
- API health: http://127.0.0.1:8010/api/health
- API docs: http://127.0.0.1:8010/docs

Create an account. To try a live conversation on one computer, open the site in a separate browser or private/incognito window and create a second account. Each account uses its own sign-in session. Select each other from the People tab and send messages; both conversations update live.

Message and account data are saved locally in `backend/chat.db`. This is a local learning project; public chats need an online host and a production security review.

## Technology

- React and Vite frontend
- FastAPI with WebSockets
- SQLite and SQLAlchemy
- JWT login sessions and Argon2 password hashing
- Live presence, typing indicators, and persisted chat history
