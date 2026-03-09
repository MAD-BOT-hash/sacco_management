"""
Test Utilities for SACCO Management System

This module provides base test classes, fixtures, and utility functions
for unit and integration testing.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate, add_months, flt
import unittest


class SACCOBaseTestCase(FrappeTestCase):
    """
    Base test case class for all SACCO tests
    
    Provides common setup, teardown, and helper methods
    """
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_test_data()
    
    @classmethod
    def tearDownClass(cls):
        cls.cleanup_test_data()
        super().tearDownClass()
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        frappe.set_user("Administrator")
    
    def tearDown(self):
        """Tear down test fixtures after each test method"""
        frappe.db.rollback()
    
    @classmethod
    def setup_test_data(cls):
        """Setup common test data - override in subclasses"""
        pass
    
    @classmethod
    def cleanup_test_data(cls):
        """Cleanup test data - override in subclasses"""
        pass
    
    def assertResponseSuccess(self, response):
        """Assert that API response indicates success"""
        self.assertTrue(response.get("success"))
        self.assertEqual(response.get("status_code"), 200)
    
    def assertResponseError(self, response, expected_error=None):
        """Assert that API response indicates error"""
        self.assertFalse(response.get("success"))
        self.assertIn("errors", response)
        
        if expected_error:
            errors = response.get("errors", [])
            self.assertTrue(
                any(expected_error.lower() in str(e).lower() for e in errors),
                f"Expected error containing '{expected_error}', got: {errors}"
            )
    
    def create_test_member(self, **kwargs):
        """Helper to create test member"""
        member_data = {
            "member_name": kwargs.get("member_name", "Test Member"),
            "email": kwargs.get("email", f"test_{frappe.generate_hash()[:8]}@example.com"),
            "membership_type": kwargs.get("membership_type", "Ordinary"),
            "membership_status": kwargs.get("membership_status", "Active"),
            "joining_date": kwargs.get("joining_date", nowdate()),
            "branch": kwargs.get("branch"),
        }
        
        member = frappe.new_doc("SACCO Member")
        member.update(member_data)
        member.insert(ignore_permissions=True)
        
        return member
    
    def create_test_savings_account(self, member, **kwargs):
        """Helper to create test savings account"""
        account_data = {
            "member": member.name,
            "account_type": kwargs.get("account_type", "Regular Savings"),
            "status": kwargs.get("status", "Active"),
        }
        
        account = frappe.new_doc("Savings Account")
        account.update(account_data)
        account.insert(ignore_permissions=True)
        
        return account
    
    def create_test_loan_application(self, member, **kwargs):
        """Helper to create test loan application"""
        loan_data = {
            "member": member.name,
            "loan_type": kwargs.get("loan_type", "Normal Loan"),
            "amount_requested": kwargs.get("amount_requested", 100000),
            "interest_rate": kwargs.get("interest_rate", 12),
            "repayment_period": kwargs.get("repayment_period", 12),
            "application_date": kwargs.get("application_date", nowdate()),
        }
        
        loan = frappe.new_doc("Loan Application")
        loan.update(loan_data)
        loan.insert(ignore_permissions=True)
        
        return loan
    
    def create_test_share_allocation(self, member, **kwargs):
        """Helper to create test share allocation"""
        allocation_data = {
            "member": member.name,
            "share_type": kwargs.get("share_type", "Ordinary Shares"),
            "quantity": kwargs.get("quantity", 100),
            "total_amount": kwargs.get("total_amount", 10000),
            "allocation_date": kwargs.get("allocation_date", nowdate()),
        }
        
        allocation = frappe.new_doc("Share Allocation")
        allocation.update(allocation_data)
        allocation.insert(ignore_permissions=True)
        allocation.submit()
        
        return allocation


class APITestCase(SACCOBaseTestCase):
    """
    Base test case for API testing
    
    Provides API client and authentication helpers
    """
    
    def setUp(self):
        super().setUp()
        self.api_base = "/api/method/sacco_management.sacco.api"
    
    def get_api_endpoint(self, endpoint):
        """Get full API endpoint URL"""
        return f"{self.api_base}.{endpoint}"
    
    def make_api_call(self, method, endpoint, **kwargs):
        """
        Make API call using Frappe's test client
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint name
            **kwargs: Parameters to pass to the endpoint
        
        Returns:
            dict: API response
        """
        from frappe.tests.utils import make_get_request, make_post_request, make_put_request, make_delete_request
        
        url = self.get_api_endpoint(endpoint)
        
        request_methods = {
            "GET": make_get_request,
            "POST": make_post_request,
            "PUT": make_put_request,
            "DELETE": make_delete_request
        }
        
        if method not in request_methods:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        try:
            response = request_methods[method](url, **kwargs)
            return response
        except Exception as e:
            # Return error response
            return {
                "success": False,
                "errors": [str(e)]
            }


class DatabaseTestCase(SACCOBaseTestCase):
    """
    Test case for database-level tests
    
    Provides transaction management and query helpers
    """
    
    def setUp(self):
        super().setUp()
        self._transaction = frappe.db.transaction()
    
    def tearDown(self):
        if hasattr(self, '_transaction'):
            self._transaction.rollback()
        super().tearDown()
    
    def count_records(self, doctype, filters=None):
        """Count records matching filters"""
        return frappe.db.count(doctype, filters=filters or {})
    
    def exists(self, doctype, filters):
        """Check if record exists"""
        return frappe.db.exists(doctype, filters)


def run_test_suite(test_class, test_method_pattern=None):
    """
    Run test suite programmatically
    
    Args:
        test_class: Test class to run
        test_method_pattern: Optional pattern to filter test methods
    
    Returns:
        TestResult object
    """
    loader = unittest.TestLoader()
    
    if test_method_pattern:
        suite = loader.loadTestsFromName(test_method_pattern, test_class)
    else:
        suite = loader.loadTestsFromTestCase(test_class)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


def create_test_fixtures():
    """Create common test fixtures"""
    
    fixtures = {
        "branches": [],
        "members": [],
        "loan_types": [],
        "share_types": []
    }
    
    # Create test branch if not exists
    if not frappe.db.exists("Branch", "Test Branch"):
        branch = frappe.new_doc("Branch")
        branch.branch_name = "Test Branch"
        branch.insert(ignore_permissions=True)
        fixtures["branches"].append(branch.name)
    
    # Create test user
    if not frappe.db.exists("User", "testuser@sacco.com"):
        user = frappe.new_doc("User")
        user.email = "testuser@sacco.com"
        user.first_name = "Test"
        user.user_type = "System User"
        user.append("roles", {"role": "SACCO Admin"})
        user.insert(ignore_permissions=True)
    
    return fixtures


def cleanup_test_fixtures():
    """Cleanup test fixtures"""
    
    # Remove test branch
    branch = frappe.db.exists("Branch", "Test Branch")
    if branch:
        frappe.delete_doc("Branch", branch, force=True)
    
    # Remove test user
    user = frappe.db.exists("User", "testuser@sacco.com")
    if user:
        frappe.delete_doc("User", user, force=True)
    
    frappe.db.commit()


# Decorator for skipping tests in production
def skip_in_production(func):
    """Skip test when running in production"""
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        if frappe.flags.in_test:
            return func(*args, **kwargs)
        else:
            raise unittest.SkipTest("Skipping test in non-test environment")
    
    return wrapper
