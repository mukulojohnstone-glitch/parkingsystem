# Smart Parking Management System

A simple Flask learning project for managing 20 parking bays in Kenya. It records vehicle arrivals, assigns the next free bay, calculates fees on exit, simulates payment, and keeps a transaction report.

## Requirements

- Python 3.9 or newer
- Flask

## Run the app

From this folder, create and activate a virtual environment if desired, then run:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

Open <http://127.0.0.1:5000>. The SQLite database `parking.db` is created automatically the first time the app starts.

## Using the system

- **Slots:** View all bays; the grid refreshes automatically.
- **Vehicle entry:** Enter a number plate. The lowest-numbered free bay is assigned.
- **Vehicle exit:** Look up the plate, review the fee, choose M-Pesa, card, or cash, then confirm the simulated payment. The bay is released only when the transaction is recorded.
- **Admin & reports:** Change the amounts for each time band and review completed transactions.

Default rates: up to 30 minutes is free; up to 2 hours is Kshs. 50; up to 4 hours is Kshs. 100; up to 6 hours is Kshs. 300; over 6 hours is Kshs. 500. Rate amounts are stored in SQLite and are editable on the admin page.

## Data structure and storage

SQLite is included with Python and keeps the active vehicles, 20 fixed slot records, configurable rates, and completed transactions between restarts. The slot table is joined to active vehicles to determine each bay's status; an active vehicle's plate uniquely identifies that visit, and its slot number cannot be assigned twice.