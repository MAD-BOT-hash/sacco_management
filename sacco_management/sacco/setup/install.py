import frappe
from frappe import _


def after_install():
    """Setup SACCO after installation"""
    create_roles()
    create_default_gl_accounts()
    create_default_payment_modes()
    create_default_contribution_types()
    create_default_loan_types()
    create_default_share_types()
    create_default_fine_types()
    frappe.db.commit()
    print("SACCO Management System installed successfully!")


def create_roles():
    """Create SACCO specific roles"""
    roles = [
        {
            "role_name": "SACCO Teller",
            "desk_access": 1,
            "description": "Can manage member contributions, basic transactions"
        },
        {
            "role_name": "SACCO Loan Officer", 
            "desk_access": 1,
            "description": "Can review and recommend loan applications"
        },
        {
            "role_name": "SACCO Branch Manager",
            "desk_access": 1,
            "description": "Can approve loans, manage branch operations"
        },
        {
            "role_name": "SACCO Admin",
            "desk_access": 1,
            "description": "Full access to SACCO management system"
        },
        {
            "role_name": "SACCO Auditor",
            "desk_access": 1,
            "description": "Read-only access for auditing purposes"
        }
    ]
    
    for role_data in roles:
        if not frappe.db.exists("Role", role_data["role_name"]):
            role = frappe.new_doc("Role")
            role.role_name = role_data["role_name"]
            role.desk_access = role_data["desk_access"]
            role.insert(ignore_permissions=True)
            print(f"Created role: {role_data['role_name']}")


def create_default_gl_accounts():
    """Create default Chart of Accounts for SACCO"""
    accounts = [
        # Assets
        {"account_name": "SACCO Assets", "account_type": "Asset", "is_group": 1, "account_number": "1000"},
        {"account_name": "Cash", "account_type": "Asset", "is_group": 0, "account_number": "1001", "parent_account": "SACCO Assets"},
        {"account_name": "Bank Account", "account_type": "Asset", "is_group": 0, "account_number": "1002", "parent_account": "SACCO Assets"},
        {"account_name": "Mobile Money", "account_type": "Asset", "is_group": 0, "account_number": "1003", "parent_account": "SACCO Assets"},
        {"account_name": "Loans Receivable", "account_type": "Asset", "is_group": 0, "account_number": "1100", "parent_account": "SACCO Assets"},
        {"account_name": "Interest Receivable", "account_type": "Asset", "is_group": 0, "account_number": "1101", "parent_account": "SACCO Assets"},
        {"account_name": "Fines Receivable", "account_type": "Asset", "is_group": 0, "account_number": "1102", "parent_account": "SACCO Assets"},
        
        # Liabilities
        {"account_name": "SACCO Liabilities", "account_type": "Liability", "is_group": 1, "account_number": "2000"},
        {"account_name": "Member Savings", "account_type": "Liability", "is_group": 0, "account_number": "2001", "parent_account": "SACCO Liabilities"},
        {"account_name": "Member Deposits", "account_type": "Liability", "is_group": 0, "account_number": "2002", "parent_account": "SACCO Liabilities"},
        {"account_name": "Dividends Payable", "account_type": "Liability", "is_group": 0, "account_number": "2100", "parent_account": "SACCO Liabilities"},
        
        # Equity
        {"account_name": "SACCO Equity", "account_type": "Equity", "is_group": 1, "account_number": "3000"},
        {"account_name": "Share Capital", "account_type": "Equity", "is_group": 0, "account_number": "3001", "parent_account": "SACCO Equity"},
        {"account_name": "Retained Earnings", "account_type": "Equity", "is_group": 0, "account_number": "3002", "parent_account": "SACCO Equity"},
        
        # Income
        {"account_name": "SACCO Income", "account_type": "Income", "is_group": 1, "account_number": "4000"},
        {"account_name": "Loan Interest Income", "account_type": "Income", "is_group": 0, "account_number": "4001", "parent_account": "SACCO Income"},
        {"account_name": "Processing Fee Income", "account_type": "Income", "is_group": 0, "account_number": "4002", "parent_account": "SACCO Income"},
        {"account_name": "Fine Income", "account_type": "Income", "is_group": 0, "account_number": "4003", "parent_account": "SACCO Income"},
        {"account_name": "Penalty Income", "account_type": "Income", "is_group": 0, "account_number": "4004", "parent_account": "SACCO Income"},
        {"account_name": "Membership Fee Income", "account_type": "Income", "is_group": 0, "account_number": "4005", "parent_account": "SACCO Income"},
        
        # Expenses
        {"account_name": "SACCO Expenses", "account_type": "Expense", "is_group": 1, "account_number": "5000"},
        {"account_name": "Interest Expense", "account_type": "Expense", "is_group": 0, "account_number": "5001", "parent_account": "SACCO Expenses"},
        {"account_name": "Dividend Expense", "account_type": "Expense", "is_group": 0, "account_number": "5002", "parent_account": "SACCO Expenses"},
        {"account_name": "Operating Expenses", "account_type": "Expense", "is_group": 0, "account_number": "5003", "parent_account": "SACCO Expenses"},
    ]
    
    for acc_data in accounts:
        if not frappe.db.exists("SACCO GL Account", {"account_name": acc_data["account_name"]}):
            acc = frappe.new_doc("SACCO GL Account")
            acc.account_name = acc_data["account_name"]
            acc.account_type = acc_data["account_type"]
            acc.account_number = acc_data["account_number"]
            acc.is_group = acc_data.get("is_group", 0)
            if acc_data.get("parent_account"):
                parent = frappe.db.get_value("SACCO GL Account", {"account_name": acc_data["parent_account"]}, "name")
                acc.parent_account = parent
            acc.insert(ignore_permissions=True)
            print(f"Created GL Account: {acc_data['account_name']}")


def create_default_payment_modes():
    """Create default payment modes"""
    modes = [
        {"mode_name": "Cash", "gl_account": "Cash", "is_active": 1},
        {"mode_name": "Bank Transfer", "gl_account": "Bank Account", "is_active": 1},
        {"mode_name": "Mobile Money", "gl_account": "Mobile Money", "is_active": 1},
        {"mode_name": "Cheque", "gl_account": "Bank Account", "is_active": 1},
    ]
    
    for mode_data in modes:
        if not frappe.db.exists("Payment Mode", mode_data["mode_name"]):
            mode = frappe.new_doc("Payment Mode")
            mode.mode_name = mode_data["mode_name"]
            mode.is_active = mode_data["is_active"]
            # Link GL account after it's created
            gl_account = frappe.db.get_value("SACCO GL Account", {"account_name": mode_data["gl_account"]}, "name")
            if gl_account:
                mode.gl_account = gl_account
            mode.insert(ignore_permissions=True)
            print(f"Created Payment Mode: {mode_data['mode_name']}")


def create_default_contribution_types():
    """Create default contribution types"""
    types = [
        {
            "contribution_name": "Monthly Savings",
            "code": "SAV",
            "is_mandatory": 1,
            "minimum_amount": 500,
            "interest_applicable": 1,
            "interest_rate": 5.0,
            "gl_account": "Member Savings"
        },
        {
            "contribution_name": "Registration Fee",
            "code": "REG",
            "is_mandatory": 1,
            "is_one_time": 1,
            "minimum_amount": 1000,
            "interest_applicable": 0,
            "gl_account": "Membership Fee Income"
        },
        {
            "contribution_name": "Development Fund",
            "code": "DEV",
            "is_mandatory": 0,
            "minimum_amount": 100,
            "interest_applicable": 0,
            "gl_account": "Member Deposits"
        },
        {
            "contribution_name": "Emergency Fund",
            "code": "EMG",
            "is_mandatory": 0,
            "minimum_amount": 200,
            "interest_applicable": 1,
            "interest_rate": 3.0,
            "gl_account": "Member Deposits"
        },
    ]
    
    for type_data in types:
        if not frappe.db.exists("Contribution Type", {"contribution_name": type_data["contribution_name"]}):
            ct = frappe.new_doc("Contribution Type")
            ct.contribution_name = type_data["contribution_name"]
            ct.code = type_data["code"]
            ct.is_mandatory = type_data.get("is_mandatory", 0)
            ct.is_one_time = type_data.get("is_one_time", 0)
            ct.minimum_amount = type_data.get("minimum_amount", 0)
            ct.interest_applicable = type_data.get("interest_applicable", 0)
            ct.interest_rate = type_data.get("interest_rate", 0)
            gl_account = frappe.db.get_value("SACCO GL Account", {"account_name": type_data["gl_account"]}, "name")
            if gl_account:
                ct.default_gl_account = gl_account
            ct.insert(ignore_permissions=True)
            print(f"Created Contribution Type: {type_data['contribution_name']}")


def create_default_loan_types():
    """Create default loan types"""
    types = [
        {
            "loan_name": "Normal Loan",
            "code": "NL",
            "interest_rate": 12.0,
            "interest_method": "Reducing Balance",
            "max_amount": 500000,
            "min_amount": 10000,
            "max_tenure_months": 24,
            "min_tenure_months": 3,
            "processing_fee_percent": 1.0,
            "requires_guarantors": 1,
            "min_guarantors": 2,
            "max_loan_multiplier": 3.0,  # 3x savings
            "min_contribution_months": 6,
            "gl_account": "Loans Receivable"
        },
        {
            "loan_name": "Emergency Loan",
            "code": "EL",
            "interest_rate": 15.0,
            "interest_method": "Flat Rate",
            "max_amount": 100000,
            "min_amount": 5000,
            "max_tenure_months": 6,
            "min_tenure_months": 1,
            "processing_fee_percent": 2.0,
            "requires_guarantors": 1,
            "min_guarantors": 1,
            "max_loan_multiplier": 1.5,
            "min_contribution_months": 3,
            "gl_account": "Loans Receivable"
        },
        {
            "loan_name": "Development Loan",
            "code": "DL",
            "interest_rate": 10.0,
            "interest_method": "Reducing Balance",
            "max_amount": 1000000,
            "min_amount": 50000,
            "max_tenure_months": 36,
            "min_tenure_months": 6,
            "processing_fee_percent": 1.5,
            "requires_guarantors": 1,
            "min_guarantors": 3,
            "requires_collateral": 1,
            "max_loan_multiplier": 5.0,
            "min_contribution_months": 12,
            "gl_account": "Loans Receivable"
        },
    ]
    
    for type_data in types:
        if not frappe.db.exists("Loan Type", {"loan_name": type_data["loan_name"]}):
            lt = frappe.new_doc("Loan Type")
            for key, value in type_data.items():
                if key != "gl_account":
                    setattr(lt, key, value)
            gl_account = frappe.db.get_value("SACCO GL Account", {"account_name": type_data["gl_account"]}, "name")
            if gl_account:
                lt.default_gl_account = gl_account
            lt.insert(ignore_permissions=True)
            print(f"Created Loan Type: {type_data['loan_name']}")


def create_default_share_types():
    """Create default share types"""
    types = [
        {
            "share_name": "Ordinary Shares",
            "code": "ORD",
            "price_per_share": 100,
            "min_shares": 10,
            "max_shares": 10000,
            "dividend_eligible": 1,
            "transferable": 1,
            "gl_account": "Share Capital"
        },
        {
            "share_name": "Preference Shares",
            "code": "PREF",
            "price_per_share": 500,
            "min_shares": 5,
            "max_shares": 1000,
            "dividend_eligible": 1,
            "fixed_dividend_rate": 8.0,
            "transferable": 0,
            "gl_account": "Share Capital"
        },
    ]
    
    for type_data in types:
        if not frappe.db.exists("Share Type", {"share_name": type_data["share_name"]}):
            st = frappe.new_doc("Share Type")
            for key, value in type_data.items():
                if key != "gl_account":
                    setattr(st, key, value)
            gl_account = frappe.db.get_value("SACCO GL Account", {"account_name": type_data["gl_account"]}, "name")
            if gl_account:
                st.default_gl_account = gl_account
            st.insert(ignore_permissions=True)
            print(f"Created Share Type: {type_data['share_name']}")


def create_default_fine_types():
    """Create default fine types"""
    types = [
        {
            "fine_name": "Late Payment Penalty",
            "code": "LPP",
            "default_amount": 500,
            "is_percentage": 1,
            "percentage_rate": 5.0,
            "auto_apply": 1,
            "apply_after_days": 7,
            "gl_account": "Penalty Income"
        },
        {
            "fine_name": "Meeting Absence Fine",
            "code": "MAF",
            "default_amount": 200,
            "is_percentage": 0,
            "auto_apply": 0,
            "gl_account": "Fine Income"
        },
        {
            "fine_name": "Late Contribution Fine",
            "code": "LCF",
            "default_amount": 100,
            "is_percentage": 0,
            "auto_apply": 1,
            "apply_after_days": 5,
            "gl_account": "Fine Income"
        },
        {
            "fine_name": "Bounced Cheque Fee",
            "code": "BCF",
            "default_amount": 1000,
            "is_percentage": 0,
            "auto_apply": 0,
            "gl_account": "Fine Income"
        },
    ]
    
    for type_data in types:
        if not frappe.db.exists("Fine Type", {"fine_name": type_data["fine_name"]}):
            ft = frappe.new_doc("Fine Type")
            for key, value in type_data.items():
                if key != "gl_account":
                    setattr(ft, key, value)
            gl_account = frappe.db.get_value("SACCO GL Account", {"account_name": type_data["gl_account"]}, "name")
            if gl_account:
                ft.default_gl_account = gl_account
            ft.insert(ignore_permissions=True)
            print(f"Created Fine Type: {type_data['fine_name']}")
