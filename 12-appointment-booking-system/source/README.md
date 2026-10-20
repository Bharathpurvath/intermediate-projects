# Meetwell — Appointment Booking System

Offer future appointment times, browse the community calendar, book or cancel, and see your schedule. The API prevents overlapping times and prevents a member from holding overlapping bookings.

## Run on Windows

Double-click `Start Project.bat`. It opens the website and starts the frontend and API in separate PowerShell windows. Keep both windows open while using the app.

- Website: http://127.0.0.1:5184
- API health: http://127.0.0.1:8011/api/health
- API docs: http://127.0.0.1:8011/docs

Create an account and select **Offer a time** to add availability. To try booking as a client on the same computer, open the app in a private/incognito window, create another account, choose **Find a time**, and book the offered slot. A guest cancellation makes that time available again; a host cancellation removes it from the calendar.

Appointments and accounts are stored locally in `backend/appointments.db`. This learning app is not published online.

## Technology

- React and Vite frontend
- FastAPI API
- SQLite and SQLAlchemy
- JWT sign-in sessions and Argon2 password hashing
- Booking validation and overlap prevention
