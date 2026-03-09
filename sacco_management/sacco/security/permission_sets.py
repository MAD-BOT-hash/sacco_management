"""
Enhanced Permission Sets and Roles Configuration

This module defines custom roles and permission sets for the SACCO system:
- API-specific roles
- Department-based permission sets
- Function-based permission sets
- Field-level security configurations
"""

import frappe
from frappe import _


def get_role_definitions():
    """
    Define custom roles for the SACCO system
    
    Returns:
        dict: Role definitions with descriptions
    """
    return {
        # Core System Roles
        "SACCO Admin": {
            "description": "Full system administrator access",
            "level": "admin"
        },
        "System Manager": {
            "description": "Technical system management",
            "level": "admin"
        },
        
        # Management Roles
        "Branch Manager": {
            "description": "Full branch operations management",
            "level": "manager"
        },
        "Credit Committee": {
            "description": "Loan approval authority",
            "level": "approver"
        },
        "Board Member": {
            "description": "Board-level oversight and approvals",
            "level": "approver"
        },
        
        # Operational Roles
        "Loan Officer": {
            "description": "Loan processing and member services",
            "level": "officer"
        },
        "Accountant": {
            "description": "Financial transactions and reporting",
            "level": "officer"
        },
        "Cashier": {
            "description": "Cash handling and deposits",
            "level": "clerk"
        },
        "Front Office": {
            "description": "Member registration and basic services",
            "level": "clerk"
        },
        
        # Member Services
        "Member": {
            "description": "Basic member self-service access",
            "level": "member"
        },
        
        # Audit & Compliance
        "Internal Auditor": {
            "description": "Read-only audit access",
            "level": "auditor"
        },
        "External Auditor": {
            "description": "Limited external audit access",
            "level": "auditor"
        },
        "Compliance Officer": {
            "description": "Regulatory compliance monitoring",
            "level": "officer"
        },
        
        # API Access Roles
        "API User": {
            "description": "Basic API access",
            "level": "api"
        },
        "API Admin": {
            "description": "API management and monitoring",
            "level": "api_admin"
        }
    }


def get_permission_sets():
    """
    Define permission sets (groups of permissions)
    
    Returns:
        dict: Permission set definitions
    """
    return {
        # Member Management Permission Sets
        "Member View": {
            "doctype": "SACCO Member",
            "permissions": ["read"]
        },
        "Member Create": {
            "doctype": "SACCO Member",
            "permissions": ["create"]
        },
        "Member Edit": {
            "doctype": "SACCO Member",
            "permissions": ["read", "write"]
        },
        "Member Delete": {
            "doctype": "SACCO Member",
            "permissions": ["read", "delete"]
        },
        
        # Loan Management Permission Sets
        "Loan View": {
            "doctype": "Loan Application",
            "permissions": ["read"]
        },
        "Loan Create": {
            "doctype": "Loan Application",
            "permissions": ["read", "create"]
        },
        "Loan Approve": {
            "doctype": "Loan Application",
            "permissions": ["read", "write", "submit"]
        },
        "Loan Disburse": {
            "doctype": "Loan Disbursement",
            "permissions": ["read", "create", "submit"]
        },
        "Loan Repayment Process": {
            "doctype": "Loan Repayment",
            "permissions": ["read", "create", "submit"]
        },
        
        # Savings Management Permission Sets
        "Savings View": {
            "doctype": "Savings Account",
            "permissions": ["read"]
        },
        "Savings Transaction": {
            "doctype": ["Savings Deposit", "Savings Withdrawal"],
            "permissions": ["read", "create", "submit"]
        },
        
        # Share Management Permission Sets
        "Share View": {
            "doctype": "Share Allocation",
            "permissions": ["read"]
        },
        "Share Purchase": {
            "doctype": "Share Purchase",
            "permissions": ["read", "create", "submit"]
        },
        "Share Redemption Approve": {
            "doctype": "Share Redemption",
            "permissions": ["read", "write", "submit"]
        },
        
        # Dividend Management Permission Sets
        "Dividend View": {
            "doctype": ["Dividend Calculation", "Dividend Ledger"],
            "permissions": ["read"]
        },
        "Dividend Process": {
            "doctype": ["Dividend Period", "Dividend Declaration"],
            "permissions": ["read", "create", "submit"]
        },
        
        # Accounting Permission Sets
        "Journal Entry Create": {
            "doctype": "SACCO Journal Entry",
            "permissions": ["read", "create", "submit"]
        },
        "GL Report View": {
            "doctype": "General Ledger",
            "permissions": ["read"]
        },
        "Financial Reports": {
            "doctype": ["Trial Balance", "Profit and Loss Statement"],
            "permissions": ["read"]
        },
        
        # Meeting Management Permission Sets
        "Meeting View": {
            "doctype": ["SACCO Meeting", "Meeting Register"],
            "permissions": ["read"]
        },
        "Meeting Organize": {
            "doctype": "SACCO Meeting",
            "permissions": ["read", "create", "write", "submit"]
        },
        "Resolution Pass": {
            "doctype": "Meeting Resolution",
            "permissions": ["read", "create", "submit"]
        },
        
        # Fine Management Permission Sets
        "Fine View": {
            "doctype": ["Member Fine", "Fine Payment"],
            "permissions": ["read"]
        },
        "Fine Apply": {
            "doctype": "Member Fine",
            "permissions": ["read", "create", "submit"]
        },
        "Fine Waiver Approve": {
            "doctype": "Fine Waiver",
            "permissions": ["read", "write", "submit"]
        },
        
        # Report Permission Sets
        "Operational Reports": {
            "doctype": "Report",
            "permissions": ["read"],
            "restricted_to": ["Branch Performance Report", "Loan Performance Report"]
        },
        "Advanced Analytics": {
            "doctype": "Report",
            "permissions": ["read"],
            "restricted_to": ["Advanced Member Analytics", "Portfolio at Risk Report", "Liquidity Analysis Report"]
        },
        
        # API Permission Sets
        "API Basic Access": {
            "doctype": "API Endpoint",
            "permissions": ["read"],
            "endpoints": ["get_members", "get_member", "get_loans", "get_loan"]
        },
        "API Transaction Access": {
            "doctype": "API Endpoint",
            "permissions": ["read", "write"],
            "endpoints": ["create_*", "update_*", "process_*"]
        },
        "API Admin Access": {
            "doctype": "API Endpoint",
            "permissions": ["read", "write", "delete"]
        }
    }


def get_role_permission_matrix():
    """
    Define which permission sets each role should have
    
    Returns:
        dict: Role to permission set mapping
    """
    return {
        "SACCO Admin": "all",
        
        "Branch Manager": [
            "Member Edit", "Loan View", "Loan Approve",
            "Savings View", "Savings Transaction",
            "Share View", "Dividend View",
            "Journal Entry Create", "Financial Reports",
            "Meeting Organize", "Fine View", "Fine Waiver Approve",
            "Advanced Analytics"
        ],
        
        "Credit Committee": [
            "Member View", "Loan View", "Loan Approve",
            "Advanced Analytics"
        ],
        
        "Board Member": [
            "Member View", "Loan View", "Savings View",
            "Share View", "Dividend View", "Financial Reports",
            "Advanced Analytics", "Meeting View", "Resolution Pass"
        ],
        
        "Loan Officer": [
            "Member Edit", "Loan Create", "Loan View",
            "Loan Disburse", "Loan Repayment Process",
            "Savings View", "Savings Transaction",
            "Share View", "Fine View", "Fine Apply"
        ],
        
        "Accountant": [
            "Member View", "Loan View", "Loan Repayment Process",
            "Savings View", "Savings Transaction",
            "Share View", "Share Purchase",
            "Dividend Process", "Journal Entry Create",
            "GL Report View", "Financial Reports"
        ],
        
        "Cashier": [
            "Member View", "Savings Transaction",
            "Share Purchase", "Fine View"
        ],
        
        "Front Office": [
            "Member Create", "Member View",
            "Loan View", "Loan Create",
            "Savings View"
        ],
        
        "Member": [
            "Member View",  # Can only view own profile
            "Loan View", "Loan Create",  # Can apply for loans
            "Savings View", "Savings Transaction",  # Can transact on own savings
            "Share View", "Share Purchase"  # Can purchase shares
        ],
        
        "Internal Auditor": [
            "Member View", "Loan View", "Savings View",
            "Share View", "Dividend View",
            "GL Report View", "Financial Reports",
            "Advanced Analytics", "Meeting View"
        ],
        
        "External Auditor": [
            "Member View", "Loan View", "Savings View",
            "Financial Reports"
        ],
        
        "Compliance Officer": [
            "Member View", "Loan View", "Savings View",
            "Share View", "Dividend View",
            "Advanced Analytics", "Financial Reports"
        ],
        
        "API User": [
            "API Basic Access"
        ],
        
        "API Admin": [
            "API Admin Access"
        ]
    }


def create_custom_roles():
    """Create custom roles if they don't exist"""
    roles = get_role_definitions()
    
    for role_name in roles.keys():
        if not frappe.db.exists("Role", role_name):
            doc = frappe.new_doc("Role")
            doc.role_name = role_name
            doc.desk_access = 1
            doc.insert(ignore_permissions=True)
            frappe.log_error(f"Created role: {role_name}")
    
    return list(roles.keys())


def setup_field_level_security():
    """Configure field-level security for sensitive fields"""
    
    field_restrictions = {
        "SACCO Member": {
            "national_id": ["SACCO Admin", "Branch Manager", "Compliance Officer"],
            "pin_number": ["SACCO Admin", "Accountant", "Compliance Officer"],
            "bank_account": ["SACCO Admin", "Accountant"],
            "total_savings": ["SACCO Admin", "Branch Manager", "Accountant"],
            "total_shares": ["SACCO Admin", "Branch Manager", "Accountant"],
            "total_dividend_received": ["SACCO Admin", "Branch Manager", "Accountant"]
        },
        "Loan Application": {
            "credit_score": ["SACCO Admin", "Credit Committee", "Branch Manager"],
            "approval_comments": ["SACCO Admin", "Credit Committee", "Branch Manager"],
            "guarantor_details": ["SACCO Admin", "Credit Committee", "Loan Officer"]
        },
        "Savings Account": {
            "current_balance": ["SACCO Admin", "Branch Manager", "Accountant", "Owner"]
        }
    }
    
    return field_restrictions


@frappe.whitelist()
def initialize_security_setup():
    """Initialize complete security setup"""
    
    # Create roles
    roles = create_custom_roles()
    
    # Get permission sets
    permission_sets = get_permission_sets()
    
    # Get role matrix
    role_matrix = get_role_permission_matrix()
    
    # Setup field-level security
    field_security = setup_field_level_security()
    
    return api_response(
        success=True,
        data={
            "roles_created": len(roles),
            "permission_sets": len(permission_sets),
            "role_mappings": len(role_matrix),
            "field_restrictions": len(field_security)
        },
        message="Security setup initialized successfully"
    )


# Helper function for API responses
def api_response(success=True, data=None, message=None):
    return {
        "success": success,
        "data": data or {},
        "message": message or ""
    }
