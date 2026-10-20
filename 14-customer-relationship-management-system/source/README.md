# Project 14 — Fieldnotes CRM

A responsive, full-stack customer relationship manager for organizing contacts, sales conversations, follow-ups, and deal values.

## Run it on Windows

1. Double-click `Start Project.bat`.
2. The first launch installs the project dependencies and may take a minute.
3. Your browser opens `http://127.0.0.1:5186`.
4. Create an account. Use **Load sample leads** to explore the dashboard, or add your own first lead.
5. Keep both terminal windows open while you use the app. Close them to stop it.

## Features

- Private account and sign-in
- Create, edit, inspect, move, search, filter, and remove leads
- Deal value and six sales stages
- Follow-up dates, overdue reminders, and upcoming list
- Pipeline summary and win rate
- Responsive dashboard for desktop and mobile
- SQLite database stored in `backend/crm.db`

## Stack

React, Vite, FastAPI, SQLAlchemy, SQLite, and bearer-token authentication.

This starter is designed for local learning and development. Before putting a CRM with real customer information on a public server, configure secure production secrets, HTTPS, backups, and deployment-grade authentication.
