/**
 * SmartPark — Professional Parking Management System
 * Theme: Midnight Navy (#061A33) & Vibrant Teal (#00CBB0)
 * 
 * Features:
 * 1. Live Clock & Timers
 * 2. Floating Toast Notifications (Stays in position, no layout jumps)
 * 3. In-Place Slot Reservation Toggling (AJAX, no scroll jump)
 * 4. Automatic Receipt PDF Download on Vehicle Exit (No popup/preview)
 * 5. Strict Input Formatting & Client-Side Validation
 * 6. Responsive Chart.js Visualizations (Midnight & Teal Palette)
 */

document.addEventListener("DOMContentLoaded", function () {
  initLiveClock();
  initFlashDismissal();
  initModals();
  initDurationTicker();
  initDashboardCharts();
  initReservationAjax();
  initExitBillSubmission();
  initInputFormatters();
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
   2. FLOATING TOAST NOTIFICATIONS (STAYS IN POSITION)
   ========================================================================== */
function showToast(message, type = "success") {
  let container = document.getElementById("toastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "toastContainer";
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;

  const icon = type === "success" ? "✓" : (type === "danger" ? "✕" : "ℹ");
  toast.innerHTML = `
    <div style="display: flex; align-items: center; gap: 0.6rem;">
      <span style="font-weight: 800; font-size: 1rem;">${icon}</span>
      <span>${message}</span>
    </div>
    <button type="button" style="background: none; border: none; color: inherit; cursor: pointer; font-size: 1.1rem; opacity: 0.6; line-height: 1;">&times;</button>
  `;

  const closeBtn = toast.querySelector("button");
  closeBtn.addEventListener("click", () => removeToast(toast));

  container.appendChild(toast);

  // Auto remove after 4.5 seconds
  setTimeout(() => removeToast(toast), 4500);
}

function removeToast(toast) {
  if (!toast || !toast.parentNode) return;
  toast.style.opacity = "0";
  toast.style.transform = "translateX(20px)";
  setTimeout(() => toast.remove(), 250);
}

/* ==========================================================================
   3. FLASH MESSAGE DISMISSAL
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
   4. MODAL CONTROLS
   ========================================================================== */
function initModals() {
  const closeBtns = document.querySelectorAll("[data-close-modal]");
  closeBtns.forEach(btn => {
    btn.addEventListener("click", function () {
      const modalId = btn.getAttribute("data-close-modal");
      closeModal(modalId);
    });
  });

  const modals = document.querySelectorAll(".modal-backdrop");
  modals.forEach(modal => {
    modal.addEventListener("click", function (e) {
      if (e.target === modal) {
        modal.classList.remove("show");
      }
    });
  });

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
      slotDisplay.textContent = `Target Slot Selected: ${slotNumber} (${category})`;
    }
    if (categorySelect && category) {
      categorySelect.value = category;
    }
  } else {
    if (slotInput) slotInput.value = "";
    if (slotDisplay) slotDisplay.style.display = "none";
  }

  modal.classList.add("show");
  const vehInput = modal.querySelector("#vehicleNumber");
  if (vehInput) setTimeout(() => vehInput.focus(), 150);
}

function openExitModal(vehicleNumber, slotNumber, category, entryTime) {
  const modal = document.getElementById("exitVehicleModal");
  if (!modal) return;

  const vehInput = modal.querySelector("#exitVehicleNumber");
  const vehDisplay = modal.querySelector("#exitVehDisplay");
  const simSelect = modal.querySelector("#simulatedMinutes");

  if (vehInput) vehInput.value = vehicleNumber;
  if (vehDisplay) vehDisplay.textContent = vehicleNumber;
  if (simSelect) simSelect.value = "";

  modal.classList.add("show");
}

/* ==========================================================================
   5. RESERVATION: STAY IN POSITION + UPDATE IN PLACE (REQUIREMENT 6)
   ========================================================================== */
function initReservationAjax() {
  document.addEventListener("submit", function (e) {
    const form = e.target.closest(".reserve-toggle-form");
    if (!form) return;

    e.preventDefault();

    const submitBtn = form.querySelector("button[type='submit']");
    if (submitBtn) submitBtn.disabled = true;

    // Capture current scroll position
    const currentScrollY = window.scrollY;

    fetch(form.action, {
      method: "POST",
      headers: {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest"
      }
    })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        updateSlotInPlace(data.slot_id, data.new_status, data.slot_number, data.category);
        showToast(data.message, "success");

        // Update toolbar legend numbers if present
        if (data.summary) {
          const availEl = document.getElementById("legendAvailableCount");
          const occEl = document.getElementById("legendOccupiedCount");
          const resEl = document.getElementById("legendReservedCount");
          if (availEl) availEl.textContent = data.summary.available_slots;
          if (occEl) occEl.textContent = data.summary.occupied_slots;
          if (resEl) resEl.textContent = data.summary.reserved_slots;
        }

        if (data.queue_allocation) {
          showToast(`Waiting vehicle ${data.queue_allocation.vehicle_number} allocated to Slot ${data.queue_allocation.slot_number}`, "info");
        }
      } else {
        showToast(data.message || "Failed to update reservation.", "danger");
      }
    })
    .catch(err => {
      console.error("Reservation AJAX error:", err);
      showToast("Network error updating reservation.", "danger");
    })
    .finally(() => {
      if (submitBtn) submitBtn.disabled = false;
      // Guarantee scroll position remains identical
      window.scrollTo(window.scrollX, currentScrollY);
    });
  });
}

function updateSlotInPlace(slotId, newStatus, slotNumber, category) {
  const slotCard = document.getElementById(`slot-card-${slotId}`);
  if (!slotCard) return;

  // 1. Update card classes
  slotCard.classList.remove("status-available", "status-reserved", "status-occupied");
  slotCard.classList.add(`status-${newStatus}`);
  slotCard.setAttribute("data-status", newStatus);

  const mainArea = slotCard.querySelector(".slot-main");
  const actionsArea = slotCard.querySelector(".slot-actions");

  if (newStatus === "reserved") {
    // Remove park modal click if previously available
    slotCard.onclick = null;

    if (mainArea) {
      mainArea.innerHTML = `
        <div class="slot-reserved-display">
          <div class="reserved-lock-icon">🔒</div>
          <div class="slot-reserved-text">RESERVED</div>
        </div>
        <div class="slot-hint-text">VIP / Priority Bay</div>
      `;
    }

    if (actionsArea) {
      actionsArea.innerHTML = `
        <form action="/slot/toggle-reserve/${slotId}" method="POST" class="reserve-toggle-form" data-slot-id="${slotId}" style="width: 100%;" onclick="event.stopPropagation();">
          <button type="submit" class="btn btn-secondary btn-sm reserve-btn" style="width: 100%;">Unreserve</button>
        </form>
      `;
    }
  } else if (newStatus === "available") {
    // Re-attach park modal click
    slotCard.onclick = function () {
      openParkModal(slotId, slotNumber, category);
    };

    if (mainArea) {
      mainArea.innerHTML = `
        <div class="slot-available-display">
          <div class="available-check-icon">✓</div>
          <div class="slot-available-text">AVAILABLE</div>
        </div>
        <div class="slot-hint-text">Click bay to park</div>
      `;
    }

    if (actionsArea) {
      actionsArea.innerHTML = `
        <form action="/slot/toggle-reserve/${slotId}" method="POST" class="reserve-toggle-form" data-slot-id="${slotId}" style="width: 100%;" onclick="event.stopPropagation();">
          <button type="submit" class="btn btn-secondary btn-sm reserve-btn" style="width: 100%;">Reserve</button>
        </form>
      `;
    }
  }
}

/* ==========================================================================
   6. VEHICLE EXIT & BILLING: AUTOMATIC PDF DOWNLOAD (REQUIREMENT 1)
   ========================================================================== */
function initExitBillSubmission() {
  const exitForm = document.getElementById("exitVehicleForm");
  if (!exitForm) return;

  exitForm.addEventListener("submit", function (e) {
    e.preventDefault();

    const submitBtn = document.getElementById("btnConfirmExit");
    const vehNumber = document.getElementById("exitVehicleNumber").value;

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = "<span>Processing &amp; Generating PDF...</span>";
    }

    const formData = new FormData(exitForm);

    fetch(exitForm.action, {
      method: "POST",
      body: formData
    })
    .then(response => {
      if (!response.ok) {
        throw new Error("Billing failed or vehicle not found.");
      }

      // Check for filename in header or default
      const disposition = response.headers.get("Content-Disposition");
      let filename = `SmartPark_Receipt_${vehNumber}.pdf`;
      if (disposition && disposition.indexOf("filename=") !== -1) {
        const matches = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (matches && matches[1]) {
          filename = matches[1].replace(/['"]/g, "");
        }
      }

      return response.blob().then(blob => ({ blob, filename }));
    })
    .then(({ blob, filename }) => {
      // Trigger instant browser download of the PDF
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();

      closeModal("exitVehicleModal");
      showToast(`Receipt downloaded! Vehicle ${vehNumber} exited successfully.`, "success");

      // Remove vehicle row from table smoothly if on Active Vehicles page
      const row = document.getElementById(`veh-row-${vehNumber}`);
      if (row) {
        row.style.transition = "all 0.3s ease";
        row.style.opacity = "0";
        row.style.transform = "translateX(-20px)";
        setTimeout(() => {
          row.remove();
          // Update active count badge if present
          const countBadge = document.getElementById("navOccupiedBadge");
          if (countBadge) {
            const currentCount = parseInt(countBadge.textContent, 10) || 1;
            countBadge.textContent = Math.max(0, currentCount - 1);
          }
        }, 300);
      } else {
        // If not on vehicles page or table needs full sync, soft reload after 800ms
        setTimeout(() => window.location.reload(), 800);
      }
    })
    .catch(err => {
      console.error("Exit & Billing Error:", err);
      showToast(err.message || "Could not complete vehicle exit.", "danger");
    })
    .finally(() => {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = "<span>Confirm and Bill (Download PDF)</span>";
      }
    });
  });
}

/* ==========================================================================
   7. STRICT INPUT FORMATTERS (REQUIREMENT 4)
   ========================================================================== */
function initInputFormatters() {
  // 1. Vehicle Registration: Uppercase letters A-Z and digits 0-9 only
  const vehInputs = document.querySelectorAll("input[name='vehicle_number']");
  vehInputs.forEach(input => {
    input.addEventListener("input", function () {
      this.value = this.value.toUpperCase().replace(/[^A-Z0-9]/g, "");
    });
  });

  // 2. Driver Contact: Exactly digits only, max 10 chars
  const contactInputs = document.querySelectorAll("input[name='driver_contact']");
  contactInputs.forEach(input => {
    input.addEventListener("input", function () {
      this.value = this.value.replace(/[^0-9]/g, "").slice(0, 10);
    });
  });
}

/* ==========================================================================
   8. LIVE DURATION TICKER FOR PARKED VEHICLES
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
   9. DASHBOARD CHARTS (MIDNIGHT NAVY & TEAL PALETTE)
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
              borderColor: "#0c284d",
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
                  color: "#cbd5e1",
                  font: { size: 12, family: "-apple-system, sans-serif" }
                }
              },
              tooltip: {
                callbacks: {
                  label: function (context) {
                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                    const val = context.raw || 0;
                    const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                    return ` ${context.label}: ${val} bays (${pct}%)`;
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
                label: "Occupied Bays",
                data: data.chart_data.category.occupied,
                backgroundColor: "#ef4444",
                borderRadius: 5
              },
              {
                label: "Available Bays",
                data: data.chart_data.category.available,
                backgroundColor: "#00CBB0",
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
                ticks: { color: "#94a3b8", font: { size: 11, weight: "700" } }
              },
              y: {
                beginAtZero: true,
                ticks: { stepSize: 2, color: "#94a3b8", font: { size: 11 } },
                grid: { color: "rgba(255, 255, 255, 0.06)" }
              }
            },
            plugins: {
              legend: {
                position: "bottom",
                labels: { boxWidth: 12, color: "#cbd5e1" }
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
   10. CLIENT-SIDE SEARCH FOR TABLES
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
      row.style.display = text.includes(query) ? "" : "none";
    });
  });
}
