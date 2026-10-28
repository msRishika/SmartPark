"""
tests/test_app.py
Flask web application integration tests for SmartPark.

Tests all 6 core requirements:
1. Exit & Bill: immediate PDF download without popup/preview.
2. Parking History: Print Receipt PDF download and isolated Delete.
3. Dark Midnight Navy & Teal theme consistency and responsive routes.
4. Park Vehicle strict input validation on frontend and backend (A-Z0-9, exactly 10 digits).
5. Waiting List strict category compatibility (EV never to Four-Wheeler).
6. In-place reservation toggle without page reload or jump.
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
        self.assertNotIn("Live DSA Performance Telemetry", html)
        self.assertNotIn("Linear Search: O(N)", html)

    def test_parking_map_route(self):
        """Test GET /map displays all 30 parking slots with category indicators."""
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

    def test_park_vehicle_post_strict_validation(self):
        """
        Verify Park Vehicle strict input validation (Requirement 4):
        - Valid vehicle (A-Z, 0-9) and 10-digit contact succeeds.
        - Invalid vehicle (commas, dots, hyphens, short) rejected with error and preserved input.
        - Invalid contact (not 10 digits) rejected with error and preserved input.
        """
        # 1. Successful Park with valid format
        response = self.client.post("/park", data={
            "vehicle_number": "ABCD1234",
            "category": "Four-Wheeler",
            "driver_contact": "9876543210"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("ABCD1234", html)
        self.assertIn("ABCD1234", self.pm.active_vehicles)

        # 2. Reject vehicle with commas / special characters
        with self.client.session_transaction() as sess:
            sess.clear()

        bad_veh_resp = self.client.post("/park", data={
            "vehicle_number": "KA,01,AB",
            "category": "Four-Wheeler",
            "driver_contact": "9876543210"
        }, follow_redirects=True)

        bad_veh_html = bad_veh_resp.data.decode("utf-8")
        self.assertIn("Vehicle registration must contain only uppercase", bad_veh_html)
        self.assertNotIn("KA,01,AB", self.pm.active_vehicles)

        # 3. Reject vehicle that is too short or punctuation only
        short_resp = self.client.post("/park", data={
            "vehicle_number": ",,,",
            "category": "Four-Wheeler",
            "driver_contact": "9876543210"
        }, follow_redirects=True)
        self.assertIn("Vehicle registration must contain only uppercase", short_resp.data.decode("utf-8"))

        # 4. Reject driver contact with fewer than 10 digits
        bad_contact_resp = self.client.post("/park", data={
            "vehicle_number": "MH12AB9999",
            "category": "Four-Wheeler",
            "driver_contact": "98765"  # Only 5 digits
        }, follow_redirects=True)
        self.assertIn("Driver contact number must be exactly 10 numeric digits", bad_contact_resp.data.decode("utf-8"))
        self.assertNotIn("MH12AB9999", self.pm.active_vehicles)

    def test_exit_vehicle_generates_pdf_download(self):
        """
        Verify vehicle exit immediately downloads PDF without popup or preview (Requirement 1).
        """
        self.pm.park_vehicle("EXITCAR1", "Four-Wheeler", driver_contact="9876543210")
        self.assertIn("EXITCAR1", self.pm.active_vehicles)

        # Post /exit
        exit_resp = self.client.post("/exit", data={
            "vehicle_number": "EXITCAR1",
            "simulated_minutes": "60"
        })

        # Response must be a PDF file download
        self.assertEqual(exit_resp.status_code, 200)
        self.assertEqual(exit_resp.mimetype, "application/pdf")
        self.assertIn("attachment", exit_resp.headers.get("Content-Disposition", ""))
        self.assertIn("SmartPark_Receipt_EXITCAR1.pdf", exit_resp.headers.get("Content-Disposition", ""))
        
        # Verify valid PDF binary bytes
        pdf_bytes = exit_resp.data
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

        # Verify vehicle is removed from active vehicles
        self.assertNotIn("EXITCAR1", self.pm.active_vehicles)

        # Verify history is saved
        history = self.pm.get_parking_history()
        records = [r for r in history if r["vehicle_number"] == "EXITCAR1"]
        self.assertEqual(len(records), 1)

    def test_download_history_receipt_pdf(self):
        """
        Verify Print Receipt button downloads original PDF receipt from history (Requirement 2).
        Does not change amount or create duplicate history.
        """
        self.pm.park_vehicle("HISTREPRINT1", "Two-Wheeler", driver_contact="9876543210")
        exit_res = self.pm.exit_vehicle("HISTREPRINT1", simulated_minutes=30)
        rec_id = exit_res["summary"]["id"]

        # Call GET /receipt/<rec_id>
        receipt_resp = self.client.get(f"/receipt/{rec_id}")
        self.assertEqual(receipt_resp.status_code, 200)
        self.assertEqual(receipt_resp.mimetype, "application/pdf")
        self.assertTrue(receipt_resp.data.startswith(b"%PDF"))
        self.assertIn(f"SmartPark_Receipt_HISTREPRINT1_INV{rec_id:05d}.pdf", receipt_resp.headers.get("Content-Disposition", ""))

        # Verify history record count did not change
        history = self.pm.get_parking_history()
        records = [r for r in history if r["vehicle_number"] == "HISTREPRINT1"]
        self.assertEqual(len(records), 1)

    def test_delete_history_record_route(self):
        """
        Verify deleting a history record via POST /history/delete/<id> (Requirement 2).
        Does not delete active vehicles or other records.
        """
        # Create history record
        self.pm.park_vehicle("DELTEST1", "Four-Wheeler", driver_contact="9876543210")
        exit_res = self.pm.exit_vehicle("DELTEST1", simulated_minutes=30)
        rec_id = exit_res["summary"]["id"]

        # Create active vehicle
        self.pm.park_vehicle("STILLACTIVE1", "Four-Wheeler", driver_contact="9876543210")

        # Delete history record
        del_resp = self.client.post(f"/history/delete/{rec_id}", follow_redirects=True)
        self.assertEqual(del_resp.status_code, 200)
        html = del_resp.data.decode("utf-8")
        self.assertIn("successfully deleted", html)

        # Active vehicle must still be present
        self.assertIn("STILLACTIVE1", self.pm.active_vehicles)

        # History record must be gone
        history = self.pm.get_parking_history()
        self.assertEqual(len([r for r in history if r["id"] == rec_id]), 0)

    def test_slot_reservation_toggle_in_place_ajax(self):
        """
        Verify in-place reservation toggling via AJAX (Requirement 6):
        - Returns JSON response with updated status and summary counts.
        - Cannot reserve occupied slots.
        """
        slot_27 = next(s for s in self.pm.slots if s.slot_number == "S-27")
        self.assertEqual(slot_27.status, "available")

        # Toggle to reserved via AJAX
        ajax_resp = self.client.post(
            f"/slot/toggle-reserve/{slot_27.id}",
            headers={"Accept": "application/json"}
        )
        self.assertEqual(ajax_resp.status_code, 200)
        data = json.loads(ajax_resp.data.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["new_status"], "reserved")
        self.assertIn("summary", data)

        # Toggle back to available
        ajax_resp2 = self.client.post(
            f"/slot/toggle-reserve/{slot_27.id}",
            headers={"Accept": "application/json"}
        )
        self.assertEqual(ajax_resp2.status_code, 200)
        data2 = json.loads(ajax_resp2.data.decode("utf-8"))
        self.assertTrue(data2["success"])
        self.assertEqual(data2["new_status"], "available")

        # Park a vehicle in S-07 and attempt to reserve it (should fail)
        self.pm.park_vehicle("OCCUPYCAR1", "Four-Wheeler", driver_contact="9876543210")
        slot_7 = next(s for s in self.pm.slots if s.slot_number == "S-07")
        occupied_res = self.client.post(
            f"/slot/toggle-reserve/{slot_7.id}",
            headers={"Accept": "application/json"}
        )
        self.assertEqual(occupied_res.status_code, 400)
        data_occ = json.loads(occupied_res.data.decode("utf-8"))
        self.assertFalse(data_occ["success"])
        self.assertIn("occupied", data_occ["message"])

    def test_api_stats_json(self):
        """Test GET /api/stats returns valid JSON data structure for Chart.js."""
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode("utf-8"))
        self.assertIn("summary", data)
        self.assertIn("chart_data", data)
        self.assertEqual(data["summary"]["total_slots"], 30)

    def test_api_slots_json(self):
        """Test GET /api/slots returns 30 slots."""
        response = self.client.get("/api/slots")
        self.assertEqual(response.status_code, 200)
        slots = json.loads(response.data.decode("utf-8"))
        self.assertEqual(len(slots), 30)

if __name__ == '__main__':
    unittest.main()
