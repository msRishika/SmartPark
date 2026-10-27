# SmartPark — Smart Parking Slot Allocation System
> **An Advanced Data Structures & Algorithms (DSA) Web Project**  
> Built with **Python, Flask, SQLite, collections.deque, Hashing, Linear Search, and Merge/Quick Sort**.

---

## 📌 Project Overview
**SmartPark** is a full-featured, responsive college-level DSA project that simulates an intelligent real-time parking lot management system. It manages **30 designated parking slots** across multiple vehicle categories (Two-Wheeler, Four-Wheeler, EV Charging, Reserved/VIP).

Unlike typical web applications that leave algorithms on paper, **SmartPark connects real Data Structures and Algorithms directly to live application features**:
1. **Hashing (Python Dictionary)**: $O(1)$ active vehicle lookup and duplicate entry prevention.
2. **Searching (Linear Search)**: $O(N)$ sequential scanning to allocate the first eligible vacant slot.
3. **Queue (`collections.deque`)**: True $O(1)$ FIFO waiting queue when parking is full, with automatic dispatch when a slot is released.
4. **Sorting (Merge Sort & Quick Sort)**: Custom $O(N \log N)$ recursive divide-and-conquer algorithms to sort completed parking sessions by Vehicle Number, Entry Time, Duration, or Fee.

---

## 🏗️ Architecture & Technology Stack
- **Backend**: Python 3.x, Flask (Lightweight WSGI framework)
- **DSA Engine**: `parking_manager.py` (Strictly separated DSA layer)
- **Database**: SQLite3 (`smartpark.db`) with parameterized queries, indexes, and ACID transactions
- **Frontend**: Responsive HTML5, CSS3 (Modern clean light theme), Vanilla JavaScript
- **Visualizations**: Chart.js for real-time capacity and category distribution charts
- **Testing**: Python `unittest` suite with 15 automated test cases

---

## 📁 Project Directory Structure
```
SmartPark/
├── app.py                      # Flask routes, API endpoints & controller logic
├── parking_manager.py          # Core DSA Engine (Hashing, Linear Search, Deque, Merge/Quick Sort)
├── database.py                 # SQLite schema initialization, connection & persistence helpers
├── schema.sql                  # Database schema definition with table structures and indexes
├── requirements.txt            # Project dependencies (Flask)
├── README.md                   # Complete documentation & faculty viva demonstration guide
├── static/
│   ├── css/
│   │   └── style.css           # Modern light theme CSS with responsive grid and parking map styling
│   └── js/
│       └── script.js           # Frontend interactivity, Chart.js integrations, and live tickers
├── templates/
│   ├── base.html               # Shared layout with responsive sidebar, navbar, and modals
│   ├── dashboard.html          # KPI cards, real-time Chart.js charts, and live DSA telemetry
│   ├── parking_map.html        # Visual 30-slot parking grid (Green=Available, Red=Occupied, Yellow=Reserved)
│   ├── vehicles.html           # Active parked vehicles directory with instant O(1) search
│   ├── waiting_queue.html      # FIFO queue visualizer using collections.deque
│   ├── history.html            # Searchable and sortable parking records with algorithm telemetry
│   └── dsa_insights.html       # Academic viva guide with Big-O matrix and complexity proofs
└── tests/
    ├── test_parking_manager.py # Unit tests for all DSA operations and edge cases
    └── test_app.py             # Integration tests for Flask routes, forms, and API endpoints
```

---

## 🧠 Data Structures & Algorithms (DSA) Implementation

### 1. Hashing — Python Dictionary (`dict`)
- **Applied In**: `pm.active_vehicles` in `parking_manager.py`.
- **Purpose**: Rapid $O(1)$ duplicate checking when vehicles enter and instant session lookup when vehicles exit.
- **Why It Matters**: Prevents duplicate entry of vehicles without scanning 30 slots or running costly database queries.
- **Complexity**:
  - **Lookup / Insertion / Deletion**: $O(1)$ Average Case, $O(N)$ Worst Case (extreme hash collisions).
  - **Space**: $O(K)$ where $K$ is the number of active parked vehicles.

### 2. Searching — Linear Search
- **Applied In**: `find_first_available_slot(vehicle_category)` in `parking_manager.py`.
- **Purpose**: Sequentially scans the 30 parking slots to find the first slot that is both `available` and `eligible` for the vehicle category.
- **Why It Matters**: Accurately models a physical parking lot where drivers take the first open stall along the driveway.
- **Complexity**:
  - **Best Case**: $O(1)$ (First slot checked is vacant and eligible).
  - **Worst Case**: $O(N)$ (Only the 30th slot is vacant, or all slots are occupied).
  - **Auxiliary Space**: $O(1)$.

### 3. Queue — First-In, First-Out (`collections.deque`)
- **Applied In**: `pm.waiting_queue = deque()` in `parking_manager.py`.
- **Purpose**: Manages vehicles waiting for a slot when all eligible slots are full.
- **Why `collections.deque` over Python `list`**:
  - Python `list.pop(0)` takes $O(N)$ because all $N-1$ remaining items must be shifted in memory.
  - Python's `collections.deque` is implemented as a doubly linked list of memory blocks, guaranteeing true $O(1)$ time complexity for both `append()` (enqueue) and `popleft()` (dequeue).
- **Auto-Allocation Trigger**: When any vehicle exits, the system automatically inspects the deque in FIFO order and assigns the newly freed slot to the first eligible waiting vehicle.

### 4. Sorting — Merge Sort & Quick Sort
- **Applied In**: `merge_sort_history()` and `quick_sort_history()` in `parking_manager.py`.
- **Purpose**: Sorts completed parking sessions by Vehicle Number, Entry Time, Duration, or Fee.
- **Why Merge Sort**:
  - Stable divide-and-conquer algorithm.
  - Guaranteed worst-case time complexity of $O(N \log N)$ governed by recurrence relation:
    $$T(N) = 2T(N/2) + O(N) \implies O(N \log N)$$
- **Telemetry Counter**: Both algorithms track the exact number of comparisons made, which is displayed directly in the UI for academic evaluation.

### Master Complexity Matrix
| Operation | Algorithm / Structure | Best Case | Average Case | Worst Case | Space Complexity |
| :--- | :--- | :---: | :---: | :---: | :---: |
| Duplicate Check | Hash Map (`dict`) | $O(1)$ | $O(1)$ | $O(N)$ | $O(N)$ |
| Slot Search | Linear Search | $O(1)$ | $O(N)$ | $O(N)$ | $O(1)$ |
| Enqueue Waiting | `collections.deque.append()` | $O(1)$ | $O(1)$ | $O(1)$ | $O(1)$ |
| Dequeue Waiting | `collections.deque.popleft()` | $O(1)$ | $O(1)$ | $O(1)$ | $O(1)$ |
| History Sorting | Merge Sort | $O(N \log N)$ | $O(N \log N)$ | $O(N \log N)$ | $O(N)$ |
| History Sorting | Quick Sort | $O(N \log N)$ | $O(N \log N)$ | $O(N^2)$ | $O(\log N)$ |

---

## 🅿️ Parking Lot Slot Distribution (30 Slots)
- **Slots S-01 to S-06 (6 Slots)**: Dedicated Two-Wheeler Bay (Motorcycles / Scooters)
- **Slots S-07 to S-22 (16 Slots)**: Four-Wheeler Bays (Cars / Sedans / SUVs)
- **Slots S-23 to S-26 (4 Slots)**: EV Fast Charging Bays
- **Slots S-27 to S-30 (4 Slots)**: Reserved / Accessible / Priority Bays

### Real-Time Color Coding:
- 🟢 **Green**: Available for immediate parking.
- 🔴 **Red**: Currently occupied by a parked vehicle.
- 🟡 **Yellow**: Reserved (VIP, maintenance, or accessible).

---

## 🚀 Step-by-Step Installation & Run Guide on Windows

### Prerequisites
- Windows 10 or 11
- Python 3.8 or higher installed and added to PATH (`python --version`)

### Step 1: Open Terminal in the Project Directory
Open **PowerShell** or **Command Prompt** and navigate to the project directory:
```powershell
cd C:\Users\msris\OneDrive\Documents\SmartPark
```

### Step 2: Install Dependencies
Install Flask from `requirements.txt`:
```powershell
python -m pip install -r requirements.txt
```

### Step 3: Initialize the SQLite Database
Initialize the 30 slots in SQLite:
```powershell
python database.py
```
*(You will see: `Database initialized successfully with 30 slots.`)*

### Step 4: Run the Automated Unit Tests
Verify all 15 test cases pass:
```powershell
python -m unittest discover tests
```
*(You will see: `Ran 15 tests in ... OK`)*

### Step 5: Start the Flask Application
Run the main application:
```powershell
python app.py
```
*(You will see: `Access web UI at: http://127.0.0.1:5000`)*

### Step 6: Open in Your Web Browser
Open any web browser (Chrome, Edge, Firefox) and navigate to:
```
http://127.0.0.1:5000
```

---

## 🎓 Faculty Viva & Demonstration Script
When presenting this project to your college professors or examiners, follow this exact sequence to demonstrate each DSA concept effectively:

### 1. Introduction to the Dashboard & Telemetry
- Open `http://127.0.0.1:5000`.
- Show the **KPI Cards** (Total Slots: 30, Available: 28, Reserved: 2, Waiting: 0).
- Highlight the **Live DSA Performance Telemetry Banner**, which reports live metrics from `parking_manager.py` (Active hash keys, linear search probes, deque items, and sort comparisons).
- Show the two live **Chart.js visualizations** (Real-Time Occupancy Breakdown & Category Distribution).

### 2. Demonstrating Hashing & $O(1)$ Duplicate Rejection
- Click the **"➕ Park Vehicle"** button in the top navigation bar.
- Enter vehicle registration number: `KA-01-AB-1234` and select `Four-Wheeler`.
- Click **"Allocate Slot"**. Notice it allocates `Slot S-07` via Linear Search.
- Now, try to enter `KA-01-AB-1234` again.
- **Viva Explanation**: *"The system immediately rejects the vehicle with an alert: 'Duplicate vehicle! Vehicle KA-01-AB-1234 is already parked in Slot S-07'. This is checked in $O(1)$ constant time using Python's in-memory dictionary `self.active_vehicles`, avoiding an unnecessary database search."*

### 3. Demonstrating Linear Search ($O(N)$) on the Visual Parking Map
- Navigate to the **🅿️ Parking Map** page.
- Explain the 30-slot layout: Zone A (Two-Wheeler S-01 to S-06), Zone B & C (Four-Wheeler S-07 to S-22), Zone D (EV Charging S-23 to S-26), and Zone E (Reserved S-27 to S-30).
- Point out the color coding: Green (Available), Red (Occupied), Yellow (Reserved).
- Notice that `KA-01-AB-1234` is parked in `S-07`.
- Park a second car: `KA-01-CD-5678`. Show that Linear Search progresses to the next available slot: `S-08`.

### 4. Demonstrating the FIFO Waiting Queue (`collections.deque`)
- To quickly demonstrate this without typing 6 vehicles manually, click the **"⚡ Demo Data"** button on the top bar.
- Navigate to the **⏳ FIFO Queue** page.
- Show the examiner the **Visual FIFO Flow** showing Queue Position #1 (Head) to #2 (Tail).
- **Viva Explanation**: *"When all slots for a vehicle category are full, vehicles enter a FIFO queue. We used `collections.deque` instead of a standard Python list. If we used `list.pop(0)`, removing an element would take $O(N)$ time as memory blocks shift. `collections.deque` is a doubly linked list, giving guaranteed $O(1)$ time for both enqueue (`append`) and dequeue (`popleft`)."*

### 5. Demonstrating Automatic FIFO Queue Dispatch on Vehicle Exit
- In the top bar or on the map, find a parked Two-Wheeler (e.g. `KA-01-MJ-1001` in `S-01`).
- Click **"Exit Vehicle"**.
- A modal opens showing duration and billing. Select *"Simulate 30 Minutes"* and click **"Confirm Exit & Bill"**.
- Observe the flash notification:
  > *"FIFO Queue Dispatch: Waiting vehicle KA-02-WQ-7777 was automatically allocated freed Slot S-01!"*
- Open the **🅿️ Parking Map**: Slot S-01 is now occupied by `KA-02-WQ-7777`.
- Open the **⏳ FIFO Queue**: Position #1 has progressed to the next vehicle!

### 6. Demonstrating Merge Sort & Quick Sort on Parking History
- Click **📜 Parking History** in the sidebar.
- Show the table of completed parking sessions.
- In the sort controls:
  - Set **Sort By Attribute** to `Duration (Minutes)`
  - Set **Sort Order** to `Descending`
  - Select **DSA Algorithm** as `Merge Sort (O(N log N))`
  - Click **Apply**.
- Highlight the **Sort Algorithm Telemetry Banner** showing the exact number of comparisons made.
- Now switch the algorithm to `Quick Sort` and click **Apply** to show the comparison count differences.
- **Viva Explanation**: *"Merge Sort recursively divides the list into halves ($T(N) = 2T(N/2) + O(N)$) and merges them in sorted order. It guarantees stable $O(N \log N)$ sorting even in the worst case."*

### 7. Navigating to the Academic Viva Insights Page
- Click **🧠 DSA Insights & Viva** in the sidebar.
- Show the examiner the Master Complexity Table, code snippets, and theoretical explanations.

---

## 🧪 Running Automated Tests
Run the test suite anytime using Python's built-in test runner:
```powershell
python -m unittest discover tests -v
```
All 15 tests verify:
- Initial 30-slot categorization
- Sequential linear search allocation
- $O(1)$ duplicate vehicle rejection via hashing
- Full parking detection and FIFO queue enqueuing
- Vehicle exit, duration billing, and history persistence
- Automatic FIFO queue dispatch upon slot release
- Merge Sort and Quick Sort correctness across multiple data types
- Persistence across server restarts

---

## 📄 License & Academic Attribution
Developed as an advanced academic Computer Science & Engineering college project demonstrating real-world applications of Data Structures and Algorithms (DSA) in Web Architecture.
