"""
Savings & Shares API Endpoints

RESTful API endpoints for Savings and Share operations
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from sacco_management.sacco.api.api_utils import (
    api_response, require_auth, require_role, validate_request_data,
    sanitize_input, get_doc_permissions, log_api_call, handle_api_exception
)


# ========== SAVINGS API ENDPOINTS ==========

@frappe.whitelist()
@handle_api_exception
def get_savings_accounts(member_id=None):
    """Get savings accounts with optional member filter"""
    filters = {"docstatus": 1}
    if member_id:
        filters["member"] = member_id
    
    accounts = frappe.get_all("Savings Account",
                             filters=filters,
                             fields=["name", "member", "member_name", "account_type", 
                                    "current_balance", "status", "branch"])
    
    return api_response(success=True, data={"accounts": accounts})


@frappe.whitelist()
@require_role(["SACCO Admin", "Loan Officer", "Member"])
@handle_api_exception
def create_savings_account(account_data):
    """Create new savings account"""
    validate_request_data(["member", "account_type"], account_data)
    account_data = sanitize_input(account_data)
    
    account = frappe.new_doc("Savings Account")
    account.update(account_data)
    account.insert(ignore_permissions=True)
    
    return api_response(
        success=True,
        data={"account_id": account.name},
        message="Savings account created successfully"
    )


@frappe.whitelist()
@require_role(["SACCO Admin", "Loan Officer", "Member"])
@handle_api_exception
def process_deposit(deposit_data):
    """Process savings deposit"""
    validate_request_data(["savings_account", "amount", "payment_mode"], deposit_data)
    
    from sacco_management.sacco.doctype.savings_deposit.savings_deposit import create_savings_deposit
    
    deposit = create_savings_deposit(deposit_data["savings_account"])
    deposit.amount = flt(deposit_data["amount"])
    deposit.payment_mode = deposit_data["payment_mode"]
    
    if "payment_reference" in deposit_data:
        deposit.payment_reference = deposit_data["payment_reference"]
    
    deposit.insert(ignore_permissions=True)
    deposit.submit()
    
    return api_response(
        success=True,
        data={"deposit_id": deposit.name},
        message="Deposit processed successfully"
    )


@frappe.whitelist()
@require_role(["SACCO Admin", "Loan Officer", "Member"])
@handle_api_exception
def process_withdrawal(withdrawal_data):
    """Process savings withdrawal"""
    validate_request_data(["savings_account", "amount", "withdrawal_reason"], withdrawal_data)
    
    from sacco_management.sacco.doctype.savings_withdrawal.savings_withdrawal import create_savings_withdrawal
    
    withdrawal = create_savings_withdrawal(withdrawal_data["savings_account"])
    withdrawal.amount = flt(withdrawal_data["amount"])
    withdrawal.reason = withdrawal_data["withdrawal_reason"]
    
    if "payment_mode" in withdrawal_data:
        withdrawal.payment_mode = withdrawal_data["payment_mode"]
    
    withdrawal.insert(ignore_permissions=True)
    withdrawal.submit()
    
    return api_response(
        success=True,
        data={"withdrawal_id": withdrawal.name},
        message="Withdrawal processed successfully"
    )


# ========== SHARES API ENDPOINTS ==========

@frappe.whitelist()
@handle_api_exception
def get_share_allocations(member_id=None):
    """Get share allocations with optional member filter"""
    filters = {"docstatus": 1, "status": "Allocated"}
    if member_id:
        filters["member"] = member_id
    
    allocations = frappe.get_all("Share Allocation",
                                filters=filters,
                                fields=["name", "member", "share_type", "quantity", 
                                       "total_amount", "allocation_date"])
    
    return api_response(success=True, data={"allocations": allocations})


@frappe.whitelist()
@require_role(["SACCO Admin", "Loan Officer", "Member"])
@handle_api_exception
def purchase_shares(purchase_data):
    """Purchase new shares"""
    validate_request_data(["member", "share_type", "quantity"], purchase_data)
    
    from sacco_management.sacco.doctype.share_purchase.share_purchase import create_share_purchase
    
    purchase = create_share_purchase(purchase_data["member"])
    purchase.share_type = purchase_data["share_type"]
    purchase.quantity = int(purchase_data["quantity"])
    
    if "payment_mode" in purchase_data:
        purchase.payment_mode = purchase_data["payment_mode"]
    if "payment_reference" in purchase_data:
        purchase.payment_reference = purchase_data["payment_reference"]
    
    purchase.insert(ignore_permissions=True)
    purchase.submit()
    
    return api_response(
        success=True,
        data={"purchase_id": purchase.name},
        message="Share purchase completed successfully"
    )


@frappe.whitelist()
@require_role(["SACCO Admin", "Loan Officer"])
@handle_api_exception
def redeem_shares(redemption_data):
    """Redeem shares"""
    validate_request_data(["member", "share_type", "quantity_requested"], redemption_data)
    
    from sacco_management.sacco.doctype.share_redemption.share_redemption import create_share_redemption
    
    redemption = create_share_redemption(redemption_data["member"])
    redemption.share_type = redemption_data["share_type"]
    redemption.quantity_requested = int(redemption_data["quantity_requested"])
    
    if "reason" in redemption_data:
        redemption.reason = redemption_data["reason"]
    
    redemption.insert(ignore_permissions=True)
    redemption.submit()
    
    return api_response(
        success=True,
        data={"redemption_id": redemption.name},
        message="Share redemption request submitted successfully"
    )


@frappe.whitelist()
@handle_api_exception
def get_dividend_calculations(period_id=None, member_id=None):
    """Get dividend calculations"""
    filters = {"docstatus": 1}
    if period_id:
        filters["dividend_period"] = period_id
    if member_id:
        filters["member"] = member_id
    
    calculations = frappe.get_all("Dividend Calculation",
                                 filters=filters,
                                 fields=["name", "member", "dividend_period", "eligible_shares",
                                        "dividend_rate", "gross_dividend", "net_dividend_payable"])
    
    return api_response(success=True, data={"calculations": calculations})


@frappe.whitelist()
@require_role(["SACCO Admin", "Accountant"])
@handle_api_exception
def process_dividend_payment(payment_data):
    """Process dividend payment"""
    validate_request_data(["dividend_calculation", "payment_mode"], payment_data)
    
    from sacco_management.sacco.doctype.dividend_ledger.dividend_ledger import create_dividend_ledger
    
    ledger = create_dividend_ledger(payment_data["dividend_calculation"])
    ledger.payment_mode = payment_data["payment_mode"]
    
    if "payment_reference" in payment_data:
        ledger.payment_reference = payment_data["payment_reference"]
    
    ledger.insert(ignore_permissions=True)
    ledger.submit()
    
    return api_response(
        success=True,
        data={"payment_id": ledger.name},
        message="Dividend payment processed successfully"
    )
