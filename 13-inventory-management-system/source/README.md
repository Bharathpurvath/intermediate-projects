# Stockroom — Inventory Management System

A responsive small-business inventory dashboard. Manage products and SKUs, track unit cost and quantities, set reorder levels, record stock received or issued, and review a movement history. The summary includes units, item count, low-stock count, and on-hand value.

## Run on Windows

Double-click `Start Project.bat`. It opens the website and starts the API and frontend in separate PowerShell windows. Keep both windows open while using the app.

- Website: http://127.0.0.1:5185
- API health: http://127.0.0.1:8012/api/health
- API docs: http://127.0.0.1:8012/docs

Create an account. Add your own products, or choose **Load example inventory** to add seven clearly labeled sample items. You can edit, adjust, or delete the sample items just like your own. Each account has a separate inventory. The database is stored locally in `backend/inventory.db`.

## Technology

- React and Vite frontend
- FastAPI API
- SQLite and SQLAlchemy
- JWT sign-in sessions and Argon2 password hashing
- Product CRUD, stock adjustment history, category filtering, and low-stock alerts
