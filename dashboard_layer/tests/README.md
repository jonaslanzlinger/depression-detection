# Board Analytics Test Suite

This directory contains comprehensive test cases for the boards data analytics features.

## Overview

The test suite provides:

- **Synthetic Data Generation**: Realistic test data for multiple boards with various activity patterns
- **Comprehensive Test Coverage**: Tests for analytics, CRUD operations, data deletion, and edge cases
- **Automated Test Runner**: Easy execution and cleanup of test scenarios
- **Integration Testing**: Validates the complete flow from data generation to analytics visualization

## Files

- `synthetic_board_data_generator.py` - Generates realistic test data for boards and analytics
- `test_board_analytics.py` - Comprehensive unit tests for board analytics features
- `run_board_tests.py` - Test runner script with automated setup and teardown
- `test_sankey_adapter.py` - Existing tests for Sankey adapter
- `README.md` - This file

## Quick Start

### Running All Tests

```bash
cd dashboard_layer
python tests/run_board_tests.py
```

### Running Specific Test Scenarios

```bash
# List available scenarios
python tests/run_board_tests.py --list-scenarios

# Run multi-board comparison scenario
python tests/run_board_tests.py --scenario multi_board_comparison

# Run data deletion scenario
python tests/run_board_tests.py --scenario data_deletion

# Run edge cases scenario
python tests/run_board_tests.py --scenario edge_cases

# Run full analytics scenario
python tests/run_board_tests.py --scenario full_analytics
```

### Running Individual Tests

```bash
# Run all board analytics tests
python -m unittest tests.test_board_analytics

# Run specific test class
python -m unittest tests.test_board_analytics.TestBoardAnalytics

# Run specific test method
python -m unittest tests.test_board_analytics.TestBoardAnalytics.test_multi_board_comparison
```

### Cleanup Test Data

```bash
python tests/run_board_tests.py --cleanup-only
```

## Test Scenarios

### 1. Multi-Board Comparison
- **Purpose**: Test analytics with multiple boards in different environments
- **Setup**: 3 boards with different activity patterns (high, normal, low)
- **Tests**: Heatmap data, signal quality matrix, activity distribution

### 2. Data Deletion
- **Purpose**: Test data deletion functionality without breaking analytics
- **Setup**: Single board with recent data for deletion
- **Tests**: Delete metrics, verify remaining data, ensure analytics still work

### 3. Edge Cases
- **Purpose**: Test handling of unusual scenarios
- **Setup**: Idle board, board with clipping issues, inactive board
- **Tests**: Empty data handling, high clipping detection, offline status

### 4. Full Analytics
- **Purpose**: Comprehensive analytics testing with realistic data
- **Setup**: 3 boards with 6 hours of varied activity
- **Tests**: All analytics features with sufficient data volume

## Test Coverage

The test suite covers:

### Board Management
- ✅ Create board
- ✅ Read board details
- ✅ Update board configuration
- ✅ Delete board
- ✅ List boards by user

### Environment Management
- ✅ Create environment
- ✅ Read environment details
- ✅ Update environment
- ✅ Delete environment
- ✅ List environments by user

### Analytics Features
- ✅ Acoustic heatmap data generation
- ✅ Signal quality matrix calculation
- ✅ Activity distribution analysis
- ✅ Time window queries (10min, 30min, 1hr, 2hr, 6hr)
- ✅ Streaming status detection
- ✅ RMS, dBFS, clipping statistics
- ✅ SNR availability and calculation

### Data Operations
- ✅ Data deletion with time window
- ✅ Bulk metric queries
- ✅ Empty data handling
- ✅ Edge case validation

### Integration
- ✅ End-to-end data flow
- ✅ Analytics calculation with various patterns
- ✅ Error handling and recovery
- ✅ Data consistency after deletion

## Synthetic Data Generator

### Usage Example

```python
from tests.synthetic_board_data_generator import BoardDataGenerator

# Initialize generator
generator = BoardDataGenerator(
    mongo_uri="mongodb://localhost:27017",
    test_db="iotsensing_test"
)

# Generate test scenario
result = generator.generate_test_scenario("multi_board_comparison", duration_hours=2)

# Or generate custom data
result = generator.generate_test_data(num_boards=5, days=1, pattern="normal")

# Cleanup when done
generator.cleanup()
generator.close()
```

### Activity Patterns

The generator supports multiple activity patterns:

- **normal**: Typical audio activity with moderate RMS and occasional clipping
- **high_activity**: High volume levels, more clipping events
- **low_activity**: Quiet environment, low RMS values
- **intermittent**: Sporadic activity with gaps in data
- **clipping_issues**: Frequent clipping events (signal overload)

### Generated Metrics

Each board generates realistic:
- RMS (Root Mean Square) values
- Peak amplitude measurements
- dBFS (decibels relative to full scale)
- Clipping event counts
- Dynamic range calculations
- SNR (Signal-to-Noise Ratio) - available for ~30% of samples

## Database Structure

Test data is stored in `iotsensing_test` database with these collections:

- `boards` - Board configurations
- `environments` - Environment definitions
- `audio_quality_metrics` - Real-time quality metrics per board
- `raw_metrics` - Raw acoustic metrics for streaming detection

All test data uses `user_id: 9999` for easy identification and cleanup.

## Requirements

- Python 3.9+
- pymongo
- numpy
- MongoDB instance (local or remote)

## Troubleshooting

### Tests fail with "pymongo not available"
```bash
pip install pymongo
```

### Tests fail with connection error
Check that MongoDB is running:
```bash
# For Docker
docker ps | grep mongodb

# For local MongoDB
systemctl status mongodb
```

Verify connection URI:
```bash
python tests/run_board_tests.py --mongo-uri mongodb://your-host:27017
```

### Test data not cleaned up
Manually cleanup:
```bash
python tests/run_board_tests.py --cleanup-only
```

Or use MongoDB client:
```javascript
use iotsensing_test
db.boards.deleteMany({user_id: 9999})
db.environments.deleteMany({user_id: 9999})
db.raw_metrics.deleteMany({user_id: 9999})
// ... etc
```

## Integration with CI/CD

The tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Board Analytics Tests
  run: |
    cd dashboard_layer
    python tests/run_board_tests.py --mongo-uri mongodb://mongodb:27017
```

## Contributing

When adding new tests:

1. Add test methods to `test_board_analytics.py`
2. Follow existing naming conventions (`test_*`)
3. Use the generator for data setup
4. Clean up in tearDown
5. Add assertions with descriptive messages
6. Update this README with new coverage

## License

Same as the main project.
