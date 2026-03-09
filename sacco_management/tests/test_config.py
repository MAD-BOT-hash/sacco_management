"""
Test Configuration for SACCO Management System

Configure test database, fixtures, and settings
"""

import frappe
import os


# Test Database Configuration
TEST_DB_NAME = "test_sacco_db"
TEST_DB_PASSWORD = os.environ.get("TEST_DB_PASSWORD", "admin")

# Test Settings
TEST_SETTINGS = {
    "create_test_data": True,
    "cleanup_after_tests": True,
    "show_sql_queries": False,
    "enable_performance_profiling": True,
    "max_execution_time": 300  # seconds
}

# Test Fixtures
TEST_FIXTURES = {
    "branches": ["Test Branch - Nairobi", "Test Branch - Mombasa"],
    "loan_types": ["Normal Loan", "Emergency Loan", "Development Loan"],
    "share_types": ["Ordinary Shares", "Preference Shares"],
    "payment_modes": ["Cash", "Bank Transfer", "Cheque", "M-Pesa"]
}


def setup_test_environment():
    """Setup test environment"""
    print("Setting up test environment...")
    
    # Set test flags
    frappe.flags.in_test = True
    frappe.flags.test_data_created = False
    
    # Create test roles if they don't exist
    create_test_roles()
    
    # Create test fixtures
    create_test_fixtures()
    
    print("Test environment setup complete!")


def teardown_test_environment():
    """Cleanup test environment"""
    print("Tearing down test environment...")
    
    if TEST_SETTINGS.get("cleanup_after_tests"):
        cleanup_test_fixtures()
    
    print("Test environment teardown complete!")


def create_test_roles():
    """Create test roles"""
    test_roles = [
        "SACCO Admin",
        "Loan Officer",
        "Accountant",
        "Member",
        "Credit Committee"
    ]
    
    for role_name in test_roles:
        if not frappe.db.exists("Role", role_name):
            role = frappe.new_doc("Role")
            role.role_name = role_name
            role.desk_access = 1
            role.insert(ignore_permissions=True)
            print(f"Created role: {role_name}")


def create_test_fixtures():
    """Create common test fixtures"""
    
    # Create test branches
    for branch_name in TEST_FIXTURES["branches"]:
        if not frappe.db.exists("Branch", branch_name):
            branch = frappe.new_doc("Branch")
            branch.branch_name = branch_name
            branch.insert(ignore_permissions=True)
            print(f"Created branch: {branch_name}")
    
    # Create test loan types
    for loan_type in TEST_FIXTURES["loan_types"]:
        if not frappe.db.exists("Loan Type", loan_type):
            lt = frappe.new_doc("Loan Type")
            lt.loan_type_name = loan_type
            lt.insert(ignore_permissions=True)
            print(f"Created loan type: {loan_type}")
    
    # Create test share types
    for share_type in TEST_FIXTURES["share_types"]:
        if not frappe.db.exists("Share Type", share_type):
            st = frappe.new_doc("Share Type")
            st.share_type_name = share_type
            st.insert(ignore_permissions=True)
            print(f"Created share type: {share_type}")
    
    # Create test payment modes
    for payment_mode in TEST_FIXTURES["payment_modes"]:
        if not frappe.db.exists("Payment Mode", payment_mode):
            pm = frappe.new_doc("Payment Mode")
            pm.payment_mode_name = payment_mode
            pm.insert(ignore_permissions=True)
            print(f"Created payment mode: {payment_mode}")
    
    frappe.db.commit()


def cleanup_test_fixtures():
    """Cleanup test fixtures"""
    print("Cleaning up test fixtures...")
    
    # Remove test branches
    for branch_name in TEST_FIXTURES["branches"]:
        branch = frappe.db.exists("Branch", branch_name)
        if branch:
            frappe.delete_doc("Branch", branch, force=True)
    
    # Remove test loan types
    for loan_type in TEST_FIXTURES["loan_types"]:
            lt = frappe.db.exists("Loan Type", loan_type)
            if lt:
                frappe.delete_doc("Loan Type", lt, force=True)
    
    # Remove test share types
    for share_type in TEST_FIXTURES["share_types"]:
        st = frappe.db.exists("Share Type", share_type)
        if st:
            frappe.delete_doc("Share Type", st, force=True)
    
    # Remove test payment modes
    for payment_mode in TEST_FIXTURES["payment_modes"]:
        pm = frappe.db.exists("Payment Mode", payment_mode)
        if pm:
            frappe.delete_doc("Payment Mode", pm, force=True)
    
    frappe.db.commit()


def get_test_user():
    """Get or create test user"""
    test_email = "testuser@sacco.com"
    
    if not frappe.db.exists("User", test_email):
        user = frappe.new_doc("User")
        user.email = test_email
        user.first_name = "Test"
        user.user_type = "System User"
        user.append("roles", {"role": "SACCO Admin"})
        user.insert(ignore_permissions=True)
    
    return test_email


# Performance Test Configuration
PERFORMANCE_THRESHOLDS = {
    "member_creation_ms": 500,
    "loan_calculation_ms": 50,
    "api_response_ms": 500,
    "database_query_ms": 200,
    "search_operation_ms": 100
}


# Coverage Configuration
COVERAGE_CONFIG = {
    "source": ["sacco_management.sacco"],
    "omit": [
        "*/tests/*",
        "*/node_modules/*",
        "*/__init__.py"
    ],
    "include": [
        "*/doctype/*",
        "*/api/*",
        "*/utils/*",
        "*/report/*"
    ]
}
