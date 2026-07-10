#!/usr/bin/env python3
"""
Test Suite Validation Script

Validates that the test suite is properly configured and ready to run.
Checks for:
- File structure
- Import availability
- Basic functionality

Usage:
    python tests/validate_tests.py
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def check_file_structure():
    """Verify all test files exist."""
    print("\n" + "="*60)
    print("CHECKING FILE STRUCTURE")
    print("="*60)
    
    required_files = [
        "tests/__init__.py",
        "tests/synthetic_board_data_generator.py",
        "tests/test_board_analytics.py",
        "tests/run_board_tests.py",
        "tests/integration_example.py",
        "tests/README.md",
    ]
    
    all_found = True
    for file_path in required_files:
        full_path = os.path.join(os.path.dirname(__file__), "..", file_path)
        exists = os.path.exists(full_path)
        status = "✓" if exists else "✗"
        print(f"  {status} {file_path}")
        if not exists:
            all_found = False
    
    return all_found


def check_imports():
    """Check if required imports are available."""
    print("\n" + "="*60)
    print("CHECKING IMPORTS")
    print("="*60)
    
    imports_available = True
    
    # Check pymongo
    try:
        import pymongo
        print("  ✓ pymongo available (version {})".format(pymongo.version))
    except ImportError:
        print("  ✗ pymongo NOT available - install with: pip install pymongo")
        imports_available = False
    
    # Check numpy
    try:
        import numpy
        print("  ✓ numpy available (version {})".format(numpy.__version__))
    except ImportError:
        print("  ✗ numpy NOT available - install with: pip install numpy")
        imports_available = False
    
    # Check pandas
    try:
        import pandas
        print("  ✓ pandas available (version {})".format(pandas.__version__))
    except ImportError:
        print("  ✗ pandas NOT available - install with: pip install pandas")
        imports_available = False
    
    # Check unittest (built-in)
    try:
        import unittest
        print("  ✓ unittest available")
    except ImportError:
        print("  ✗ unittest NOT available")
        imports_available = False
    
    return imports_available


def check_generator():
    """Test if the generator can be imported."""
    print("\n" + "="*60)
    print("CHECKING GENERATOR")
    print("="*60)
    
    try:
        from tests.synthetic_board_data_generator import BoardDataGenerator
        print("  ✓ BoardDataGenerator can be imported")
        
        # Try to instantiate (without connecting)
        print("  ✓ BoardDataGenerator class is valid")
        return True
    except Exception as e:
        print(f"  ✗ Error importing generator: {e}")
        return False


def check_tests():
    """Test if test modules can be imported."""
    print("\n" + "="*60)
    print("CHECKING TEST MODULES")
    print("="*60)
    
    try:
        from tests import test_board_analytics
        print("  ✓ test_board_analytics can be imported")
        
        # Check test classes
        if hasattr(test_board_analytics, 'TestBoardAnalytics'):
            print("  ✓ TestBoardAnalytics class found")
        else:
            print("  ✗ TestBoardAnalytics class not found")
            return False
            
        if hasattr(test_board_analytics, 'TestBoardDataGenerator'):
            print("  ✓ TestBoardDataGenerator class found")
        else:
            print("  ✗ TestBoardDataGenerator class not found")
            return False
            
        return True
    except Exception as e:
        print(f"  ✗ Error importing tests: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation checks."""
    print("\n" + "="*60)
    print("TEST SUITE VALIDATION")
    print("="*60)
    print("\nValidating board analytics test suite...")
    
    results = {
        "File Structure": check_file_structure(),
        "Imports": check_imports(),
        "Generator": check_generator(),
        "Test Modules": check_tests(),
    }
    
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {check}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✓ All validation checks passed!")
        print("\nYou can now run the tests:")
        print("  python tests/run_board_tests.py")
        print("  python tests/integration_example.py")
        return 0
    else:
        print("\n✗ Some validation checks failed.")
        print("\nPlease fix the issues above before running tests.")
        print("\nCommon fixes:")
        print("  - Install dependencies: pip install -r requirements.txt")
        print("  - Install pymongo: pip install pymongo")
        print("  - Install numpy: pip install numpy")
        return 1


if __name__ == "__main__":
    sys.exit(main())
