#!/usr/bin/env python3
"""
Test Cases for Board Analytics

Comprehensive tests for board configuration, analytics, and data deletion.

Usage:
    # Run all tests
    cd dashboard_layer && python -m unittest tests.test_board_analytics
    
    # Run specific test
    python -m unittest tests.test_board_analytics.TestBoardAnalytics.test_multi_board_comparison
"""

import unittest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import warnings

# Suppress SSL warnings for MongoDB connections
warnings.filterwarnings("ignore")

# Adjust path to import utilities
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from pymongo import MongoClient
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    print("Warning: pymongo not available, skipping database tests")

from tests.synthetic_board_data_generator import BoardDataGenerator


@unittest.skipIf(not PYMONGO_AVAILABLE, "pymongo not available")
class TestBoardAnalytics(unittest.TestCase):
    """Test board analytics functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database connection."""
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        cls.generator = BoardDataGenerator(mongo_uri=mongo_uri, test_db="iotsensing_test")
        cls.db = cls.generator.db
        cls.test_user_id = cls.generator.get_test_user_id()
        
    @classmethod
    def tearDownClass(cls):
        """Clean up test data and close connection."""
        cls.generator.cleanup()
        cls.generator.close()
        
    def setUp(self):
        """Clean up before each test."""
        self.generator.cleanup()
        
    def tearDown(self):
        """Clean up after each test."""
        self.generator.cleanup()
        
    def test_multi_board_comparison(self):
        """Test multi-board comparison analytics scenario."""
        # Generate test scenario
        result = self.generator.generate_test_scenario("multi_board_comparison", duration_hours=2)
        
        # Verify boards were created
        self.assertEqual(len(result["boards"]), 3)
        self.assertEqual(len(result["environments"]), 3)
        
        # Query boards
        boards = list(self.db["boards"].find({"user_id": self.test_user_id}))
        self.assertEqual(len(boards), 3)
        
        # Verify all boards are active
        for board in boards:
            self.assertTrue(board["is_active"])
            self.assertIn("board_id", board)
            self.assertIn("name", board)
            self.assertIn("environment_id", board)
            
        # Verify metrics were generated
        self.assertGreater(result["metrics_count"], 0)
        
        # Test analytics query - acoustic heatmap data
        quality_metrics = list(self.db["audio_quality_metrics"].find(
            {"board_id": {"$in": result["boards"]}}
        ))
        self.assertGreater(len(quality_metrics), 0)
        
        # Verify each metric has required fields
        for metric in quality_metrics[:5]:  # Check first 5
            self.assertIn("rms", metric)
            self.assertIn("peak_amplitude", metric)
            self.assertIn("db_fs", metric)
            self.assertIn("clipping_count", metric)
            self.assertIn("timestamp", metric)
            
        # Test signal quality matrix - count clipping by board
        for board_id in result["boards"]:
            board_metrics = [m for m in quality_metrics if m["board_id"] == board_id]
            total_clipping = sum(m.get("clipping_count", 0) for m in board_metrics)
            # Should have some data
            self.assertGreaterEqual(total_clipping, 0)
            
        # Test activity distribution - find dominant board per time window
        # Group by 5-minute intervals
        time_bins = {}
        for metric in quality_metrics:
            time_bin = metric["timestamp"].replace(second=0, microsecond=0)
            time_bin = time_bin - timedelta(minutes=time_bin.minute % 5)
            
            if time_bin not in time_bins:
                time_bins[time_bin] = {}
            
            board_id = metric["board_id"]
            if board_id not in time_bins[time_bin]:
                time_bins[time_bin][board_id] = []
            time_bins[time_bin][board_id].append(metric.get("rms", 0))
            
        # Verify we have multiple time bins
        self.assertGreater(len(time_bins), 0)
        
        print(f"✓ Multi-board comparison: {len(boards)} boards, {len(quality_metrics)} metrics, {len(time_bins)} time bins")
        
    def test_data_deletion(self):
        """Test data deletion functionality."""
        # Constants for time window
        DELETION_WINDOW_START_OFFSET = 0.5  # seconds before timestamp
        DELETION_WINDOW_END_OFFSET = 5.5    # seconds after timestamp
        
        # Generate test scenario with recent data
        result = self.generator.generate_test_scenario("data_deletion", duration_hours=1)
        
        board_id = result["board"]
        test_timestamp = result["test_timestamp"]
        
        # Verify initial data exists
        initial_metrics = self.db["audio_quality_metrics"].count_documents(
            {"board_id": board_id}
        )
        initial_raw = self.db["raw_metrics"].count_documents(
            {"board_id": board_id}
        )
        
        self.assertGreater(initial_metrics, 0, "Should have audio quality metrics")
        self.assertGreater(initial_raw, 0, "Should have raw metrics")
        
        # Simulate deletion - delete metrics in a time window around test_timestamp
        ts_dt = datetime.utcfromtimestamp(test_timestamp)
        window_start = ts_dt - timedelta(seconds=DELETION_WINDOW_START_OFFSET)
        window_end = ts_dt + timedelta(seconds=DELETION_WINDOW_END_OFFSET)
        
        delete_result = self.db["raw_metrics"].delete_many({
            "board_id": board_id,
            "timestamp": {"$gte": window_start, "$lte": window_end}
        })
        
        deleted_count = delete_result.deleted_count
        self.assertGreater(deleted_count, 0, "Should have deleted some metrics")
        
        # Verify data was deleted
        remaining_metrics = self.db["raw_metrics"].count_documents(
            {"board_id": board_id}
        )
        self.assertLess(remaining_metrics, initial_raw, "Should have fewer metrics after deletion")
        
        # Verify analytics still work with remaining data
        remaining_quality = list(self.db["audio_quality_metrics"].find(
            {"board_id": board_id}
        ))
        self.assertGreater(len(remaining_quality), 0, "Should still have quality metrics")
        
        # Test that we can still calculate statistics
        if remaining_quality:
            avg_rms = sum(m.get("rms", 0) for m in remaining_quality) / len(remaining_quality)
            self.assertGreater(avg_rms, 0, "Should be able to calculate average RMS")
            
        print(f"✓ Data deletion: deleted {deleted_count} metrics, {remaining_metrics} remaining")
        
    def test_edge_cases(self):
        """Test edge cases in board analytics."""
        # Generate edge case scenario
        result = self.generator.generate_test_scenario("edge_cases", duration_hours=3)
        
        boards = result["boards"]
        self.assertEqual(len(boards), 3)
        
        # Board 1: Active but no recent data (idle)
        board1 = boards[0]
        five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
        recent_data = self.db["raw_metrics"].find_one({
            "board_id": board1,
            "timestamp": {"$gte": five_mins_ago}
        })
        self.assertIsNone(recent_data, "Board 1 should have no recent data")
        
        # But should have old data
        old_data = self.db["audio_quality_metrics"].count_documents(
            {"board_id": board1}
        )
        self.assertGreater(old_data, 0, "Board 1 should have old data")
        
        # Board 2: Should have clipping issues
        board2 = boards[1]
        board2_metrics = list(self.db["audio_quality_metrics"].find(
            {"board_id": board2}
        ))
        total_clipping = sum(m.get("clipping_count", 0) for m in board2_metrics)
        self.assertGreater(total_clipping, 50, "Board 2 should have significant clipping")
        
        # Board 3: Should be inactive
        board3_doc = self.db["boards"].find_one({"board_id": boards[2]})
        self.assertIsNotNone(board3_doc)
        self.assertFalse(board3_doc.get("is_active", True), "Board 3 should be inactive")
        
        # Test empty data handling
        empty_board_id = "nonexistent-board-id"
        empty_metrics = list(self.db["audio_quality_metrics"].find(
            {"board_id": empty_board_id}
        ))
        self.assertEqual(len(empty_metrics), 0, "Should handle empty data gracefully")
        
        print(f"✓ Edge cases: idle board, {total_clipping} clipping events, inactive board")
        
    def test_board_crud_operations(self):
        """Test board CRUD operations."""
        # Create environment first
        env_id = self.generator.generate_environment("CRUD Test Room", "Testing CRUD")
        
        # Create board
        board_id = self.generator.generate_board("CRUD Test Board", env_id, is_active=True)
        
        # Read board
        board = self.db["boards"].find_one({"board_id": board_id})
        self.assertIsNotNone(board)
        self.assertEqual(board["name"], "CRUD Test Board")
        self.assertEqual(board["environment_id"], env_id)
        self.assertTrue(board["is_active"])
        
        # Update board
        self.db["boards"].update_one(
            {"board_id": board_id},
            {"$set": {"name": "Updated Board Name", "is_active": False}}
        )
        
        updated_board = self.db["boards"].find_one({"board_id": board_id})
        self.assertEqual(updated_board["name"], "Updated Board Name")
        self.assertFalse(updated_board["is_active"])
        
        # Delete board
        delete_result = self.db["boards"].delete_one({"board_id": board_id})
        self.assertEqual(delete_result.deleted_count, 1)
        
        # Verify deletion
        deleted_board = self.db["boards"].find_one({"board_id": board_id})
        self.assertIsNone(deleted_board)
        
        print("✓ Board CRUD: create, read, update, delete")
        
    def test_environment_crud_operations(self):
        """Test environment CRUD operations."""
        # Create environment
        env_id = self.generator.generate_environment("Test Environment", "Test Description")
        
        # Read environment
        env = self.db["environments"].find_one({"environment_id": env_id})
        self.assertIsNotNone(env)
        self.assertEqual(env["name"], "Test Environment")
        self.assertEqual(env["description"], "Test Description")
        
        # Update environment
        self.db["environments"].update_one(
            {"environment_id": env_id},
            {"$set": {"name": "Updated Environment", "description": "Updated Description"}}
        )
        
        updated_env = self.db["environments"].find_one({"environment_id": env_id})
        self.assertEqual(updated_env["name"], "Updated Environment")
        self.assertEqual(updated_env["description"], "Updated Description")
        
        # Delete environment
        delete_result = self.db["environments"].delete_one({"environment_id": env_id})
        self.assertEqual(delete_result.deleted_count, 1)
        
        # Verify deletion
        deleted_env = self.db["environments"].find_one({"environment_id": env_id})
        self.assertIsNone(deleted_env)
        
        print("✓ Environment CRUD: create, read, update, delete")
        
    def test_analytics_calculations(self):
        """Test analytics calculations with various data patterns."""
        # Generate full analytics scenario
        result = self.generator.generate_test_scenario("full_analytics", duration_hours=6)
        
        boards = result["boards"]
        
        # Test 1: Calculate average RMS per board
        for board_id in boards:
            metrics = list(self.db["audio_quality_metrics"].find(
                {"board_id": board_id},
                {"rms": 1, "_id": 0}
            ))
            
            if metrics:
                avg_rms = sum(m.get("rms", 0) for m in metrics) / len(metrics)
                self.assertGreater(avg_rms, 0, f"Board {board_id} should have positive average RMS")
                self.assertLess(avg_rms, 1.0, f"Board {board_id} RMS should be less than 1.0")
                
        # Test 2: Calculate dBFS statistics
        for board_id in boards:
            metrics = list(self.db["audio_quality_metrics"].find(
                {"board_id": board_id},
                {"db_fs": 1, "_id": 0}
            ))
            
            if metrics:
                dbfs_values = [m.get("db_fs", -96) for m in metrics]
                avg_dbfs = sum(dbfs_values) / len(dbfs_values)
                self.assertGreaterEqual(avg_dbfs, -96, "dBFS should be >= -96")
                self.assertLessEqual(avg_dbfs, 0, "dBFS should be <= 0")
                
        # Test 3: Calculate total clipping events
        total_clipping = 0
        for board_id in boards:
            board_clipping = self.db["audio_quality_metrics"].aggregate([
                {"$match": {"board_id": board_id}},
                {"$group": {"_id": None, "total": {"$sum": "$clipping_count"}}}
            ])
            
            result_list = list(board_clipping)
            if result_list:
                total_clipping += result_list[0]["total"]
                
        self.assertGreaterEqual(total_clipping, 0, "Total clipping should be non-negative")
        
        # Test 4: Test SNR availability
        snr_metrics = list(self.db["audio_quality_metrics"].find(
            {"board_id": {"$in": boards}, "snr": {"$ne": None}},
            {"snr": 1, "_id": 0}
        ))
        
        # SNR should be available for some metrics (30% probability in generator)
        if len(snr_metrics) > 0:
            avg_snr = sum(m.get("snr", 0) for m in snr_metrics) / len(snr_metrics)
            self.assertGreater(avg_snr, 0, "Average SNR should be positive when available")
            
        print(f"✓ Analytics calculations: {len(boards)} boards, {total_clipping} total clipping, {len(snr_metrics)} SNR samples")
        
    def test_streaming_detection(self):
        """Test detection of boards currently streaming data."""
        # Generate test data
        result = self.generator.generate_test_scenario("multi_board_comparison", duration_hours=1)
        
        boards = result["boards"]
        
        # Check which boards have recent data (last 5 minutes)
        five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
        
        streaming_boards = []
        for board_id in boards:
            recent_data = self.db["raw_metrics"].find_one({
                "board_id": board_id,
                "timestamp": {"$gte": five_mins_ago}
            })
            if recent_data:
                streaming_boards.append(board_id)
                
        # At least some boards should be streaming (we generated recent data for active boards)
        self.assertGreater(len(streaming_boards), 0, "Should have at least one streaming board")
        
        # Verify streaming count matches expected
        # In multi_board_comparison, we generate recent data for board1 and board2
        self.assertGreaterEqual(len(streaming_boards), 2, "Should have at least 2 streaming boards")
        
        print(f"✓ Streaming detection: {len(streaming_boards)}/{len(boards)} boards streaming")
        
    def test_time_window_queries(self):
        """Test analytics queries with different time windows."""
        # Generate 12 hours of data
        result = self.generator.generate_test_scenario("full_analytics", duration_hours=12)
        
        board_id = result["boards"][0]
        
        # Test different time windows
        windows = [
            ("10 minutes", 10),
            ("30 minutes", 30),
            ("60 minutes", 60),
            ("2 hours", 120),
            ("6 hours", 360),
        ]
        
        for window_label, window_minutes in windows:
            time_threshold = datetime.utcnow() - timedelta(minutes=window_minutes)
            
            metrics = list(self.db["audio_quality_metrics"].find(
                {
                    "board_id": board_id,
                    "timestamp": {"$gte": time_threshold}
                }
            ))
            
            # Should have metrics for each window
            # At 5-second intervals, we expect: (window_minutes * 60 / 5) samples
            expected_min = (window_minutes * 60 // 5) * 0.5  # Allow 50% tolerance
            
            if window_minutes <= 360:  # Within our data range
                self.assertGreater(
                    len(metrics), 
                    expected_min,
                    f"Should have sufficient data for {window_label} window"
                )
                
        print(f"✓ Time window queries: tested {len(windows)} different windows")
        
    def test_empty_data_handling(self):
        """Test that analytics handle empty data gracefully."""
        # Create boards but don't generate any metrics
        env_id = self.generator.generate_environment("Empty Test Room", "No data")
        board_id = self.generator.generate_board("Empty Board", env_id, is_active=True)
        
        # Query for metrics (should be empty)
        metrics = list(self.db["audio_quality_metrics"].find(
            {"board_id": board_id}
        ))
        self.assertEqual(len(metrics), 0, "Should have no metrics")
        
        # Test analytics calculations with empty data
        # These should not raise errors
        total_clipping = sum(m.get("clipping_count", 0) for m in metrics)
        self.assertEqual(total_clipping, 0)
        
        # Average should handle division by zero
        avg_rms = sum(m.get("rms", 0) for m in metrics) / len(metrics) if metrics else 0
        self.assertEqual(avg_rms, 0)
        
        print("✓ Empty data handling: gracefully handled empty metrics")


class TestBoardDataGenerator(unittest.TestCase):
    """Test the synthetic data generator itself."""
    
    def test_quality_metrics_patterns(self):
        """Test that different patterns generate distinct characteristics."""
        generator = BoardDataGenerator(mongo_uri="mongodb://localhost:27017", test_db="iotsensing_test")
        
        start_time = datetime.utcnow() - timedelta(hours=1)
        end_time = datetime.utcnow()
        board_id = "test-board"
        
        # Generate different patterns
        patterns = {
            "normal": generator.generate_quality_metrics(board_id, start_time, end_time, "normal"),
            "high_activity": generator.generate_quality_metrics(board_id, start_time, end_time, "high_activity"),
            "low_activity": generator.generate_quality_metrics(board_id, start_time, end_time, "low_activity"),
            "clipping_issues": generator.generate_quality_metrics(board_id, start_time, end_time, "clipping_issues"),
        }
        
        # Verify each pattern has distinct characteristics
        for pattern_name, metrics in patterns.items():
            self.assertGreater(len(metrics), 0, f"{pattern_name} should generate metrics")
            
            avg_rms = sum(m["rms"] for m in metrics) / len(metrics)
            total_clipping = sum(m["clipping_count"] for m in metrics)
            
            if pattern_name == "high_activity":
                self.assertGreater(avg_rms, 0.20, "High activity should have higher RMS")
            elif pattern_name == "low_activity":
                self.assertLess(avg_rms, 0.10, "Low activity should have lower RMS")
            elif pattern_name == "clipping_issues":
                self.assertGreater(total_clipping, 50, "Clipping pattern should have many clipping events")
                
        generator.close()
        print("✓ Pattern generation: all patterns generate distinct data")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
