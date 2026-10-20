# Project 15 — Pocket Ledger

A responsive personal finance dashboard for tracking income, expenses, category budgets, and monthly trends.

## Run on Windows

1. Double-click `Start Project.bat`.
2. On first launch, the app installs the needed packages. This can take a minute.
3. Your browser opens `http://127.0.0.1:5187`.
4. Create your private account, then select **Load sample month** to explore, or add your own entries.
5. Keep both terminal windows open while using it. Close them to stop the app.

## Features

- Private account and sign-in
- Record income and expenses with categories, dates, and notes
- Month picker and searchable, filterable transaction ledger
- Income, expense, balance, and savings rate summaries
- Six-month income and expense chart
- Spending breakdown by category
- Monthly category budgets with progress indicators and editing
- Sample month data for a one-click guided tour
- SQLite database stored in `backend/finance.db`

## Stack

React, Vite, Recharts, FastAPI, SQLAlchemy, and SQLite.

This is a local learning project. Before deploying it or entering sensitive financial data into a public service, configure secure production secrets, HTTPS, backups, and deployment-grade authentication.
