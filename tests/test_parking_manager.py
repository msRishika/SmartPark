"""
tests/test_parking_manager.py
Unit tests for the Core DSA Engine of SmartPark.

Tests:
1. Slot allocation via Linear Search
2. Full parking scenario & FIFO Queue enqueuing
3. FIFO queue ordering (collections.deque)
4. Duplicate vehicle rejection via Hashing (dict)
5. Vehicle exit, fee calculation, and history archiving
6. Automatic FIFO queue dispatch upon slot release
7. Custom Merge Sort and Quick Sort correctness
8. SQLite data persistence across manager reloads
"""

import unittest
import os
import tempfile
from collections import deque

from database import init_db
from parking_manager import ParkingManager, Slot

class TestParkingManagerDSA(unittest.TestCase):
    def setUp(self):
        # Create a temporary SQLite database for each test to ensure isolation
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        init_db(self.temp_db_path, force_reset=True)
        self.pm = ParkingManager(self.temp_db_path)

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_initial_slot_setup(self):
        """Verify that exactly 30 slots are initialized with correct categories."""
        self.assertEqual(len(self.pm.slots), 30)
        
        # 6 Two-Wheeler slots (S-01 to S-06)
        two_wheelers = [s for s in self.pm.slots if s.category == "Two-Wheeler"]
        self.assertEqual(len(two_wheelers), 6)

        # 16 Four-Wheeler slots (S-07 to S-22)
        four_wheelers = [s for s in self.pm.slots if s.category == "Four-Wheeler"]
        self.assertEqual(len(four_wheelers), 16)

        # 4 EV Charging slots (S-23 to S-26)
        ev_slots = [s for s in self.pm.slots if s.category == "EV Charging"]
        self.assertEqual(len(ev_slots), 4)

        # 4 Reserved slots (S-27 to S-30)
        reserved_slots = [s for s in self.pm.slots if s.category == "Reserved"]
        self.assertEqual(len(reserved_slots), 4)

    def test_linear_search_slot_allocation(self):
        """Test that first available eligible slot is allocated sequentially via linear search."""
        # First vehicle should get S-07 (first Four-Wheeler slot)
        res1 = self.pm.park_vehicle("KA-01-AA-1001", "Four-Wheeler")
        self.assertTrue(res1["success"])
        self.assertEqual(res1["slot_number"], "S-07")

        # Second vehicle should get S-08 (sequential linear search progression)
        res2 = self.pm.park_vehicle("KA-01-AA-1002", "Four-Wheeler")
        self.assertTrue(res2["success"])
        self.assertEqual(res2["slot_number"], "S-08")

        # Two-Wheeler should get S-01
        res_bike = self.pm.park_vehicle("KA-01-BIKE-1", "Two-Wheeler")
        self.assertTrue(res_bike["success"])
        self.assertEqual(res_bike["slot_number"], "S-01")

        # Check search metrics tracking
        self.assertEqual(self.pm.last_search_metrics["algorithm"], "Linear Search")
        self.assertGreater(self.pm.last_search_metrics["probes_count"], 0)

    def test_duplicate_vehicle_rejection_via_hashing(self):
        """Verify that duplicate vehicles are rejected in O(1) via hash map lookup."""
        self.pm.park_vehicle("KA-05-DUP-1111", "Four-Wheeler")
        
        # Verify it exists in the active_vehicles dictionary (O(1))
        self.assertIn("KA-05-DUP-1111", self.pm.active_vehicles)

        # Attempt to park the same vehicle registration number again
        duplicate_res = self.pm.park_vehicle("KA-05-DUP-1111", "Four-Wheeler")
        self.assertFalse(duplicate_res["success"])
        self.assertIn("Duplicate vehicle", duplicate_res["message"])

        # Also case-insensitive check (e.g. lowercase)
        dup_case = self.pm.park_vehicle("ka-05-dup-1111", "Four-Wheeler")
        self.assertFalse(dup_case["success"])

    def test_full_parking_and_fifo_waiting_queue(self):
        """Verify that when slots are full, vehicles are queued into collections.deque in FIFO order."""
        # Fill all 6 Two-Wheeler slots (S-01 to S-06)
        for i in range(1, 7):
            res = self.pm.park_vehicle(f"BIKE-{i}", "Two-Wheeler")
            self.assertTrue(res["success"])
            self.assertEqual(res["status"], "allocated")

        # 7th Two-Wheeler: Parking is full for Two-Wheelers -> Enqueue into FIFO Queue
        q1 = self.pm.park_vehicle("BIKE-QUEUE-1", "Two-Wheeler")
        self.assertTrue(q1["success"])
        self.assertEqual(q1["status"], "queued")
        self.assertEqual(q1["queue_position"], 1)

        # 8th Two-Wheeler -> Position 2
        q2 = self.pm.park_vehicle("BIKE-QUEUE-2", "Two-Wheeler")
        self.assertTrue(q2["success"])
        self.assertEqual(q2["status"], "queued")
        self.assertEqual(q2["queue_position"], 2)

        # Verify collections.deque structure & order
        self.assertEqual(len(self.pm.waiting_queue), 2)
        self.assertEqual(self.pm.waiting_queue[0]["vehicle_number"], "BIKE-QUEUE-1")
        self.assertEqual(self.pm.waiting_queue[1]["vehicle_number"], "BIKE-QUEUE-2")

    def test_vehicle_exit_and_fee_calculation(self):
        """Test vehicle exit, slot freeing, fee calculation, and history entry."""
        self.pm.park_vehicle("KA-03-EX-1234", "Four-Wheeler")
        
        # Simulate exit with 120 minutes (2 hours)
        # Four-Wheeler rate: Base Rs. 20 + Rs. 30/hr * 2 hrs = Rs. 80.00
        exit_res = self.pm.exit_vehicle("KA-03-EX-1234", simulated_minutes=120)
        self.assertTrue(exit_res["success"])
        self.assertEqual(exit_res["summary"]["duration_minutes"], 120)
        self.assertEqual(exit_res["summary"]["fee"], 80.0)
        self.assertEqual(exit_res["summary"]["base_fee"], 20.0)
        self.assertEqual(exit_res["summary"]["hourly_rate"], 30.0)
        self.assertEqual(exit_res["summary"]["hours_billed"], 2)

        # Check vehicle is removed from active_vehicles dict (O(1))
        self.assertNotIn("KA-03-EX-1234", self.pm.active_vehicles)

        # Check parking history contains record
        history = self.pm.get_parking_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["vehicle_number"], "KA-03-EX-1234")
        self.assertEqual(history[0]["duration_minutes"], 120)
        self.assertEqual(history[0]["fee"], 80.0)

    def test_vehicle_exit_defensive_against_type_error(self):
        """Verify exit_vehicle handles empty string, string integers, and None without TypeError."""
        self.pm.park_vehicle("DEF-CAR-1", "Four-Wheeler")
        
        # Test simulated_minutes as empty string "" (the exact bug triggering TypeError)
        res_empty = self.pm.exit_vehicle("DEF-CAR-1", simulated_minutes="")
        self.assertTrue(res_empty["success"])
        self.assertIn("summary", res_empty)

        # Test simulated_minutes as string integer "45"
        self.pm.park_vehicle("DEF-CAR-2", "Two-Wheeler")
        res_str = self.pm.exit_vehicle("DEF-CAR-2", simulated_minutes="45")
        self.assertTrue(res_str["success"])
        self.assertEqual(res_str["summary"]["duration_minutes"], 45)
        # Two-Wheeler: Base 10 + 15*1 = Rs. 25
        self.assertEqual(res_str["summary"]["fee"], 25.0)

    def test_automatic_fifo_queue_dispatch_on_exit(self):
        """Verify that when an occupied slot is freed, the head of FIFO queue is automatically assigned."""
        # 1. Fill all 6 Two-Wheelers
        for i in range(1, 7):
            self.pm.park_vehicle(f"TW-{i}", "Two-Wheeler")

        # 2. Queue 2 waiting vehicles
        self.pm.park_vehicle("WAITING-1", "Two-Wheeler")
        self.pm.park_vehicle("WAITING-2", "Two-Wheeler")
        self.assertEqual(len(self.pm.waiting_queue), 2)

        # 3. Exit TW-1 (which was in Slot S-01)
        exit_res = self.pm.exit_vehicle("TW-1", simulated_minutes=30)
        self.assertTrue(exit_res["success"])
        
        # Verify queue dispatch took place
        self.assertIsNotNone(exit_res["queue_allocation"])
        self.assertEqual(exit_res["queue_allocation"]["vehicle_number"], "WAITING-1")
        self.assertEqual(exit_res["queue_allocation"]["slot_number"], "S-01")

        # WAITING-1 is now active in active_vehicles dict!
        self.assertIn("WAITING-1", self.pm.active_vehicles)
        self.assertEqual(self.pm.active_vehicles["WAITING-1"]["slot_number"], "S-01")

        # Queue length reduced to 1, and WAITING-2 is now #1 in line
        self.assertEqual(len(self.pm.waiting_queue), 1)
        self.assertEqual(self.pm.waiting_queue[0]["vehicle_number"], "WAITING-2")
        self.assertEqual(self.pm.waiting_queue[0]["queue_position"], 1)

    def test_merge_sort_and_quick_sort(self):
        """Test custom DSA Merge Sort and Quick Sort algorithms on parking history."""
        # Seed test history records
        test_records = [
            {"id": 1, "vehicle_number": "KA-05-B", "duration_minutes": 90, "fee": 110.0, "exit_time": "2026-10-27 10:00:00"},
            {"id": 2, "vehicle_number": "KA-01-A", "duration_minutes": 30, "fee": 50.0, "exit_time": "2026-10-27 12:00:00"},
            {"id": 3, "vehicle_number": "KA-09-C", "duration_minutes": 180, "fee": 200.0, "exit_time": "2026-10-27 11:00:00"},
            {"id": 4, "vehicle_number": "KA-02-D", "duration_minutes": 15, "fee": 35.0, "exit_time": "2026-10-27 09:00:00"}
        ]

        # 1. Merge Sort by duration ascending
        sorted_msort = self.pm.merge_sort_history(test_records, sort_key="duration_minutes", reverse=False)
        durations = [r["duration_minutes"] for r in sorted_msort]
        self.assertEqual(durations, [15, 30, 90, 180])
        self.assertEqual(self.pm.last_sort_metrics["algorithm"], "Merge Sort")
        self.assertGreater(self.pm.last_sort_metrics["comparisons"], 0)

        # 2. Quick Sort by vehicle_number ascending
        sorted_qsort = self.pm.quick_sort_history(test_records, sort_key="vehicle_number", reverse=False)
        veh_nums = [r["vehicle_number"] for r in sorted_qsort]
        self.assertEqual(veh_nums, ["KA-01-A", "KA-02-D", "KA-05-B", "KA-09-C"])
        self.assertEqual(self.pm.last_sort_metrics["algorithm"], "Quick Sort")
        self.assertGreater(self.pm.last_sort_metrics["comparisons"], 0)

        # 3. Merge Sort by fee descending
        sorted_fee = self.pm.merge_sort_history(test_records, sort_key="fee", reverse=True)
        fees = [r["fee"] for r in sorted_fee]
        self.assertEqual(fees, [200.0, 110.0, 50.0, 35.0])

    def test_database_persistence_across_reloads(self):
        """Verify that in-memory DSA structures are accurately restored from SQLite upon manager restart."""
        # 1. Park vehicles and add to queue
        self.pm.park_vehicle("PERSIST-CAR-1", "Four-Wheeler")
        self.pm.park_vehicle("PERSIST-CAR-2", "Four-Wheeler")
        
        # Fill Two-Wheelers and queue one
        for i in range(1, 7):
            self.pm.park_vehicle(f"P-TW-{i}", "Two-Wheeler")
        self.pm.park_vehicle("P-TW-QUEUED", "Two-Wheeler")

        # 2. Simulate complete application restart by instantiating a new ParkingManager pointing to same SQLite DB
        new_pm = ParkingManager(self.temp_db_path)

        # Verify new manager recovered all active vehicles into its O(1) dictionary
        self.assertIn("PERSIST-CAR-1", new_pm.active_vehicles)
        self.assertIn("PERSIST-CAR-2", new_pm.active_vehicles)
        self.assertEqual(new_pm.active_vehicles["PERSIST-CAR-1"]["slot_number"], "S-07")
        self.assertEqual(new_pm.active_vehicles["PERSIST-CAR-2"]["slot_number"], "S-08")

        # Verify slots status in new manager
        slot_7 = next(s for s in new_pm.slots if s.slot_number == "S-07")
        self.assertEqual(slot_7.status, "occupied")
        self.assertEqual(slot_7.current_vehicle, "PERSIST-CAR-1")

        # Verify FIFO waiting queue was restored in collections.deque
        self.assertEqual(len(new_pm.waiting_queue), 1)
        self.assertEqual(new_pm.waiting_queue[0]["vehicle_number"], "P-TW-QUEUED")

if __name__ == '__main__':
    unittest.main()
