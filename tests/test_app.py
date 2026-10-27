"""
tests/test_app.py
Flask web application integration tests for SmartPark.

Tests:
1. Dashboard route rendering
2. Parking map rendering with 30 slots
3. Active vehicles directory
4. Waiting list route
5. Vehicle park form submission
6. Vehicle exit & billing with empty string simulated_minutes (TypeError prevention)
7. Vehicle exit & billing receipt display
8. API endpoint /api/preview-bill/<vehicle>
9. API endpoint /api/stats for Chart.js
10. API endpoint /api/slots
11. Slot reservation toggling
"""

import unittest
import os
import tempfile
import json

from app import app
from database import init_db
from parking_manager import ParkingManager

class TestApp(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        init_db(self.temp_db_path, force_reset=True)
        
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

        # Connect app's global pm to our isolated test db
        import app as app_module
        app_module.pm = ParkingManager(self.temp_db_path)
        self.pm = app_module.pm

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_dashboard_route(self):
        """Test GET /dashboard returns HTTP 200 and loads clean summary cards."""
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("SmartPark", html)
        self.assertIn("Total Slots", html)
        self.assertIn("Available Slots", html)
        self.assertIn("Real-Time Capacity Breakdown", html)
        # Ensure removed irrelevant academic content is NOT present
        self.assertNotIn("Live DSA Performance Telemetry", html)
        self.assertNotIn("Linear Search: O(N)", html)

    def test_parking_map_route(self):
        """Test GET /map displays all 30 parking slots."""
        response = self.client.get("/map")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("S-01", html)
        self.assertIn("S-30", html)
        self.assertIn("Two-Wheeler", html)
        self.assertIn("Four-Wheeler", html)
        self.assertIn("EV Charging", html)

    def test_waiting_list_route(self):
        """Test GET /waiting-list returns HTTP 200."""
        response = self.client.get("/waiting-list")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("Customer Waiting List", html)

    def test_park_vehicle_post(self):
        """Test POST /park allocates slot and redirects."""
        response = self.client.post("/park", data={
            "vehicle_number": "KA-01-TEST-1",
            "category": "Four-Wheeler",
            "driver_contact": "9900112233"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("KA-01-TEST-1", html)
        self.assertIn("assigned to vehicle", html)
        self.assertIn("KA-01-TEST-1", self.pm.active_vehicles)

    def test_exit_vehicle_post_with_empty_simulated_minutes(self):
        """
        Critical Test: Test POST /exit with empty string simulated_minutes=""
        Verifies that NO TypeError is raised when the user clicks 'Confirm and Bill'
        without selecting a simulated duration.
        """
        # First park
        self.pm.park_vehicle("KA-02-EXIT-9", "Four-Wheeler")
        self.assertIn("KA-02-EXIT-9", self.pm.active_vehicles)

        # Exit with empty simulated_minutes="" (the default selection in UI)
        response = self.client.post("/exit", data={
            "vehicle_number": "KA-02-EXIT-9",
            "simulated_minutes": ""
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("successfully exited", html)
        self.assertNotIn("KA-02-EXIT-9", self.pm.active_vehicles)
        # Check receipt invoice is shown on page
        self.assertIn("SmartPark Parking Receipt", html)
        self.assertIn("PAID &amp; COMPLETED", html)

    def test_api_preview_bill(self):
        """Test GET /api/preview-bill/<veh> returns accurate live bill calculations."""
        self.pm.park_vehicle("KA-05-PREVIEW-1", "Four-Wheeler")
        response = self.client.get("/api/preview-bill/KA-05-PREVIEW-1")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["vehicle_number"], "KA-05-PREVIEW-1")
        self.assertEqual(data["category"], "Four-Wheeler")
        self.assertEqual(data["base_fee"], 20.0)
        self.assertEqual(data["hourly_rate"], 30.0)
        self.assertGreaterEqual(data["estimated_fee"], 50.0)

    def test_receipt_appears_only_on_vehicles_page(self):
        """
        Verify that the receipt appears ONLY on the Active Vehicles page where exit occurred,
        and does NOT appear on Dashboard, Map, Waiting List, or History.
        """
        self.pm.park_vehicle("KA-09-PAGE-TEST", "Four-Wheeler")
        
        # Exit vehicle -> redirected to /vehicles
        exit_resp = self.client.post("/exit", data={"vehicle_number": "KA-09-PAGE-TEST", "simulated_minutes": "30"}, follow_redirects=True)
        self.assertEqual(exit_resp.status_code, 200)
        vehicles_html = exit_resp.data.decode("utf-8")
        self.assertIn("SmartPark Parking Receipt", vehicles_html)
        self.assertIn("KA-09-PAGE-TEST", vehicles_html)

        # Navigating to Dashboard must NOT show the receipt
        dash_resp = self.client.get("/dashboard")
        dash_html = dash_resp.data.decode("utf-8")
        self.assertNotIn("SmartPark Parking Receipt", dash_html)

        # Navigating to Parking Map must NOT show the receipt
        map_resp = self.client.get("/map")
        map_html = map_resp.data.decode("utf-8")
        self.assertNotIn("SmartPark Parking Receipt", map_html)

        # Navigating to Waiting List must NOT show the receipt
        queue_resp = self.client.get("/waiting-list")
        queue_html = queue_resp.data.decode("utf-8")
        self.assertNotIn("SmartPark Parking Receipt", queue_html)

        # Navigating to History must NOT show the receipt
        hist_resp = self.client.get("/history")
        hist_html = hist_resp.data.decode("utf-8")
        self.assertNotIn("SmartPark Parking Receipt", hist_html)

        # Returning to Vehicles page must not resurrect the old receipt unexpectedly
        revisit_resp = self.client.get("/vehicles")
        revisit_html = revisit_resp.data.decode("utf-8")
        self.assertNotIn("SmartPark Parking Receipt", revisit_html)

    def test_receipt_dismissal_preserves_history(self):
        """Verify dismissing the receipt removes it without deleting completed history."""
        self.pm.park_vehicle("KA-09-DISMISS", "Two-Wheeler")
        exit_resp = self.client.post("/exit", data={"vehicle_number": "KA-09-DISMISS", "simulated_minutes": "30"}, follow_redirects=True)
        self.assertIn("SmartPark Parking Receipt", exit_resp.data.decode("utf-8"))

        # Dismiss via /clear-bill
        dismiss_resp = self.client.post("/clear-bill", follow_redirects=True)
        self.assertEqual(dismiss_resp.status_code, 200)
        self.assertNotIn("SmartPark Parking Receipt", dismiss_resp.data.decode("utf-8"))

        # Verify history is still saved exactly once
        history = self.pm.get_parking_history()
        matching = [r for r in history if r["vehicle_number"] == "KA-09-DISMISS"]
        self.assertEqual(len(matching), 1)

    def test_api_stats_json(self):
        """Test GET /api/stats returns valid JSON data structure for Chart.js."""
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode("utf-8"))
        self.assertIn("summary", data)
        self.assertIn("chart_data", data)
        self.assertEqual(data["summary"]["total_slots"], 30)
        self.assertIn("occupancy", data["chart_data"])
        self.assertIn("category", data["chart_data"])

    def test_api_slots_json(self):
        """Test GET /api/slots returns 30 slots."""
        response = self.client.get("/api/slots")
        self.assertEqual(response.status_code, 200)
        slots = json.loads(response.data.decode("utf-8"))
        self.assertEqual(len(slots), 30)
        self.assertEqual(slots[0]["slot_number"], "S-01")

    def test_slot_reservation_toggle(self):
        """Test toggling reservation on slot."""
        slot_27 = next(s for s in self.pm.slots if s.slot_number == "S-27")
        orig_status = slot_27.status

        response = self.client.post(f"/slot/toggle-reserve/{slot_27.id}", follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # Check in pm
        updated_slot = next(s for s in self.pm.slots if s.id == slot_27.id)
        expected = "reserved" if orig_status == "available" else "available"
        self.assertEqual(updated_slot.status, expected)

if __name__ == '__main__':
    unittest.main()
