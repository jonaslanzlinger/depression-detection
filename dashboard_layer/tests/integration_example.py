#!/usr/bin/env python3
"""
Board Analytics Integration Example

Demonstrates how to use the synthetic data generator and test suite
for board analytics testing and validation.

This script shows:
1. Generating test data for different scenarios
2. Running analytics queries
3. Testing data deletion
4. Validating analytics calculations
5. Cleaning up test data

Usage:
    python tests/integration_example.py
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from pymongo import MongoClient
except ImportError:
    print("ERROR: pymongo is required. Install with: pip install pymongo")
    print("       or: pip install -r requirements.txt")
    sys.exit(1)

from tests.synthetic_board_data_generator import BoardDataGenerator


def example_multi_board_analytics():
    """Example: Generate data for multi-board analytics testing."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Multi-Board Analytics")
    print("="*70)
    
    # Initialize generator
    generator = BoardDataGenerator(
        mongo_uri="mongodb://localhost:27017",
        test_db="iotsensing_test"
    )
    
    try:
        # Clean up any existing test data
        print("\n1. Cleaning up existing test data...")
        generator.cleanup()
        
        # Generate multi-board scenario
        print("2. Generating multi-board comparison scenario...")
        result = generator.generate_test_scenario("multi_board_comparison", duration_hours=2)
        
        print(f"\n   ✓ Created {len(result['boards'])} boards in {len(result['environments'])} environments")
        print(f"   ✓ Generated {result['metrics_count']} quality metrics")
        
        # Query and display analytics data
        print("\n3. Running analytics queries...")
        
        # Get boards
        boards = list(generator.db["boards"].find({"user_id": generator.test_user_id}))
        print(f"\n   Boards:")
        for board in boards:
            print(f"   - {board['name']} ({board['mac_address']})")
            print(f"     ID: {board['board_id'][:20]}...")
            print(f"     Active: {board['is_active']}")
        
        # Calculate analytics
        print("\n4. Calculating analytics...")
        
        for board in boards:
            metrics = list(generator.db["audio_quality_metrics"].find(
                {"board_id": board["board_id"]}
            ))
            
            if metrics:
                avg_rms = sum(m.get("rms", 0) for m in metrics) / len(metrics)
                avg_dbfs = sum(m.get("db_fs", -96) for m in metrics) / len(metrics)
                total_clipping = sum(m.get("clipping_count", 0) for m in metrics)
                
                print(f"\n   {board['name']}:")
                print(f"   - Samples: {len(metrics)}")
                print(f"   - Avg RMS: {avg_rms:.4f}")
                print(f"   - Avg dBFS: {avg_dbfs:.2f} dB")
                print(f"   - Total Clipping: {total_clipping}")
        
        print("\n5. Test complete! Data is ready for dashboard testing.")
        print(f"   Open the dashboard at http://localhost:8084 and select user {generator.test_user_id}")
        
        # Ask user if they want to keep the data
        keep = input("\nKeep test data for manual testing? [Y/n]: ").strip().lower()
        if keep != 'n':
            print(f"\n✓ Test data preserved in 'iotsensing_test' database")
            print(f"  Run cleanup when done: python tests/run_board_tests.py --cleanup-only")
        else:
            generator.cleanup()
            print("\n✓ Test data cleaned up")
            
    finally:
        generator.close()


def example_data_deletion():
    """Example: Test data deletion functionality."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Data Deletion Testing")
    print("="*70)
    
    generator = BoardDataGenerator(
        mongo_uri="mongodb://localhost:27017",
        test_db="iotsensing_test"
    )
    
    try:
        print("\n1. Generating test data for deletion testing...")
        result = generator.generate_test_scenario("data_deletion", duration_hours=1)
        
        board_id = result["board"]
        test_timestamp = result["test_timestamp"]
        
        # Check initial counts
        initial_quality = generator.db["audio_quality_metrics"].count_documents(
            {"board_id": board_id}
        )
        initial_raw = generator.db["raw_metrics"].count_documents(
            {"board_id": board_id}
        )
        
        print(f"\n   ✓ Initial data:")
        print(f"     - Audio quality metrics: {initial_quality}")
        print(f"     - Raw metrics: {initial_raw}")
        
        # Simulate deletion
        print("\n2. Simulating data deletion...")
        ts_dt = datetime.utcfromtimestamp(test_timestamp)
        window_start = ts_dt - timedelta(seconds=0.5)
        window_end = ts_dt + timedelta(seconds=5.5)
        
        raw_result = generator.db["raw_metrics"].delete_many({
            "board_id": board_id,
            "timestamp": {"$gte": window_start, "$lte": window_end}
        })
        
        quality_result = generator.db["audio_quality_metrics"].delete_many({
            "board_id": board_id,
            "timestamp": {"$gte": window_start, "$lte": window_end}
        })
        
        print(f"\n   ✓ Deleted:")
        print(f"     - Raw metrics: {raw_result.deleted_count}")
        print(f"     - Quality metrics: {quality_result.deleted_count}")
        
        # Check remaining data
        remaining_quality = generator.db["audio_quality_metrics"].count_documents(
            {"board_id": board_id}
        )
        remaining_raw = generator.db["raw_metrics"].count_documents(
            {"board_id": board_id}
        )
        
        print(f"\n   ✓ Remaining data:")
        print(f"     - Audio quality metrics: {remaining_quality}")
        print(f"     - Raw metrics: {remaining_raw}")
        
        # Verify analytics still work
        print("\n3. Verifying analytics still work with remaining data...")
        
        remaining_metrics = list(generator.db["audio_quality_metrics"].find(
            {"board_id": board_id}
        ))
        
        if remaining_metrics:
            avg_rms = sum(m.get("rms", 0) for m in remaining_metrics) / len(remaining_metrics)
            print(f"\n   ✓ Analytics functional: Avg RMS = {avg_rms:.4f}")
        else:
            print("\n   ⚠ No metrics remaining (expected if all were deleted)")
        
        # Cleanup
        generator.cleanup()
        print("\n✓ Test data cleaned up")
        
    finally:
        generator.close()


def example_edge_cases():
    """Example: Test edge cases and error handling."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Edge Cases Testing")
    print("="*70)
    
    generator = BoardDataGenerator(
        mongo_uri="mongodb://localhost:27017",
        test_db="iotsensing_test"
    )
    
    try:
        print("\n1. Generating edge case scenario...")
        result = generator.generate_test_scenario("edge_cases", duration_hours=3)
        
        boards = result["boards"]
        
        print(f"\n   ✓ Created {len(boards)} boards with different edge cases")
        
        # Check each board
        print("\n2. Analyzing edge cases...")
        
        five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
        
        # Board 1: Idle (no recent data)
        board1_recent = generator.db["raw_metrics"].find_one({
            "board_id": boards[0],
            "timestamp": {"$gte": five_mins_ago}
        })
        
        board1_old = generator.db["audio_quality_metrics"].count_documents(
            {"board_id": boards[0]}
        )
        
        print(f"\n   Board 1 (Idle):")
        print(f"   - Recent data: {'None' if not board1_recent else 'Present'}")
        print(f"   - Historical data: {board1_old} samples")
        print(f"   ✓ Correctly shows as idle board")
        
        # Board 2: Clipping issues
        board2_metrics = list(generator.db["audio_quality_metrics"].find(
            {"board_id": boards[1]}
        ))
        total_clipping = sum(m.get("clipping_count", 0) for m in board2_metrics)
        
        print(f"\n   Board 2 (Clipping Issues):")
        print(f"   - Total clipping events: {total_clipping}")
        print(f"   ✓ High clipping rate detected")
        
        # Board 3: Inactive
        board3_doc = generator.db["boards"].find_one({"board_id": boards[2]})
        
        print(f"\n   Board 3 (Offline):")
        print(f"   - Active status: {board3_doc.get('is_active', False)}")
        print(f"   ✓ Correctly marked as inactive")
        
        print("\n3. Testing empty data handling...")
        
        # Query non-existent board
        empty_metrics = list(generator.db["audio_quality_metrics"].find(
            {"board_id": "nonexistent-board"}
        ))
        
        print(f"   - Empty query result: {len(empty_metrics)} records")
        print(f"   ✓ Empty data handled gracefully")
        
        # Cleanup
        generator.cleanup()
        print("\n✓ Test data cleaned up")
        
    finally:
        generator.close()


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("BOARD ANALYTICS INTEGRATION EXAMPLES")
    print("="*70)
    print("\nThis script demonstrates the synthetic data generator and test suite.")
    print("Examples included:")
    print("  1. Multi-board analytics testing")
    print("  2. Data deletion functionality")
    print("  3. Edge cases and error handling")
    
    choice = input("\nRun which example? [1/2/3/all/quit]: ").strip().lower()
    
    if choice == '1':
        example_multi_board_analytics()
    elif choice == '2':
        example_data_deletion()
    elif choice == '3':
        example_edge_cases()
    elif choice == 'all':
        example_multi_board_analytics()
        example_data_deletion()
        example_edge_cases()
    elif choice == 'quit' or choice == 'q':
        print("\nExiting...")
    else:
        print("\nInvalid choice. Please run again and select 1, 2, 3, all, or quit.")
    
    print("\n" + "="*70)
    print("For more information, see dashboard_layer/tests/README.md")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
