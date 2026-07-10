#!/usr/bin/env python3
"""
Board Analytics Test Runner

Automated test execution with setup, teardown, and reporting.

Usage:
    # Run all tests
    python tests/run_board_tests.py
    
    # Run specific scenario
    python tests/run_board_tests.py --scenario multi_board_comparison
    
    # Run with custom MongoDB URI
    python tests/run_board_tests.py --mongo-uri mongodb://localhost:27017
    
    # Cleanup test data only
    python tests/run_board_tests.py --cleanup-only
"""

import argparse
import sys
import os
import unittest
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from pymongo import MongoClient
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    print("ERROR: pymongo is required. Install with: pip install pymongo")
    sys.exit(1)

from tests.synthetic_board_data_generator import BoardDataGenerator


def cleanup_test_data(mongo_uri: str):
    """Clean up all test data."""
    print("\n" + "="*60)
    print("CLEANUP: Removing test data...")
    print("="*60)
    
    generator = BoardDataGenerator(mongo_uri=mongo_uri, test_db="iotsensing_test")
    generator.cleanup()
    generator.close()
    
    print("✓ Test data cleaned up successfully\n")


def run_specific_scenario(scenario: str, mongo_uri: str):
    """Run a specific test scenario and display results."""
    print("\n" + "="*60)
    print(f"SCENARIO: {scenario}")
    print("="*60)
    
    generator = BoardDataGenerator(mongo_uri=mongo_uri, test_db="iotsensing_test")
    
    try:
        # Generate test data
        print(f"\nGenerating test data for scenario: {scenario}...")
        result = generator.generate_test_scenario(scenario, duration_hours=2)
        
        # Display results
        print(f"\n✓ Scenario generated successfully!")
        print(f"\nGenerated data:")
        for key, value in result.items():
            if isinstance(value, list):
                print(f"  - {key}: {len(value)} items")
            else:
                print(f"  - {key}: {value}")
                
        # Query and display statistics
        print(f"\nDatabase statistics:")
        
        test_user_id = generator.get_test_user_id()
        
        boards_count = generator.db["boards"].count_documents({"user_id": test_user_id})
        envs_count = generator.db["environments"].count_documents({"user_id": test_user_id})
        quality_count = generator.db["audio_quality_metrics"].count_documents(
            {"board_id": {"$in": generator.generated_board_ids}}
        )
        raw_count = generator.db["raw_metrics"].count_documents({"user_id": test_user_id})
        
        print(f"  - Boards: {boards_count}")
        print(f"  - Environments: {envs_count}")
        print(f"  - Audio quality metrics: {quality_count}")
        print(f"  - Raw metrics: {raw_count}")
        
        # Show sample board data
        print(f"\nSample boards:")
        boards = list(generator.db["boards"].find({"user_id": test_user_id}).limit(3))
        for board in boards:
            print(f"  - {board['name']} ({board['mac_address']})")
            print(f"    Board ID: {board['board_id'][:16]}...")
            print(f"    Active: {board['is_active']}")
            print(f"    Environment: {board['environment_id'][:16]}...")
            
        print(f"\n{'='*60}")
        print(f"SCENARIO COMPLETE: Data ready for testing")
        print(f"{'='*60}\n")
        
        # Ask if user wants to cleanup
        cleanup = input("Clean up test data? [y/N]: ").strip().lower()
        if cleanup == 'y':
            generator.cleanup()
            print("✓ Test data cleaned up")
        else:
            print(f"ℹ Test data preserved in database 'iotsensing_test' for user {test_user_id}")
            
    except Exception as e:
        print(f"\n✗ Error running scenario: {e}")
        import traceback
        traceback.print_exc()
    finally:
        generator.close()


def run_all_tests(mongo_uri: str):
    """Run all unit tests."""
    print("\n" + "="*60)
    print("RUNNING ALL BOARD ANALYTICS TESTS")
    print("="*60 + "\n")
    
    # Set environment variable for tests
    os.environ["MONGO_URI"] = mongo_uri
    
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(__file__)
    suite = loader.discover(start_dir, pattern='test_board_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Some tests failed")
        
    print("="*60 + "\n")
    
    return 0 if result.wasSuccessful() else 1


def list_scenarios():
    """List available test scenarios."""
    scenarios = {
        "multi_board_comparison": "3 boards in different environments with different activity patterns",
        "data_deletion": "Single board with recent data for testing deletion functionality",
        "edge_cases": "Boards with various edge cases (idle, clipping, offline)",
        "full_analytics": "Complete scenario with 3 boards and 6 hours of varied data",
    }
    
    print("\n" + "="*60)
    print("AVAILABLE TEST SCENARIOS")
    print("="*60 + "\n")
    
    for name, description in scenarios.items():
        print(f"  {name}")
        print(f"    {description}\n")
        
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Run board analytics tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests
  python tests/run_board_tests.py
  
  # List available scenarios
  python tests/run_board_tests.py --list-scenarios
  
  # Run specific scenario
  python tests/run_board_tests.py --scenario multi_board_comparison
  
  # Cleanup test data
  python tests/run_board_tests.py --cleanup-only
        """
    )
    
    parser.add_argument(
        "--mongo-uri",
        default="mongodb://localhost:27017",
        help="MongoDB connection URI (default: mongodb://localhost:27017)"
    )
    
    parser.add_argument(
        "--scenario",
        help="Run specific test scenario instead of unit tests"
    )
    
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Only cleanup test data, don't run tests"
    )
    
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List available test scenarios"
    )
    
    args = parser.parse_args()
    
    # List scenarios
    if args.list_scenarios:
        list_scenarios()
        return 0
    
    # Cleanup only
    if args.cleanup_only:
        cleanup_test_data(args.mongo_uri)
        return 0
    
    # Run specific scenario
    if args.scenario:
        run_specific_scenario(args.scenario, args.mongo_uri)
        return 0
    
    # Run all tests
    return run_all_tests(args.mongo_uri)


if __name__ == "__main__":
    sys.exit(main())
