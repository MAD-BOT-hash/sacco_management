# SACCO Management System - Testing Guide

## Overview

The SACCO Management System includes a comprehensive testing framework with unit tests, integration tests, and performance tests to ensure code quality and system reliability.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── test_utils.py               # Base test classes and utilities
├── test_config.py              # Test configuration settings
├── run_tests.py                # Main test runner
├── test_member.py              # Member module tests
├── test_loan.py                # Loan module tests
├── test_savings_shares.py      # Savings & Shares tests
├── test_integration.py         # API integration tests
└── test_performance.py         # Performance tests
```

## Quick Start

### Run All Tests

```bash
# From project root directory
python -m tests.run_tests --all
```

### Run Specific Module

```bash
# Test member module only
python -m tests.run_tests --module member

# Test loan module only
python -m tests.run_tests --module loan

# Test savings & shares
python -m tests.run_tests --module savings
```

### Run Performance Tests

```bash
python -m tests.run_tests --performance
```

### Generate HTML Report

```bash
python -m tests.run_tests --all --report
```

## Test Categories

### 1. Unit Tests

**Location**: `test_member.py`, `test_loan.py`, `test_savings_shares.py`

**Purpose**: Test individual components in isolation

**Examples**:
- Member creation and validation
- Loan calculations (EMI, interest)
- Savings account operations
- Share allocation processing

**Run**:
```bash
python -m tests.run_tests --module member
```

### 2. Integration Tests

**Location**: `test_integration.py`

**Purpose**: Test complete business workflows across multiple modules

**Examples**:
- Complete member lifecycle (create → update → view → search)
- Loan workflow (application → approval → disbursement → repayment)
- Savings workflow (account → deposit → withdrawal)

**Run**:
```bash
python -m tests.run_tests --module integration
```

### 3. Performance Tests

**Location**: `test_performance.py`

**Purpose**: Verify system performance under load

**Test Scenarios**:
- Bulk member creation (100 members)
- Loan calculation speed
- API response times
- Database query optimization

**Performance Thresholds**:
- Member creation: < 500ms
- Loan calculation: < 50ms
- API response: < 500ms
- Database query: < 200ms

**Run**:
```bash
python -m tests.run_tests --performance
```

## Writing Tests

### Base Test Classes

#### SACCOBaseTestCase

Use for general unit tests:

```python
from tests.test_utils import SACCOBaseTestCase

class TestMyFeature(SACCOBaseTestCase):
    
    def test_feature(self):
        member = self.create_test_member()
        # Your test logic here
        self.assertIsNotNone(member.name)
```

#### APITestCase

Use for API endpoint tests:

```python
from tests.test_utils import APITestCase

class TestMyAPI(APITestCase):
    
    def test_api_endpoint(self):
        response = self.make_api_call(
            "POST",
            "member_api.create_member",
            params={"member_data": {...}}
        )
        
        self.assertResponseSuccess(response)
```

#### DatabaseTestCase

Use for database-level tests:

```python
from tests.test_utils import DatabaseTestCase

class TestDatabase(DatabaseTestCase):
    
    def test_query(self):
        count = self.count_records("SACCO Member")
        self.assertGreater(count, 0)
```

### Helper Methods

Available in all test classes:

- `create_test_member(**kwargs)` - Create test member
- `create_test_savings_account(member, **kwargs)` - Create savings account
- `create_test_loan_application(member, **kwargs)` - Create loan application
- `create_test_share_allocation(member, **kwargs)` - Create share allocation

### Assertion Helpers

- `assertResponseSuccess(response)` - Assert API success
- `assertResponseError(response, expected_error)` - Assert API error
- `count_records(doctype, filters)` - Count database records
- `exists(doctype, filters)` - Check record existence

## Test Configuration

Edit `tests/test_config.py` to customize:

```python
TEST_SETTINGS = {
    "create_test_data": True,      # Auto-create fixtures
    "cleanup_after_tests": True,   # Cleanup after tests
    "show_sql_queries": False,     # Show SQL in logs
    "enable_performance_profiling": True,
    "max_execution_time": 300      # Timeout in seconds
}

PERFORMANCE_THRESHOLDS = {
    "member_creation_ms": 500,
    "loan_calculation_ms": 50,
    "api_response_ms": 500,
    "database_query_ms": 200,
    "search_operation_ms": 100
}
```

## Running Tests in CI/CD

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      mariadb:
        image: mariadb:10.6
        env:
          MYSQL_ROOT_PASSWORD: admin
        ports:
          - 3306:3306
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install coverage
      
      - name: Run tests with coverage
        run: |
          coverage run -m tests.run_tests --all
          coverage xml
      
      - name: Upload coverage report
        uses: codecov/codecov-action@v2
        with:
          file: ./coverage.xml
```

### Jenkins Pipeline Example

```groovy
pipeline {
    agent any
    
    stages {
        stage('Test') {
            steps {
                sh 'python -m tests.run_tests --all --report'
                junit 'test_report_*.xml'
            }
            post {
                always {
                    archiveArtifacts artifacts: 'test_report_*.html'
                }
            }
        }
    }
}
```

## Coverage Reports

Generate coverage report:

```bash
# Run tests with coverage
coverage run -m tests.run_tests --all

# Generate HTML report
coverage html

# View report
open htmlcov/index.html
```

## Best Practices

### 1. Test Naming

Use descriptive names:
- ✅ `test_member_creation_with_valid_email`
- ❌ `test_member_1`

### 2. Test Isolation

Each test should be independent:
```python
def setUp(self):
    """Setup fresh test data for each test"""
    frappe.db.rollback()
```

### 3. Cleanup Resources

Always cleanup created data:
```python
@classmethod
def tearDownClass(cls):
    for member in cls.test_members:
        frappe.delete_doc("SACCO Member", member, force=True)
    frappe.db.commit()
```

### 4. Use Transactions

Wrap tests in transactions:
```python
def test_database_operation(self):
    with frappe.db.transaction():
        # Your test logic
        pass
```

### 5. Test Edge Cases

Don't just test happy path:
```python
def test_member_creation_with_invalid_email(self):
    with self.assertRaises(Exception):
        self.create_test_member(email="invalid-email")
```

## Debugging Tests

### Enable Verbose Output

```bash
python -m tests.run_tests --all -v
```

### Run Single Test Method

```bash
python -m unittest tests.test_member.TestSACCOMember.test_member_creation -v
```

### Enable SQL Logging

Edit `test_config.py`:
```python
TEST_SETTINGS = {
    "show_sql_queries": True
}
```

## Common Issues

### Issue: Database Connection Error

**Solution**: Ensure Frappe is properly initialized:
```bash
bench setup
```

### Issue: Test Fixtures Not Created

**Solution**: Manually run setup:
```python
from tests.test_config import setup_test_environment
setup_test_environment()
```

### Issue: Tests Timing Out

**Solution**: Increase timeout in `test_config.py`:
```python
TEST_SETTINGS = {
    "max_execution_time": 600  # 10 minutes
}
```

## Test Data Management

### Creating Test Fixtures

```python
from tests.test_config import TEST_FIXTURES, create_test_fixtures

# Fixtures will be created automatically if enabled
TEST_SETTINGS["create_test_data"] = True
```

### Sample Test Data

The following test data is created automatically:
- Branches: Test Branch - Nairobi, Test Branch - Mombasa
- Loan Types: Normal Loan, Emergency Loan, Development Loan
- Share Types: Ordinary Shares, Preference Shares
- Payment Modes: Cash, Bank Transfer, Cheque, M-Pesa

## Performance Testing Guidelines

### When to Run Performance Tests

- After major code changes
- Before production deployment
- When adding new features
- Monthly regression testing

### Interpreting Results

Performance test output:
```
Bulk Member Creation Performance:
  Total members: 100
  Total time: 45.23s
  Average time per member: 452.30ms
  ✓ PASSED (threshold: 500ms)
```

### Optimizing Slow Tests

If tests exceed thresholds:
1. Check database indexes
2. Review SQL queries
3. Profile code execution
4. Consider caching strategies

## Support

For testing issues or questions:
- Check existing test files for examples
- Review test utilities in `test_utils.py`
- Consult Frappe testing documentation
- Contact development team

---

**Last Updated**: 2024-01-01  
**Version**: 1.0.0
