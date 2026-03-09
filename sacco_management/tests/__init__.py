"""
SACCO Management System - Test Suite

Comprehensive testing framework for the SACCO Management System.

Test Structure:
- test_utils.py: Base test classes and utilities
- test_member.py: Member module unit tests
- test_loan.py: Loan module unit tests
- test_savings_shares.py: Savings & Shares module tests
- test_integration.py: API integration tests
- test_performance.py: Performance and load tests
- run_tests.py: Test runner and reporter
- test_config.py: Test configuration

Usage:
    # Run all tests
    python -m tests.run_tests --all
    
    # Run specific module
    python -m tests.run_tests --module member
    
    # Run performance tests
    python -m tests.run_tests --performance
    
    # Generate HTML report
    python -m tests.run_tests --all --report
"""

from .test_utils import (
    SACCOBaseTestCase,
    APITestCase,
    DatabaseTestCase,
    run_test_suite,
    create_test_fixtures,
    cleanup_test_fixtures
)

from .test_config import (
    setup_test_environment,
    teardown_test_environment,
    TEST_SETTINGS,
    PERFORMANCE_THRESHOLDS
)

__all__ = [
    'SACCOBaseTestCase',
    'APITestCase',
    'DatabaseTestCase',
    'run_test_suite',
    'create_test_fixtures',
    'cleanup_test_fixtures',
    'setup_test_environment',
    'teardown_test_environment',
    'TEST_SETTINGS',
    'PERFORMANCE_THRESHOLDS'
]
