/**
 * SmartPark — Professional Parking Management System
 * Frontend interactivity, Chart.js integrations, modal handling,
 * live duration tickers, and dynamic bill calculations.
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
        dismissAlert(alert);
      });
    }

    // Auto dismiss after 6 seconds
    setTimeout(function () {
      if (document.body.contains(alert)) {
        dismissAlert(alert);
      }
    }, 6000);
  });
}

function dismissAlert(alert) {
  alert.style.opacity = "0";
  alert.style.transform = "translateY(-8px)";
  alert.style.transition = "all 0.25s ease";
  setTimeout(() => alert.remove(), 250);
}

/* ==========================================================================
   3. MODAL HANDLERS & BILL PREVIEW
   ========================================================================== */
function initModals() {
  // Close buttons with data-close-modal attribute
  const closeBtns = document.querySelectorAll("[data-close-modal]");
  closeBtns.forEach(btn => {
    btn.addEventListener("click", function () {
      const modalId = btn.getAttribute("data-close-modal");
      closeModal(modalId);
    });
  });

  // Close when clicking directly on the backdrop
  const modals = document.querySelectorAll(".modal-backdrop");
  modals.forEach(modal => {
    modal.addEventListener("click", function (e) {
      if (e.target === modal) {
        modal.classList.remove("show");
      }
    });
  });

  // Mobile navigation drawer toggle
  const mobileToggle = document.getElementById("mobileToggle");
  const sidebar = document.querySelector(".sidebar");
  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener("click", function () {
      sidebar.classList.toggle("open");
    });
  }

  // Hook simulation select change in Exit Modal to dynamically recalculate preview
  const simSelect = document.getElementById("simulatedMinutes");
  if (simSelect) {
    simSelect.addEventListener("change", function () {
      recalculateExitPreview();
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

// Vehicle entry modal with optional slot target
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
      slotDisplay.textContent = `Target Slot: ${slotNumber} (${category})`;
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

// Vehicle exit modal: pre-populates details and fetches live billing preview
let currentExitVehicleData = null;

function openExitModal(vehicleNumber, slotNumber, category, entryTime) {
  const modal = document.getElementById("exitVehicleModal");
  if (!modal) return;

  const vehInput = modal.querySelector("#exitVehicleNumber");
  const vehDisplay = modal.querySelector("#exitVehDisplay");
  const previewBox = modal.querySelector("#exitBillPreviewBox");
  const simSelect = modal.querySelector("#simulatedMinutes");

  if (vehInput) vehInput.value = vehicleNumber;
  if (vehDisplay) vehDisplay.textContent = vehicleNumber;
  if (simSelect) simSelect.value = "";

  currentExitVehicleData = {
    vehicleNumber: vehicleNumber,
    slotNumber: slotNumber,
    category: category,
    entryTime: entryTime
  };

  if (previewBox) {
    previewBox.innerHTML = `
      <div style="font-size: 0.85rem; line-height: 1.7; color: var(--text-muted); background: #f8fafc; padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
        <div style="display: flex; justify-content: space-between;"><strong>Slot Assigned:</strong> <span>${slotNumber}</span></div>
        <div style="display: flex; justify-content: space-between;"><strong>Category:</strong> <span>${category}</span></div>
        <div style="display: flex; justify-content: space-between;"><strong>Entry Time:</strong> <span>${entryTime || 'N/A'}</span></div>
        <div style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px dashed var(--border-subtle); text-align: center; color: var(--teal-primary);">
          <em>Loading live billing calculation...</em>
        </div>
      </div>
    `;
  }

  modal.classList.add("show");

  // Fetch live bill estimation from API
  fetch(`/api/preview-bill/${encodeURIComponent(vehicleNumber)}`)
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        currentExitVehicleData = data;
        renderBillPreview(data);
      }
    })
    .catch(err => {
      console.warn("Could not fetch bill preview:", err);
    });
}

function renderBillPreview(data, overrideMinutes) {
  const previewBox = document.getElementById("exitBillPreviewBox");
  if (!previewBox) return;

  let durationMins = overrideMinutes || data.duration_minutes || 1;
  let hoursBilled = Math.ceil(durationMins / 60);
  let baseFee = data.base_fee || 20.0;
  let hourlyRate = data.hourly_rate || 30.0;
  let totalFee = baseFee + (hourlyRate * hoursBilled);

  let hrs = Math.floor(durationMins / 60);
  let mins = durationMins % 60;
  let durationText = hrs > 0 ? `${hrs}h ${mins}m` : `${durationMins} mins`;

  previewBox.innerHTML = `
    <div style="background: #f8fafc; border: 1px solid var(--border-medium); border-radius: var(--radius-md); padding: 1rem; font-size: 0.86rem;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 0.35rem;">
        <span style="color: var(--text-muted);">Assigned Slot:</span>
        <strong>${data.slot_number} (${data.category})</strong>
      </div>
      <div style="display: flex; justify-content: space-between; margin-bottom: 0.35rem;">
        <span style="color: var(--text-muted);">Entry Time:</span>
        <span>${data.entry_time || 'N/A'}</span>
      </div>
      <div style="display: flex; justify-content: space-between; margin-bottom: 0.35rem;">
        <span style="color: var(--text-muted);">Parking Duration:</span>
        <strong style="color: var(--navy-primary);">${durationText}</strong>
      </div>
      <div style="display: flex; justify-content: space-between; margin-bottom: 0.35rem;">
        <span style="color: var(--text-muted);">Rate Breakdown:</span>
        <span>Base Rs. ${baseFee.toFixed(2)} + (Rs. ${hourlyRate.toFixed(2)}/hr × ${hoursBilled}h)</span>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.65rem; padding-top: 0.65rem; border-top: 1px solid var(--border-medium); font-size: 1.05rem;">
        <strong>Total Amount:</strong>
        <strong style="color: var(--teal-hover); font-size: 1.2rem;">Rs. ${totalFee.toFixed(2)}</strong>
      </div>
    </div>
  `;
}

function recalculateExitPreview() {
  if (!currentExitVehicleData) return;
  const simSelect = document.getElementById("simulatedMinutes");
  let val = simSelect ? simSelect.value : "";
  let override = val ? parseInt(val, 10) : null;
  renderBillPreview(currentExitVehicleData, override);
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
              borderWidth: 3,
              hoverOffset: 6
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
            cutout: "70%"
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
                borderRadius: 5
              },
              {
                label: "Available Slots",
                data: data.chart_data.category.available,
                backgroundColor: "#10b981",
                borderRadius: 5
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: {
                grid: { display: false },
                ticks: { font: { size: 11, weight: "600" } }
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
   6. CLIENT-SIDE SEARCH FOR TABLES
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
