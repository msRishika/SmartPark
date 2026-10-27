"""
tests/test_app.py
Flask web application integration tests for SmartPark.

Tests:
1. Dashboard page loading and KPI rendering
2. Parking map rendering with 30 slots
3. Active vehicles directory
4. Vehicle park form submission
5. Vehicle exit form submission & fee billing
6. API endpoint /api/stats for Chart.js
7. API endpoint /api/slots
8. Slot reservation toggling
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
        """Test GET /dashboard returns HTTP 200 and loads key elements."""
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("SmartPark", html)
        self.assertIn("Total Slots", html)
        self.assertIn("Available Slots", html)
        self.assertIn("Live DSA Performance Telemetry", html)

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
        self.assertIn("allocated to vehicle", html)
        self.assertIn("KA-01-TEST-1", self.pm.active_vehicles)

    def test_exit_vehicle_post(self):
        """Test POST /exit frees slot and calculates billing."""
        # First park
        self.pm.park_vehicle("KA-02-EXIT-9", "Four-Wheeler")
        self.assertIn("KA-02-EXIT-9", self.pm.active_vehicles)

        # Now exit with 60 simulated minutes
        response = self.client.post("/exit", data={
            "vehicle_number": "KA-02-EXIT-9",
            "simulated_minutes": "60"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("exited Slot", html)
        self.assertNotIn("KA-02-EXIT-9", self.pm.active_vehicles)

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
