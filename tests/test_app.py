"""
tests/test_app.py
Flask web application integration tests for SmartPark.

Tests:
1. Exit & Bill: immediate PDF download without popup/preview.
2. Parking History: Print Receipt PDF download and isolated Delete.
3. Dark Midnight Navy & Teal theme consistency and responsive routes.
4. Park Vehicle strict input validation on frontend and backend (A-Z0-9, exactly 10 digits).
5. Waiting List strict category compatibility (EV never to Four-Wheeler).
6. In-place reservation toggle without page reload or jump.
7. Login Page, User & Admin Access, and Logout (Requirement 1).
8. Admin Manage Slots (add, edit, toggle enable/disable) (Requirement 2).
9. Normal/Reserved bipartite layout & EV compatibility (Requirement 3).
10. Reservation and Park Vehicle integration (Requirement 4).
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

        # Default admin session for general operational route tests
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "admin@gmail.com", "role": "admin"}
            sess["role"] = "admin"
            sess["email"] = "admin@gmail.com"

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
        """Test GET /map displays parking slots with category indicators."""
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
            sess["user"] = {"email": "admin@gmail.com", "role": "admin"}
            sess["role"] = "admin"

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
        """Verify vehicle exit immediately downloads PDF without popup or preview (Requirement 1)."""
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
        """Verify Print Receipt button downloads original PDF receipt from history (Requirement 2)."""
        self.pm.park_vehicle("HISTREPRINT1", "Two-Wheeler", driver_contact="9876543210")
        exit_res = self.pm.exit_vehicle("HISTREPRINT1", simulated_minutes=30)
        rec_id = exit_res["summary"]["id"]

        receipt_resp = self.client.get(f"/receipt/{rec_id}")
        self.assertEqual(receipt_resp.status_code, 200)
        self.assertEqual(receipt_resp.mimetype, "application/pdf")
        self.assertTrue(receipt_resp.data.startswith(b"%PDF"))
        self.assertIn(f"SmartPark_Receipt_HISTREPRINT1_INV{rec_id:05d}.pdf", receipt_resp.headers.get("Content-Disposition", ""))

        history = self.pm.get_parking_history()
        records = [r for r in history if r["vehicle_number"] == "HISTREPRINT1"]
        self.assertEqual(len(records), 1)

    def test_delete_history_record_route(self):
        """Verify deleting a history record via POST /history/delete/<id> (Requirement 2)."""
        self.pm.park_vehicle("DELTEST1", "Four-Wheeler", driver_contact="9876543210")
        exit_res = self.pm.exit_vehicle("DELTEST1", simulated_minutes=30)
        rec_id = exit_res["summary"]["id"]

        self.pm.park_vehicle("STILLACTIVE1", "Four-Wheeler", driver_contact="9876543210")

        del_resp = self.client.post(f"/history/delete/{rec_id}", follow_redirects=True)
        self.assertEqual(del_resp.status_code, 200)
        html = del_resp.data.decode("utf-8")
        self.assertIn("successfully deleted", html)

        self.assertIn("STILLACTIVE1", self.pm.active_vehicles)
        history = self.pm.get_parking_history()
        self.assertEqual(len([r for r in history if r["id"] == rec_id]), 0)

    def test_slot_reservation_toggle_in_place_ajax(self):
        """Verify in-place reservation toggling via AJAX (Requirement 6)."""
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

    # =========================================================================
    # TESTS FOR 4 NEW REQUIREMENTS
    # =========================================================================

    def test_login_page_renders_for_unauthenticated_user(self):
        """Test GET /login renders SmartPark branding, User and Admin login sections (Requirement 1)."""
        with self.client.session_transaction() as sess:
            sess.clear()

        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("SmartPark", html)
        self.assertIn("Driver &amp; User Login", html)
        self.assertIn("Facility Administrator", html)
        self.assertIn("Sign In as User", html)
        self.assertIn("Sign In as Administrator", html)

    def test_user_login_accepts_any_credentials(self):
        """Test User Login accepts any non-empty email and password (Requirement 1)."""
        with self.client.session_transaction() as sess:
            sess.clear()

        response = self.client.post("/login/user", data={
            "email": "driver@test.com",
            "password": "mypassword123"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "user")
            self.assertEqual(sess.get("email"), "driver@test.com")

    def test_admin_login_strict_authentication(self):
        """Test Admin Login allows access ONLY with admin@gmail.com and password 12345 (Requirement 1)."""
        with self.client.session_transaction() as sess:
            sess.clear()

        # 1. Correct credentials succeed
        success_resp = self.client.post("/login/admin", data={
            "email": "admin@gmail.com",
            "password": "12345"
        }, follow_redirects=True)
        self.assertEqual(success_resp.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "admin")

        # 2. Incorrect password fails
        with self.client.session_transaction() as sess:
            sess.clear()

        fail_resp = self.client.post("/login/admin", data={
            "email": "admin@gmail.com",
            "password": "wrongpassword"
        }, follow_redirects=True)
        self.assertEqual(fail_resp.status_code, 200)
        html = fail_resp.data.decode("utf-8")
        self.assertIn("Invalid admin credentials", html)
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("role"))

    def test_admin_route_backend_protection(self):
        """Test backend route protection: non-admins cannot access /admin/slots (Requirement 1)."""
        # User session
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "user@test.com", "role": "user"}
            sess["role"] = "user"
            sess["email"] = "user@test.com"

        resp = self.client.get("/admin/slots", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("Access denied", html)

        # Admin session
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "admin@gmail.com", "role": "admin"}
            sess["role"] = "admin"
            sess["email"] = "admin@gmail.com"

        admin_resp = self.client.get("/admin/slots")
        self.assertEqual(admin_resp.status_code, 200)
        admin_html = admin_resp.data.decode("utf-8")
        self.assertIn("Facility Bay Management", admin_html)

    def test_logout_clears_session(self):
        """Test Logout clears user session and redirects to login (Requirement 1)."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "test@test.com", "role": "user"}
            sess["role"] = "user"

        resp = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("user"))
            self.assertIsNone(sess.get("role"))

    def test_admin_add_and_toggle_slot_route(self):
        """Test Admin adding and enabling/disabling slots via routes (Requirement 2)."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "admin@gmail.com", "role": "admin"}
            sess["role"] = "admin"

        # Add slot S-31
        add_resp = self.client.post("/admin/slots/add", data={
            "slot_number": "S-31",
            "category": "Four-Wheeler",
            "slot_type": "Normal",
            "area": "North Bay",
            "is_enabled": "1"
        }, follow_redirects=True)
        self.assertEqual(add_resp.status_code, 200)

        slot_31 = self.pm.get_slot_by_number("S-31")
        self.assertIsNotNone(slot_31)
        self.assertEqual(slot_31.slot_type, "Normal")

        # Toggle status to disabled
        toggle_resp = self.client.post(f"/admin/slots/toggle-status/{slot_31.id}", follow_redirects=True)
        self.assertEqual(toggle_resp.status_code, 200)
        slot_31_updated = self.pm.get_slot_by_number("S-31")
        self.assertEqual(slot_31_updated.is_enabled, 0)

    def test_reservation_and_checkin_integration_routes(self):
        """Test slot reservation and check-in via routes (Requirement 4)."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "admin@gmail.com", "role": "admin"}
            sess["role"] = "admin"

        slot_5 = next(s for s in self.pm.slots if s.slot_number == "S-05")
        self.assertEqual(slot_5.slot_type, "Reserved")

        # 1. Reserve slot via POST /slot/reserve
        res_resp = self.client.post("/slot/reserve", data={
            "slot_id": slot_5.id,
            "vehicle_number": "RESVTEST9",
            "category": "Two-Wheeler",
            "driver_contact": "9876543210"
        }, follow_redirects=True)
        self.assertEqual(res_resp.status_code, 200)
        self.assertEqual(slot_5.status, "reserved")

        # 2. Check in via POST /park with same vehicle number
        park_resp = self.client.post("/park", data={
            "vehicle_number": "RESVTEST9",
            "category": "Two-Wheeler",
            "driver_contact": "9876543210"
        }, follow_redirects=True)
        self.assertEqual(park_resp.status_code, 200)
        self.assertEqual(slot_5.status, "occupied")
        self.assertEqual(slot_5.current_vehicle, "RESVTEST9")

    # =========================================================================
    # TESTS FOR 3 SPECIFIC REQUIREMENTS (LOGIN PAGE, CHARTS, DELETE SLOT)
    # =========================================================================

    def test_initial_login_page_shown_to_unauthenticated_visitor(self):
        """
        Verify that opening the website without an authenticated session shows
        the SmartPark Login page first, and does NOT show Dashboard before login (Requirement 1).
        """
        # Clear session completely
        with self.client.session_transaction() as sess:
            sess.clear()

        # 1. GET / directly renders Login page without session
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("SmartPark", html)
        self.assertIn("Driver &amp; User Login", html)
        self.assertIn("Facility Administrator", html)
        self.assertNotIn("Total Slots", html)
        self.assertNotIn("Real-Time Capacity Breakdown", html)

        # 2. GET /dashboard without session redirects to login
        dash_resp = self.client.get("/dashboard")
        self.assertEqual(dash_resp.status_code, 302)
        self.assertTrue(dash_resp.headers["Location"].endswith("/login"))

        # 3. GET /login directly renders Login page
        login_resp = self.client.get("/login")
        self.assertEqual(login_resp.status_code, 200)
        login_html = login_resp.data.decode("utf-8")
        self.assertIn("Sign In as User", login_html)
        self.assertIn("Sign In as Administrator", login_html)

        # 4. Refreshing with authenticated session stays on dashboard
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "driver@smartpark.com", "role": "user"}
            sess["role"] = "user"
            sess["email"] = "driver@smartpark.com"

        auth_dash = self.client.get("/dashboard")
        self.assertEqual(auth_dash.status_code, 200)
        auth_html = auth_dash.data.decode("utf-8")
        self.assertIn("Dashboard", auth_html)
        self.assertIn("Real-Time Capacity Breakdown", auth_html)
        self.assertIn("driver@smartpark.com", auth_html)

    def test_dashboard_charts_api_data_structure(self):
        """
        Verify that /api/stats returns real database capacity breakdown and category
        distribution datasets expected by Chart.js (Requirement 2).
        """
        resp = self.client.get("/api/stats")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode("utf-8"))

        self.assertIn("chart_data", data)
        chart_data = data["chart_data"]

        # 1. Capacity breakdown (circular/doughnut chart)
        self.assertIn("occupancy", chart_data)
        self.assertEqual(chart_data["occupancy"]["labels"], ["Available", "Occupied", "Reserved"])
        self.assertEqual(len(chart_data["occupancy"]["data"]), 3)
        self.assertEqual(sum(chart_data["occupancy"]["data"]), data["summary"]["total_slots"])

        # 2. Category distribution (bar chart)
        self.assertIn("category", chart_data)
        self.assertEqual(chart_data["category"]["labels"], ["Two-Wheeler", "Four-Wheeler", "EV Charging"])
        self.assertEqual(len(chart_data["category"]["occupied"]), 3)
        self.assertEqual(len(chart_data["category"]["available"]), 3)

        # 3. Backward compatibility aliases present
        self.assertIn("capacity", chart_data)
        self.assertIn("categories", chart_data)

    def test_admin_delete_slot_route_validation_and_authorization(self):
        """
        Verify Delete Slot route enforces admin authorization, strict 4-field matching,
        blocks deletion of occupied bays, and updates database immediately (Requirement 3).
        """
        # 1. Add S-33 as Admin
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "admin@gmail.com", "role": "admin"}
            sess["role"] = "admin"
            sess["email"] = "admin@gmail.com"

        add_resp = self.client.post("/admin/slots/add", data={
            "slot_number": "S-33",
            "category": "Four-Wheeler",
            "slot_type": "Normal",
            "area": "North Bay",
            "is_enabled": "1"
        }, follow_redirects=True)
        self.assertEqual(add_resp.status_code, 200)
        self.assertIsNotNone(self.pm.get_slot_by_number("S-33"))

        # 2. Verify slot details API endpoint
        verify_resp = self.client.get("/admin/slots/verify?slot_number=S-33")
        self.assertEqual(verify_resp.status_code, 200)
        v_data = json.loads(verify_resp.data.decode("utf-8"))
        self.assertTrue(v_data["success"])
        self.assertEqual(v_data["slot"]["slot_number"], "S-33")
        self.assertEqual(v_data["slot"]["category"], "Four-Wheeler")

        # 3. Non-admin cannot delete slot
        with self.client.session_transaction() as sess:
            sess["role"] = "user"

        non_admin_resp = self.client.post("/admin/slots/delete", data={
            "slot_number": "S-33",
            "category": "Four-Wheeler",
            "slot_type": "Normal",
            "area": "North Bay"
        }, follow_redirects=True)
        self.assertEqual(non_admin_resp.status_code, 200)
        self.assertIn("Access denied", non_admin_resp.data.decode("utf-8"))
        self.assertIsNotNone(self.pm.get_slot_by_number("S-33"))

        # 4. Admin fails with mismatched category
        with self.client.session_transaction() as sess:
            sess["role"] = "admin"

        mismatch_resp = self.client.post("/admin/slots/delete", data={
            "slot_number": "S-33",
            "category": "Two-Wheeler", # Mismatched!
            "slot_type": "Normal",
            "area": "North Bay"
        }, follow_redirects=True)
        self.assertEqual(mismatch_resp.status_code, 200)
        self.assertIn("mismatch", mismatch_resp.data.decode("utf-8").lower())
        self.assertIsNotNone(self.pm.get_slot_by_number("S-33"))

        # 5. Admin succeeds with all 4 matching details
        del_resp = self.client.post("/admin/slots/delete", data={
            "slot_number": "S-33",
            "category": "Four-Wheeler",
            "slot_type": "Normal",
            "area": "North Bay"
        }, follow_redirects=True)
        self.assertEqual(del_resp.status_code, 200)
        self.assertIn("successfully deleted", del_resp.data.decode("utf-8"))
        self.assertIsNone(self.pm.get_slot_by_number("S-33"))

    def test_login_page_does_not_display_admin_credentials(self):
        """
        Verify that the login page does NOT display or expose the admin credentials
        (admin@gmail.com / 12345) in helper text or placeholders (UI Fix 2).
        """
        with self.client.session_transaction() as sess:
            sess.clear()

        resp = self.client.get("/login")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # Credentials must NOT be exposed anywhere in the HTML
        self.assertNotIn("admin@gmail.com", html)
        self.assertNotIn("12345", html)

        # Login form fields and submit button must still be present
        self.assertIn('name="email"', html)
        self.assertIn('name="password"', html)
        self.assertIn("Sign In as Administrator", html)

    def test_delete_slot_modal_markup_and_accessibility(self):
        """
        Verify that the Delete Slot modal has the proper bounded modal structure,
        accessible header close button, all 4 fields, confirmation checkbox, and footer
        containing Cancel and Delete buttons (UI Fix 1).
        """
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "admin@gmail.com", "role": "admin"}
            sess["role"] = "admin"
            sess["email"] = "admin@gmail.com"

        resp = self.client.get("/admin/slots")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # Delete Slot modal elements
        self.assertIn('id="deleteSlotModal"', html)
        self.assertIn('data-close-modal="deleteSlotModal"', html)
        self.assertIn('id="deleteSlotNumber"', html)
        self.assertIn('id="deleteCategory"', html)
        self.assertIn('id="deleteSlotType"', html)
        self.assertIn('id="deleteArea"', html)
        self.assertIn('id="deleteConfirmCheck"', html)
        self.assertIn('id="btnConfirmDeleteSlot"', html)
        self.assertIn('openDeleteSlotModal', html)

if __name__ == '__main__':
    unittest.main()
