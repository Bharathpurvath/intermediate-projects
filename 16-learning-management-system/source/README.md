# Project 16 — Learning Garden

A responsive learning management app for organizing courses, adding lessons, and tracking progress at your own pace.

## Run on Windows

1. Double-click `Start Project.bat`.
2. On first launch, the app installs its dependencies. This can take a minute.
3. Your browser opens `http://127.0.0.1:5188`.
4. Create an account, then choose **Explore with sample courses** or add your own course.
5. Open a course to add lessons and mark them complete. Keep both terminal windows open while using the app.

## Features

- Private account and sign-in
- Add, edit, search, filter, and remove courses
- Organize by subject, status, instructor, and target date
- Add lessons, check them off, and remove them
- Automatic lesson and overall progress tracking
- Course statuses update when all lessons are complete
- Responsive layout with a sample library
- SQLite database stored in `backend/learning.db`

## Stack

React, Vite, FastAPI, SQLAlchemy, and SQLite.

This is a local learning project. Before deploying it publicly, configure secure production secrets, HTTPS, backups, and deployment-grade authentication.
## GitHub Pages edition

The `frontend/publish` folder contains a standalone static edition for GitHub Pages. It stores course and lesson data in the current browser's localStorage, so each visitor has a separate library on that device. It does not use the FastAPI service or synchronize data between devices.

The full React + FastAPI app remains available locally using `Start Project.bat`.
