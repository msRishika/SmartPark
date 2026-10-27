/**
 * SmartPark - Smart Parking Slot Allocation System
 * Frontend interactivity, Chart.js visualizations, modal handling,
 * and live duration tickers.
 */

document.addEventListener("DOMContentLoaded", function () {
  initLiveClock();
  initFlashDismissal();
  initModals();
  initDurationTicker();
  initDashboardCharts();
  initTableSearch();
});

/* ==========================================================================
   1. LIVE CLOCK
   ========================================================================== */
function initLiveClock() {
  const clockEl = document.getElementById("liveClock");
  if (!clockEl) return;

  function updateClock() {
    const now = new Date();
    const options = {
      weekday: "short",
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true
    };
    clockEl.textContent = now.toLocaleDateString("en-US", options);
  }

  updateClock();
  setInterval(updateClock, 1000);
}

/* ==========================================================================
   2. FLASH MESSAGE AUTO-DISMISSAL
   ========================================================================== */
function initFlashDismissal() {
  const alerts = document.querySelectorAll(".alert");
  alerts.forEach(function (alert) {
    const closeBtn = alert.querySelector(".alert-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        alert.style.opacity = "0";
        alert.style.transform = "translateY(-10px)";
        alert.style.transition = "all 0.3s ease";
        setTimeout(() => alert.remove(), 300);
      });
    }

    // Auto dismiss after 7 seconds
    setTimeout(function () {
      if (document.body.contains(alert)) {
        alert.style.opacity = "0";
        alert.style.transform = "translateY(-10px)";
        alert.style.transition = "all 0.3s ease";
        setTimeout(() => alert.remove(), 300);
      }
    }, 7000);
  });
}

/* ==========================================================================
   3. MODAL HANDLERS
   ========================================================================== */
function initModals() {
  // Close buttons
  const closeBtns = document.querySelectorAll("[data-close-modal]");
  closeBtns.forEach(btn => {
    btn.addEventListener("click", function () {
      const modalId = btn.getAttribute("data-close-modal");
      closeModal(modalId);
    });
  });

  // Close when clicking on backdrop
  const modals = document.querySelectorAll(".modal-backdrop");
  modals.forEach(modal => {
    modal.addEventListener("click", function (e) {
      if (e.target === modal) {
        modal.classList.remove("show");
      }
    });
  });

  // Mobile sidebar toggle
  const mobileToggle = document.getElementById("mobileToggle");
  const sidebar = document.querySelector(".sidebar");
  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener("click", function () {
      sidebar.classList.toggle("open");
    });
  }
}

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add("show");
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove("show");
  }
}

// Quick Park modal with optional slot preselection
function openParkModal(slotId, slotNumber, category) {
  const modal = document.getElementById("parkVehicleModal");
  if (!modal) return;

  const slotInput = modal.querySelector("#preferredSlotId");
  const slotDisplay = modal.querySelector("#selectedSlotDisplay");
  const categorySelect = modal.querySelector("#vehicleCategory");

  if (slotId && slotNumber) {
    if (slotInput) slotInput.value = slotId;
    if (slotDisplay) {
      slotDisplay.style.display = "block";
      slotDisplay.textContent = `Selected Target: Slot ${slotNumber} (${category})`;
    }
    if (categorySelect && category && category !== "Reserved") {
      categorySelect.value = category;
    }
  } else {
    if (slotInput) slotInput.value = "";
    if (slotDisplay) slotDisplay.style.display = "none";
  }

  modal.classList.add("show");
}

// Exit vehicle modal with prefilled vehicle number
function openExitModal(vehicleNumber, slotNumber, category, entryTime) {
  const modal = document.getElementById("exitVehicleModal");
  if (!modal) return;

  const vehInput = modal.querySelector("#exitVehicleNumber");
  const vehDisplay = modal.querySelector("#exitVehDisplay");
  const detailsBox = modal.querySelector("#exitDetailsBox");

  if (vehInput) vehInput.value = vehicleNumber;
  if (vehDisplay) vehDisplay.textContent = vehicleNumber;

  if (detailsBox) {
    detailsBox.innerHTML = `
      <div style="font-size: 0.85rem; line-height: 1.6; color: var(--text-muted);">
        <div><strong>Slot Assigned:</strong> ${slotNumber}</div>
        <div><strong>Category:</strong> ${category}</div>
        <div><strong>Entry Time:</strong> ${entryTime || 'N/A'}</div>
      </div>
    `;
  }

  modal.classList.add("show");
}

/* ==========================================================================
   4. LIVE DURATION TICKER FOR PARKED VEHICLES
   ========================================================================== */
function initDurationTicker() {
  const tickers = document.querySelectorAll("[data-entry-time]");
  if (tickers.length === 0) return;

  function updateDurations() {
    const now = new Date();
    tickers.forEach(el => {
      const entryStr = el.getAttribute("data-entry-time");
      if (!entryStr) return;

      // Parse "YYYY-MM-DD HH:MM:SS"
      const parts = entryStr.split(/[- :]/);
      if (parts.length >= 6) {
        const entryDate = new Date(parts[0], parts[1] - 1, parts[2], parts[3], parts[4], parts[5]);
        const diffSeconds = Math.max(0, Math.floor((now - entryDate) / 1000));
        
        const hours = Math.floor(diffSeconds / 3600);
        const minutes = Math.floor((diffSeconds % 3600) / 60);
        const seconds = diffSeconds % 60;

        let display = "";
        if (hours > 0) display += `${hours}h `;
        display += `${minutes}m ${seconds}s`;

        el.textContent = display;
      }
    });
  }

  updateDurations();
  setInterval(updateDurations, 1000);
}

/* ==========================================================================
   5. DASHBOARD CHARTS (CHART.JS)
   ========================================================================== */
function initDashboardCharts() {
  const occupancyCanvas = document.getElementById("occupancyChart");
  const categoryCanvas = document.getElementById("categoryChart");

  if (!occupancyCanvas && !categoryCanvas) return;

  fetch("/api/stats")
    .then(response => response.json())
    .then(data => {
      // 1. Occupancy Breakdown Doughnut Chart
      if (occupancyCanvas && typeof Chart !== "undefined") {
        new Chart(occupancyCanvas, {
          type: "doughnut",
          data: {
            labels: data.chart_data.occupancy.labels,
            datasets: [{
              data: data.chart_data.occupancy.data,
              backgroundColor: ["#10b981", "#ef4444", "#f59e0b"],
              borderColor: "#ffffff",
              borderWidth: 2,
              hoverOffset: 4
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                position: "bottom",
                labels: {
                  boxWidth: 12,
                  font: { size: 12, family: "-apple-system, sans-serif" }
                }
              },
              tooltip: {
                callbacks: {
                  label: function (context) {
                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                    const val = context.raw || 0;
                    const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                    return ` ${context.label}: ${val} slots (${pct}%)`;
                  }
                }
              }
            },
            cutout: "68%"
          }
        });
      }

      // 2. Category Distribution Bar Chart
      if (categoryCanvas && typeof Chart !== "undefined") {
        new Chart(categoryCanvas, {
          type: "bar",
          data: {
            labels: data.chart_data.category.labels,
            datasets: [
              {
                label: "Occupied Slots",
                data: data.chart_data.category.occupied,
                backgroundColor: "#ef4444",
                borderRadius: 4
              },
              {
                label: "Available Slots",
                data: data.chart_data.category.available,
                backgroundColor: "#10b981",
                borderRadius: 4
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: {
                grid: { display: false },
                ticks: { font: { size: 11 } }
              },
              y: {
                beginAtZero: true,
                ticks: { stepSize: 2, font: { size: 11 } },
                grid: { color: "#f1f5f9" }
              }
            },
            plugins: {
              legend: {
                position: "bottom",
                labels: { boxWidth: 12 }
              }
            }
          }
        });
      }
    })
    .catch(err => {
      console.warn("Could not load /api/stats data:", err);
    });
}

/* ==========================================================================
   6. CLIENT-SIDE INSTANT TABLE SEARCH
   ========================================================================== */
function initTableSearch() {
  const searchInput = document.getElementById("tableSearchInput");
  const targetTable = document.getElementById("searchableTable");

  if (!searchInput || !targetTable) return;

  searchInput.addEventListener("input", function () {
    const query = this.value.toLowerCase().trim();
    const rows = targetTable.querySelectorAll("tbody tr");

    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      if (text.includes(query)) {
        row.style.display = "";
      } else {
        row.style.display = "none";
      }
    });
  });
}
