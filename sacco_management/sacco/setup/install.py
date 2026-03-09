import frappe
from frappe import _


def after_install():
    """Setup SACCO after installation - creates default data"""
    try:
        # Check if DocTypes have been created (only run after migrate)
        if not frappe.db.exists("DocType", "SACCO GL Account"):
            print("SACCO DocTypes not yet created. Run 'bench migrate' first, then 'bench execute sacco_management.sacco.setup.install.setup_sacco_data'")
            return
        
        setup_sacco_data()
    except Exception as e:
        print(f"SACCO setup will complete after migration. Error: {str(e)}")


def setup_sacco_data():
    """Create default SACCO data - call this after migrate"""
    print("Setting up SACCO Management System...")
    
    create_roles()
    
    # Only create data if DocTypes exist
    if frappe.db.exists("DocType", "SACCO GL Account"):
        create_default_gl_accounts()
    
    if frappe.db.exists("DocType", "Payment Mode"):
        create_default_payment_modes()
    
    if frappe.db.exists("DocType", "Contribution Type"):
        create_default_contribution_types()
    
    if frappe.db.exists("DocType", "Loan Type"):
        create_default_loan_types()
    
    if frappe.db.exists("DocType", "Share Type"):
        create_default_share_types()
    
    if frappe.db.exists("DocType", "Fine Type"):
        create_default_fine_types()
    
    if frappe.db.exists("DocType", "Attendance Fine Type"):
        create_default_attendance_fine_types()
    
    if frappe.db.exists("DocType", "Savings Product"):
        create_default_savings_products()
    
    frappe.db.commit()
    print("SACCO Management System setup completed successfully!")


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
        try:
            if not frappe.db.exists("Role", role_data["role_name"]):
                role = frappe.new_doc("Role")
                role.role_name = role_data["role_name"]
                role.desk_access = role_data["desk_access"]
                role.insert(ignore_permissions=True)
                print(f"Created role: {role_data['role_name']}")
        except Exception as e:
            print(f"Error creating role {role_data['role_name']}: {str(e)}")


def create_default_gl_accounts():
    """Create default Chart of Accounts for SACCO"""
    accounts = [
        # Assets
        {"account_name": "SACCO Assets", "account_type": "Asset", "is_group": 1, "account_number": "1000"},
        {"account_name": "Cash", "account_type": "Asset", "is_group": 0, "account_number": "1001", "parent_account": "1000-SACCO Assets"},
        {"account_name": "Bank Account", "account_type": "Asset", "is_group": 0, "account_number": "1002", "parent_account": "1000-SACCO Assets"},
        {"account_name": "Mobile Money", "account_type": "Asset", "is_group": 0, "account_number": "1003", "parent_account": "1000-SACCO Assets"},
        {"account_name": "Loans Receivable", "account_type": "Asset", "is_group": 0, "account_number": "1100", "parent_account": "1000-SACCO Assets"},
        {"account_name": "Interest Receivable", "account_type": "Asset", "is_group": 0, "account_number": "1101", "parent_account": "1000-SACCO Assets"},
        {"account_name": "Fines Receivable", "account_type": "Asset", "is_group": 0, "account_number": "1102", "parent_account": "1000-SACCO Assets"},
        
        # Liabilities
        {"account_name": "SACCO Liabilities", "account_type": "Liability", "is_group": 1, "account_number": "2000"},
        {"account_name": "Member Savings", "account_type": "Liability", "is_group": 0, "account_number": "2001", "parent_account": "2000-SACCO Liabilities"},
        {"account_name": "Member Deposits", "account_type": "Liability", "is_group": 0, "account_number": "2002", "parent_account": "2000-SACCO Liabilities"},
        {"account_name": "Dividends Payable", "account_type": "Liability", "is_group": 0, "account_number": "2100", "parent_account": "2000-SACCO Liabilities"},
        {"account_name": "Withholding Tax Payable", "account_type": "Liability", "is_group": 0, "account_number": "2101", "parent_account": "2000-SACCO Liabilities"},
        
        # Equity
        {"account_name": "SACCO Equity", "account_type": "Equity", "is_group": 1, "account_number": "3000"},
        {"account_name": "Share Capital", "account_type": "Equity", "is_group": 0, "account_number": "3001", "parent_account": "3000-SACCO Equity"},
        {"account_name": "Retained Earnings", "account_type": "Equity", "is_group": 0, "account_number": "3002", "parent_account": "3000-SACCO Equity"},
        
        # Income
        {"account_name": "SACCO Income", "account_type": "Income", "is_group": 1, "account_number": "4000"},
        {"account_name": "Loan Interest Income", "account_type": "Income", "is_group": 0, "account_number": "4001", "parent_account": "4000-SACCO Income"},
        {"account_name": "Processing Fee Income", "account_type": "Income", "is_group": 0, "account_number": "4002", "parent_account": "4000-SACCO Income"},
        {"account_name": "Fine Income", "account_type": "Income", "is_group": 0, "account_number": "4003", "parent_account": "4000-SACCO Income"},
        {"account_name": "Penalty Income", "account_type": "Income", "is_group": 0, "account_number": "4004", "parent_account": "4000-SACCO Income"},
        {"account_name": "Membership Fee Income", "account_type": "Income", "is_group": 0, "account_number": "4005", "parent_account": "4000-SACCO Income"},
        
        # Expenses
        {"account_name": "SACCO Expenses", "account_type": "Expense", "is_group": 1, "account_number": "5000"},
        {"account_name": "Interest Expense", "account_type": "Expense", "is_group": 0, "account_number": "5001", "parent_account": "5000-SACCO Expenses"},
        {"account_name": "Dividend Expense", "account_type": "Expense", "is_group": 0, "account_number": "5002", "parent_account": "5000-SACCO Expenses"},
        {"account_name": "Operating Expenses", "account_type": "Expense", "is_group": 0, "account_number": "5003", "parent_account": "5000-SACCO Expenses"},
    ]
    
    for acc_data in accounts:
        try:
            account_name_key = f"{acc_data['account_number']}-{acc_data['account_name']}"
            if not frappe.db.exists("SACCO GL Account", account_name_key):
                acc = frappe.new_doc("SACCO GL Account")
                acc.account_name = acc_data["account_name"]
                acc.account_type = acc_data["account_type"]
                acc.account_number = acc_data["account_number"]
                acc.is_group = acc_data.get("is_group", 0)
                if acc_data.get("parent_account"):
                    acc.parent_account = acc_data["parent_account"]
                acc.insert(ignore_permissions=True)
                print(f"Created GL Account: {acc_data['account_name']}")
        except Exception as e:
            print(f"Error creating GL Account {acc_data['account_name']}: {str(e)}")


def create_default_payment_modes():
    """Create default payment modes"""
    modes = [
        {"mode_name": "Cash", "gl_account_name": "Cash", "is_active": 1},
        {"mode_name": "Bank Transfer", "gl_account_name": "Bank Account", "is_active": 1},
        {"mode_name": "Mobile Money", "gl_account_name": "Mobile Money", "is_active": 1},
        {"mode_name": "Cheque", "gl_account_name": "Bank Account", "is_active": 1},
    ]
    
    for mode_data in modes:
        try:
            if not frappe.db.exists("Payment Mode", mode_data["mode_name"]):
                mode = frappe.new_doc("Payment Mode")
                mode.mode_name = mode_data["mode_name"]
                mode.is_active = mode_data["is_active"]
                # Link GL account
                gl_account = frappe.db.get_value("SACCO GL Account", 
                    {"account_name": mode_data["gl_account_name"]}, "name")
                if gl_account:
                    mode.gl_account = gl_account
                mode.insert(ignore_permissions=True)
                print(f"Created Payment Mode: {mode_data['mode_name']}")
        except Exception as e:
            print(f"Error creating Payment Mode {mode_data['mode_name']}: {str(e)}")


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
            "gl_account_name": "Member Savings"
        },
        {
            "contribution_name": "Registration Fee",
            "code": "REG",
            "is_mandatory": 1,
            "is_one_time": 1,
            "minimum_amount": 1000,
            "interest_applicable": 0,
            "gl_account_name": "Membership Fee Income"
        },
        {
            "contribution_name": "Development Fund",
            "code": "DEV",
            "is_mandatory": 0,
            "minimum_amount": 100,
            "interest_applicable": 0,
            "gl_account_name": "Member Deposits"
        },
        {
            "contribution_name": "Emergency Fund",
            "code": "EMG",
            "is_mandatory": 0,
            "minimum_amount": 200,
            "interest_applicable": 1,
            "interest_rate": 3.0,
            "gl_account_name": "Member Deposits"
        },
    ]
    
    for type_data in types:
        try:
            if not frappe.db.exists("Contribution Type", {"contribution_name": type_data["contribution_name"]}):
                ct = frappe.new_doc("Contribution Type")
                ct.contribution_name = type_data["contribution_name"]
                ct.code = type_data["code"]
                ct.is_mandatory = type_data.get("is_mandatory", 0)
                ct.is_one_time = type_data.get("is_one_time", 0)
                ct.minimum_amount = type_data.get("minimum_amount", 0)
                ct.interest_applicable = type_data.get("interest_applicable", 0)
                ct.interest_rate = type_data.get("interest_rate", 0)
                gl_account = frappe.db.get_value("SACCO GL Account", 
                    {"account_name": type_data["gl_account_name"]}, "name")
                if gl_account:
                    ct.default_gl_account = gl_account
                ct.insert(ignore_permissions=True)
                print(f"Created Contribution Type: {type_data['contribution_name']}")
        except Exception as e:
            print(f"Error creating Contribution Type {type_data['contribution_name']}: {str(e)}")


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
            "max_loan_multiplier": 3.0,
            "min_contribution_months": 6,
            "gl_account_name": "Loans Receivable"
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
            "gl_account_name": "Loans Receivable"
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
            "gl_account_name": "Loans Receivable"
        },
    ]
    
    for type_data in types:
        try:
            if not frappe.db.exists("Loan Type", {"loan_name": type_data["loan_name"]}):
                lt = frappe.new_doc("Loan Type")
                for key, value in type_data.items():
                    if key != "gl_account_name" and hasattr(lt, key):
                        setattr(lt, key, value)
                gl_account = frappe.db.get_value("SACCO GL Account", 
                    {"account_name": type_data["gl_account_name"]}, "name")
                if gl_account:
                    lt.default_gl_account = gl_account
                lt.insert(ignore_permissions=True)
                print(f"Created Loan Type: {type_data['loan_name']}")
        except Exception as e:
            print(f"Error creating Loan Type {type_data['loan_name']}: {str(e)}")


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
            "gl_account_name": "Share Capital"
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
            "gl_account_name": "Share Capital"
        },
    ]
    
    for type_data in types:
        try:
            if not frappe.db.exists("Share Type", {"share_name": type_data["share_name"]}):
                st = frappe.new_doc("Share Type")
                for key, value in type_data.items():
                    if key != "gl_account_name" and hasattr(st, key):
                        setattr(st, key, value)
                gl_account = frappe.db.get_value("SACCO GL Account", 
                    {"account_name": type_data["gl_account_name"]}, "name")
                if gl_account:
                    st.default_gl_account = gl_account
                st.insert(ignore_permissions=True)
                print(f"Created Share Type: {type_data['share_name']}")
        except Exception as e:
            print(f"Error creating Share Type {type_data['share_name']}: {str(e)}")


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
            "gl_account_name": "Penalty Income"
        },
        {
            "fine_name": "Meeting Absence Fine",
            "code": "MAF",
            "default_amount": 200,
            "is_percentage": 0,
            "auto_apply": 0,
            "gl_account_name": "Fine Income"
        },
        {
            "fine_name": "Late Contribution Fine",
            "code": "LCF",
            "default_amount": 100,
            "is_percentage": 0,
            "auto_apply": 1,
            "apply_after_days": 5,
            "gl_account_name": "Fine Income"
        },
        {
            "fine_name": "Bounced Cheque Fee",
            "code": "BCF",
            "default_amount": 1000,
            "is_percentage": 0,
            "auto_apply": 0,
            "gl_account_name": "Fine Income"
        },
    ]
    
    for type_data in types:
        try:
            if not frappe.db.exists("Fine Type", {"fine_name": type_data["fine_name"]}):
                ft = frappe.new_doc("Fine Type")
                for key, value in type_data.items():
                    if key != "gl_account_name" and hasattr(ft, key):
                        setattr(ft, key, value)
                gl_account = frappe.db.get_value("SACCO GL Account", 
                    {"account_name": type_data["gl_account_name"]}, "name")
                if gl_account:
                    ft.default_gl_account = gl_account
                ft.insert(ignore_permissions=True)
                print(f"Created Fine Type: {type_data['fine_name']}")
        except Exception as e:
            print(f"Error creating Fine Type {type_data['fine_name']}: {str(e)}")


def create_default_attendance_fine_types():
    """Create default attendance fine types"""
    types = [
        {
            "fine_type_name": "Meeting Absentee",
            "attendance_type": "Absent",
            "amount": 500,
            "is_active": 1,
            "apply_rules": 1,
            "waiver_allowed": 1,
            "max_waiver_percent": 50,
            "gl_account_name": "Fine Income",
            "receivable_account_name": "Fines Receivable"
        },
        {
            "fine_type_name": "Meeting Late",
            "attendance_type": "Late",
            "amount": 200,
            "is_active": 1,
            "apply_rules": 1,
            "grace_period_minutes": 15,
            "waiver_allowed": 1,
            "max_waiver_percent": 100,
            "gl_account_name": "Fine Income",
            "receivable_account_name": "Fines Receivable"
        },
    ]
    
    for type_data in types:
        try:
            if not frappe.db.exists("Attendance Fine Type", type_data["fine_type_name"]):
                aft = frappe.new_doc("Attendance Fine Type")
                aft.fine_type_name = type_data["fine_type_name"]
                aft.attendance_type = type_data["attendance_type"]
                aft.amount = type_data["amount"]
                aft.is_active = type_data.get("is_active", 1)
                aft.apply_rules = type_data.get("apply_rules", 1)
                aft.grace_period_minutes = type_data.get("grace_period_minutes", 15)
                aft.waiver_allowed = type_data.get("waiver_allowed", 1)
                aft.max_waiver_percent = type_data.get("max_waiver_percent", 100)
                
                gl_account = frappe.db.get_value("SACCO GL Account", 
                    {"account_name": type_data["gl_account_name"]}, "name")
                if gl_account:
                    aft.gl_account = gl_account
                
                recv_account = frappe.db.get_value("SACCO GL Account", 
                    {"account_name": type_data["receivable_account_name"]}, "name")
                if recv_account:
                    aft.receivable_account = recv_account
                
                aft.insert(ignore_permissions=True)
                print(f"Created Attendance Fine Type: {type_data['fine_type_name']}")
        except Exception as e:
            print(f"Error creating Attendance Fine Type {type_data['fine_type_name']}: {str(e)}")


def create_default_savings_products():
    """Create default savings products"""
    products = [
        {
            "product_name": "Regular Savings Account",
            "product_code": "RSA",
            "description": "Standard savings account for all members with competitive interest rates",
            "is_active": 1,
            "is_mandatory": 1,
            "min_balance": 500,
            "max_balance": 1000000,
            "min_deposit_amount": 100,
            "withdrawal_limits": 1,
            "max_withdrawals_per_month": 4,
            "notice_period_days": 0,
            "interest_applicable": 1,
            "interest_rate": 5.0,
            "interest_calculation_method": "Daily Balance",
            "interest_compounding_frequency": "Monthly",
            "interest_posting_frequency": "Monthly",
            "min_balance_for_interest": 500,
            "allow_overdraft": 0,
            "penalty_for_below_min_balance": 1,
            "penalty_amount": 50
        },
        {
            "product_name": "Fixed Deposit Account",
            "product_code": "FDA",
            "description": "Fixed deposit account with higher interest rates and lock-in period",
            "is_active": 1,
            "is_mandatory": 0,
            "min_balance": 10000,
            "max_balance": 5000000,
            "min_deposit_amount": 10000,
            "withdrawal_limits": 1,
            "max_withdrawals_per_month": 0,
            "notice_period_days": 30,
            "interest_applicable": 1,
            "interest_rate": 8.0,
            "interest_calculation_method": "Daily Balance",
            "interest_compounding_frequency": "Quarterly",
            "interest_posting_frequency": "Quarterly",
            "min_balance_for_interest": 10000,
            "allow_overdraft": 0,
            "penalty_for_below_min_balance": 0
        },
        {
            "product_name": "Youth Savings Account",
            "product_code": "YSA",
            "description": "Special savings account for youth members (18-35 years) with bonus interest",
            "is_active": 1,
            "is_mandatory": 0,
            "min_balance": 100,
            "max_balance": 500000,
            "min_deposit_amount": 50,
            "withdrawal_limits": 1,
            "max_withdrawals_per_month": 2,
            "notice_period_days": 0,
            "interest_applicable": 1,
            "interest_rate": 6.0,
            "interest_calculation_method": "Minimum Balance",
            "interest_compounding_frequency": "Monthly",
            "interest_posting_frequency": "Monthly",
            "min_balance_for_interest": 100,
            "allow_overdraft": 0,
            "penalty_for_below_min_balance": 0
        },
        {
            "product_name": "Senior Citizen Account",
            "product_code": "SCA",
            "description": "Premium savings account for senior members (60+ years) with preferential rates",
            "is_active": 1,
            "is_mandatory": 0,
            "min_balance": 200,
            "max_balance": 2000000,
            "min_deposit_amount": 100,
            "withdrawal_limits": 0,
            "max_withdrawals_per_month": 0,
            "notice_period_days": 0,
            "interest_applicable": 1,
            "interest_rate": 7.0,
            "interest_calculation_method": "Daily Balance",
            "interest_compounding_frequency": "Monthly",
            "interest_posting_frequency": "Monthly",
            "min_balance_for_interest": 200,
            "allow_overdraft": 0,
            "penalty_for_below_min_balance": 0
        }
    ]
    
    for prod_data in products:
        try:
            if not frappe.db.exists("Savings Product", prod_data["product_name"]):
                product = frappe.new_doc("Savings Product")
                for key, value in prod_data.items():
                    if hasattr(product, key):
                        setattr(product, key, value)
                
                # Set GL accounts
                liability_account = frappe.db.get_value("SACCO GL Account", 
                    {"account_name": "Member Savings"}, "name")
                interest_account = frappe.db.get_value("SACCO GL Account", 
                    {"account_name": "Interest Expense"}, "name")
                penalty_account = frappe.db.get_value("SACCO GL Account", 
                    {"account_name": "Penalty Income"}, "name")
                
                if liability_account:
                    product.default_gl_account = liability_account
                if interest_account:
                    product.interest_gl_account = interest_account
                if penalty_account:
                    product.penalty_gl_account = penalty_account
                
                product.insert(ignore_permissions=True)
                print(f"Created Savings Product: {prod_data['product_name']}")
        except Exception as e:
            print(f"Error creating Savings Product {prod_data['product_name']}: {str(e)}")
