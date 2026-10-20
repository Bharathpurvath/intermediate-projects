# Project 6 — Forma Supply

A full-stack sample storefront with product browsing, categories, search, sort, cart, stock tracking, demo checkout, customer accounts, and saved order history.

## Run on Windows

In PowerShell, start the API:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8005
```

In a second PowerShell window, start the store:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5178. API documentation: http://127.0.0.1:8005/docs. A starter catalog is created on first run. SQLite stores orders, users, products, and order items in `backend/store.db`; set `DATABASE_URL` in `backend/.env` to use PostgreSQL.

## Included

- Searchable catalog with categories and price/name sorting.
- Product details and stock display.
- Shopping bag with quantity controls, saved in the browser.
- Accounts and persistent order history.
- Checkout validates stock, calculates prices on the server, and records order and line items.

This is a learning storefront. Checkout is a demo and does not collect payments or arrange shipping. Do not enter real payment details.
