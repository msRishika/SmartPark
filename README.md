# SmartPark — Professional Parking Management System
> Modern, elegant, and intelligent parking facility management web application built with Python, Flask, SQLite, and ReportLab.

---

## 🌟 Overview & Key Features

**SmartPark** is an executive, responsive parking facility management web application designed for real-world parking operations. It manages **30 numbered parking bays** across dedicated vehicle categories, featuring real-time occupancy statistics, an interactive visual parking map, automated queue allocation, and an integrated ReportLab PDF invoice generation engine.

### Core Capabilities:
- **📊 Real-Time Operations Dashboard**:
  - Live capacity KPI summary cards (Total, Available, Occupied, Reserved, Waiting List, Occupancy Rate).
  - Responsive layout that fits all screen sizes without horizontal clipping or overflow.
  - Dynamic visual charts (Capacity Breakdown Doughnut Chart & Category Distribution Bar Chart powered by Chart.js).
  - Focused live facility overview table with utilization progress meters.
- **🅿️ Interactive Parking Map**:
  - Visual grid of all 30 numbered slots (`S-01` to `S-30`).
  - Clear color-coding: 🟢 **Green** (Available), 🔴 **Red** (Occupied), 🟡 **Yellow** (Reserved), ⚡ **Teal** (EV Charging).
  - In-place AJAX reservation toggling: reserve multiple slots while staying at the exact same scroll position.
  - Category filtering: Two-Wheeler, Four-Wheeler, EV Fast Charging, and Reserved/VIP.
- **🚗 Active Vehicles Directory & Instant PDF Invoicing**:
  - Real-time directory of all currently parked vehicles with live stay duration tickers.
  - Direct **Exit & Bill**: Clicking **Confirm and Bill** immediately generates and downloads the official PDF tax invoice receipt.
  - No receipt popup, receipt preview, or intermediate buttons.
  - Idempotent billing protection against double-clicks or retries.
- **⏳ Customer Waiting List with Strict Compatibility**:
  - Two-Wheeler slots assign only to Two-Wheelers.
  - Four-Wheeler slots assign only to standard Four-Wheelers.
  - EV Charging slots assign only to EV vehicles requiring charging (never fall back to Four-Wheeler slots).
  - Strict FIFO order dispatch: newly freed slots are assigned only to eligible waiting vehicles for that exact category.
  - Waiting time does not count toward active billing duration.
- **📜 Parking History with Print Receipt & Safe Deletion**:
  - Complete history of past parking sessions with vehicle registration number, slot, entry/exit timestamps, total duration, and charges.
  - **Print Receipt**: Download the original official PDF tax invoice using saved transaction details without altering billing.
  - **Delete Record**: Safely delete individual history records with confirmation; active vehicles and slots remain completely isolated.
  - Instant search and sorting by Exit Time, Entry Time, Duration, Charges, or Vehicle Number.
- **🛡️ Strict Input Validation**:
  - **Vehicle Registration**: Accepts only uppercase English letters (`A–Z`) and digits (`0–9`). Rejects commas, dots, spaces, hyphens, and short inputs (e.g. `ABCD1234` accepted).
  - **Driver Contact**: Accepts exactly 10 digits without letters, spaces, or symbols.
  - Client-side and server-side validation with preserved form inputs on failure.

---

## 🎨 Theme & UI Design
The application features an executive dark palette:
- **Main Background**: Deep Midnight Navy (`#061A33`).
- **Primary Highlights**: Vibrant Teal (`#00CBB0`).
- **Complementary Accents**: Electric Sky Blue (`#0ea5e9`, `#38bdf8`) and Slate Navy (`#0c284d`, `#0a2547`).
- **High-Contrast Status Indicators**:
  - Available: Emerald Green (`#10b981`)
  - Occupied: Coral Red (`#ef4444`)
  - Reserved: Warm Amber (`#f59e0b`)
  - EV Charging: Electric Teal (`#00CBB0`)

---

## 📁 Project Structure
```
SmartPark/
├── app.py                      # Flask routes, API endpoints, PDF streaming & reservation controller
├── parking_manager.py          # Core allocation engine, strict compatibility, FIFO deque, idempotency
├── pdf_generator.py            # ReportLab PDF invoice generation engine (A5 branded receipts)
├── database.py                 # SQLite initialization, connections & persistence helpers
├── schema.sql                  # Database schema definition with tables and indexes
├── requirements.txt            # Python dependencies (Flask, ReportLab)
├── README.md                   # Full documentation & run guide
├── static/
│   ├── css/
│   │   └── style.css           # Premium Midnight Navy & Teal theme styling
│   └── js/
│       └── script.js           # AJAX reservation, PDF blob downloads, input masks & charts
├── templates/
│   ├── base.html               # Shared layout, floating toasts, entry & exit modals
│   ├── dashboard.html          # Responsive KPI cards, capacity charts, and quick entry form
│   ├── parking_map.html        # 30-slot visual parking grid with in-place reservation
│   ├── vehicles.html           # Active vehicles directory with instant exit action
│   ├── waiting_list.html       # Customer waiting list with strict FIFO dispatch
│   └── history.html            # Searchable history with Print Receipt & Delete buttons
└── tests/
    ├── test_parking_manager.py # 14 Unit tests for DSA, validation, compatibility, and idempotency
    └── test_app.py             # 10 Integration tests for routes, PDF downloads, and AJAX
```

---

## 💰 Parking Rates & Billing Rules

Charges are calculated transparently using established category rates:

| Vehicle Category | Dedicated Bays | Base Admission Fee | Hourly Rate |
| :--- | :---: | :---: | :---: |
| **Two-Wheeler** | Slots S-01 to S-06 (6 bays) | Rs. 10.00 | Rs. 15.00 / hr |
| **Four-Wheeler** | Slots S-07 to S-22 (16 bays) | Rs. 20.00 | Rs. 30.00 / hr |
| **EV Charging** | Slots S-23 to S-26 (4 bays) | Rs. 25.00 | Rs. 40.00 / hr |
| **Reserved / VIP** | Slots S-27 to S-30 (4 bays) | Rs. 30.00 | Rs. 50.00 / hr |

$$\text{Hours Billed} = \lceil \text{Duration in Minutes} / 60 \rceil$$
$$\text{Total Fee} = \text{Base Fee} + (\text{Hourly Rate} \times \text{Hours Billed})$$

---

## 🚀 How to Run on Windows

### Step 1: Open Terminal in Project Directory
Open **PowerShell** or **Command Prompt**:
```powershell
cd C:\Users\msris\OneDrive\Documents\SmartPark
```

### Step 2: Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### Step 3: Run the Automated Tests
Run the complete test suite (24 unit and integration tests):
```powershell
python -m unittest discover tests -v
```
*(All 24 tests will pass cleanly).*

### Step 4: Start the Web Server
```powershell
python app.py
```
*(You will see: `Web Server running at: http://127.0.0.1:5000`)*

### Step 5: Open in Your Browser
Navigate to:
👉 **`http://127.0.0.1:5000`**

---

## 🔍 Verification Guide for the 6 Changes

### 1. Active Vehicles — Exit & Bill (Immediate PDF Download)
1. Open `http://127.0.0.1:5000/vehicles`.
2. Click **"➕ Park New Vehicle"** and park a vehicle (e.g. `ABCD1234`, Contact `9876543210`).
3. Click **"Exit & Bill"** on that vehicle, then click **"Confirm and Bill (Download PDF)"**.
4. The official PDF receipt (`SmartPark_Receipt_ABCD1234.pdf`) downloads automatically.
5. Notice that no receipt popup or preview appears on the screen, and the vehicle is removed from the active table.

### 2. Parking History — Print Receipt & Delete
1. Open `http://127.0.0.1:5000/history`.
2. Find the completed record for `ABCD1234`.
3. Click **"🖨️ Print Receipt"**: it immediately downloads the original PDF receipt without altering the bill amount.
4. Click **"🗑️ Delete"**: confirm the prompt. The record is deleted; active vehicles and slots remain completely unaffected.

### 3. Midnight Navy & Teal Redesign
1. Browse **Dashboard**, **Parking Map**, **Active Vehicles**, **Waiting List**, and **Parking History**.
2. Notice the deep Midnight Navy (`#061A33`) background, vibrant Teal (`#00CBB0`) highlights, and sharp status glows.
3. Verify there is no horizontal scrollbar or clipped cards across any desktop or mobile viewport.

### 4. Strict Input Validation
1. In the vehicle entry form, attempt to enter:
   - `KA,01` or `KA-01` or `...`: rejected with error explaining allowed characters.
   - Contact `12345`: rejected with error requiring exactly 10 digits.
2. Enter `ABCD1234` and `9876543210`: accepted and allocated cleanly.

### 5. Strict Slot & Waiting List Compatibility
1. Park 4 EV vehicles to fill slots S-23 to S-26.
2. Enter a 5th EV vehicle: it will be queued to the Waiting List even if Four-Wheeler slots (S-07 to S-22) are vacant.
3. Exit a Four-Wheeler: the freed Four-Wheeler slot will NOT be given to the waiting EV.
4. Exit an EV: the freed EV slot is immediately allocated to the waiting EV in FIFO order.

### 6. Stay in Position & Update in Place (Reservation)
1. Open `http://127.0.0.1:5000/map`.
2. Scroll down to Zone E (Slots S-27 to S-30).
3. Click **"Reserve"** on an available slot:
   - Notice the page stays in the exact same scroll position with no jumping.
   - The slot updates in place to "RESERVED" with a lock icon.
   - A floating toast confirms the reservation.
   - You can reserve another slot immediately without scrolling.
