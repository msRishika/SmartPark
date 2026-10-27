# SmartPark — Professional Parking Management System
> Modern, elegant, and intelligent parking management web application built with Python, Flask, and SQLite.

---

## 🌟 Overview & Key Features

**SmartPark** is a full-featured, responsive parking facility management web application designed for real-world parking operations. It manages **30 numbered parking bays** across dedicated vehicle categories, featuring real-time occupancy statistics, an interactive visual parking map, automated queue allocation, and an integrated billing & invoicing engine.

### Core Capabilities:
- **📊 Real-Time Operations Dashboard**:
  - Live capacity KPI summary cards (Total, Available, Occupied, Reserved, Waiting List, Occupancy Rate).
  - Responsive layout that adapts to all screen sizes without horizontal clipping.
  - Dynamic visual charts (Capacity Breakdown Doughnut Chart & Category Distribution Bar Chart powered by Chart.js).
  - Focused live facility overview table with utilization progress meters.
- **🅿️ Interactive Parking Map**:
  - Visual grid of all 30 numbered slots (`S-01` to `S-30`).
  - Clear color-coding: 🟢 **Green** (Available), 🔴 **Red** (Occupied), 🟡 **Yellow** (Reserved).
  - Category filtering: Two-Wheeler, Four-Wheeler, EV Fast Charging, and Reserved/VIP.
  - Direct 1-click slot actions (Quick Park, Reservation Toggle, and Exit & Bill).
- **🚗 Active Vehicles Directory**:
  - Real-time directory of all currently parked vehicles.
  - Live duration counters ticking in real time.
  - Rapid search by vehicle registration number, slot, or category.
  - Instant access to the Vehicle Exit & Billing workflow.
  - Receipt appears **strictly on this page** upon exit completion.
- **⏳ Customer Waiting List**:
  - Automatic waitlisting in FIFO order when parking slots for a category are fully occupied.
  - Automatic slot dispatch: when an occupied vehicle exits, the system automatically allocates the freed slot to the first eligible vehicle in line.
- **📜 Parking & Billing History**:
  - Complete history of past parking sessions with vehicle registration number, slot, entry/exit timestamps, total duration, and charges.
  - Instant search and sorting by Exit Time, Entry Time, Duration, Charges, or Vehicle Number.
  - Printable report view.
- **🧾 Dedicated Receipt Print View**:
  - Official Parking Invoice Receipt generated upon vehicle exit.
  - When clicking **"Print Receipt"**, prints **ONLY the receipt** on a single paper-friendly page, hiding sidebars, navigation, topbar, and tables.
  - Dismissing the receipt closes it cleanly without deleting completed parking history.

---

## 🎨 Premium Theme & UI Design
The application features a modern, executive light palette:
- **Deep Navy Blue** (`#0f172a`, `#1e293b`) for structured contrast, sidebar elevation, and typography.
- **Teal Accent** (`#0d9488`, `#14b8a6`, `#f0fdfa`) for active navigation, key action buttons, and highlights.
- **Soft Blue & Slate** (`#0284c7`, `#38bdf8`, `#f8fafc`) for cards, progress bars, and informative badges.
- **Status Accents**: Emerald Green for Available bays, Coral Red for Occupied bays, and Amber for Reserved/Waitlisted items.

---

## 📁 Project Structure
```
SmartPark/
├── app.py                      # Flask routes, API endpoints, session management & billing controller
├── parking_manager.py          # Core allocation, exit & billing engine, collections.deque queue
├── database.py                 # SQLite initialization, connections & persistence helpers
├── schema.sql                  # Database schema definition with tables and indexes
├── requirements.txt            # Python dependencies (Flask)
├── README.md                   # Full documentation & run guide
├── static/
│   ├── css/
│   │   └── style.css           # Premium UI styling + dedicated @media print layout
│   └── js/
│       └── script.js           # Live tickers, Chart.js integrations, bill calculation & modal controls
├── templates/
│   ├── base.html               # Shared layout with 5-section sidebar and topbar
│   ├── dashboard.html          # Responsive KPI cards, capacity charts, and live category overview
│   ├── parking_map.html        # 30-slot visual parking grid with real-time status
│   ├── vehicles.html           # Active vehicles directory with dedicated printable receipt area
│   ├── waiting_list.html       # Customer waiting list with FIFO queue flow
│   └── history.html            # Searchable and sortable completed parking sessions
└── tests/
    ├── test_parking_manager.py # Unit tests for allocation, exit, defensive billing & persistence
    └── test_app.py             # Integration tests for routes, receipt scoping, and dashboard sizing
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
Run the test suite (20 unit and integration tests):
```powershell
python -m unittest discover tests -v
```
*(All 20 tests will pass cleanly).*

### Step 4: Start the Web Server
```powershell
python app.py
```
*(You will see: `Web Server running at: http://127.0.0.1:5000`)*

### Step 5: Open in Your Browser
Navigate to:
👉 **`http://127.0.0.1:5000`**

---

## 🔍 Verification Steps for Recent Fixes

### 1. Print Only the Parking Receipt
1. Open `http://127.0.0.1:5000/vehicles`.
2. Click **"➕ Park New Vehicle"** and park a car (e.g. `KA-01-TEST`).
3. Click **"Exit & Bill"** for that car and click **"Confirm and Bill"**.
4. The parking receipt appears on top of the Active Vehicles page.
5. Click **"🖨️ Print Receipt"**.
6. In the browser's print preview dialog:
   - Notice that **ONLY the receipt** is displayed.
   - The sidebar, top navigation, search bar, active vehicles table, and buttons are hidden.
   - The receipt is centered and fits on a single clean page.
7. Cancel or close the print preview: the website layout on the screen remains completely unchanged.

### 2. Receipt Scoped Only to Active Vehicles Page
1. With the receipt visible on `/vehicles`:
2. Click **Dashboard** in the sidebar. Notice the dashboard displays its normal content immediately with **no receipt card**.
3. Click **Parking Map** &rarr; normal map content only.
4. Click **Waiting List** &rarr; normal waitlist content only.
5. Click **Parking History** &rarr; normal completed sessions table only.
6. Click **Active Vehicles** again &rarr; the old receipt does not linger or reappear.
7. Park another car and exit it &rarr; on the receipt, click **"Dismiss"** &rarr; the receipt closes immediately without deleting history or payment records.

### 3. Dashboard Responsiveness & No Horizontal Overflow
1. Open `http://127.0.0.1:5000/dashboard`.
2. Notice that all 6 KPI cards (including the 6th card **Occupancy Rate**) are completely visible.
3. There is **no horizontal scrollbar** at standard desktop sizes (1280px, 1366px, 1920px).
4. Resize your browser window to a narrower width (tablet or mobile):
   - The summary cards wrap into 3 or 2 columns smoothly.
   - The charts resize responsively.
   - The quick vehicle entry and live category overview stack cleanly without horizontal clipping.
