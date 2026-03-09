"""
Loan API Endpoints

RESTful API endpoints for Loan operations:
- GET /api/method/sacco_management.sacco.api.loan_api.get_loans - List loans with filters
- GET /api/method/sacco_management.sacco.api.loan_api.get_loan - Get loan details
- POST /api/method/sacco_management.sacco.api.loan_api.create_loan_application - Create loan
- POST /api/method/sacco_management.sacco.api.loan_api.approve_loan - Approve loan
- POST /api/method/sacco_management.sacco.api.loan_api.disburse_loan - Disburse loan
- POST /api/method/sacco_management.sacco.api.loan_api.process_repayment - Process repayment
- GET /api/method/sacco_management.sacco.api.loan_api.get_loan_schedule - Get repayment schedule
- GET /api/method/sacco_management.sacco.api.loan_api.get_member_loans - Get member's loans
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from sacco_management.sacco.api.api_utils import (
    api_response, require_auth, require_role, validate_request_data,
    sanitize_input, parse_filters, paginate_results, validate_loan_data,
    get_doc_permissions, log_api_call, handle_api_exception
)


@frappe.whitelist()
@handle_api_exception
def get_loans(filters=None, page=1, page_size=20):
    """
    Get list of loans with optional filtering and pagination
    
    Args:
        filters (dict|str): Filter criteria
        page (int): Page number
        page_size (int): Items per page
    
    Returns:
        dict: Paginated loan list
    """
    # Parse filters
    if isinstance(filters, str):
        filters = parse_filters(filters)
    
    conditions = "WHERE la.docstatus = 1"
    
    if filters:
        if isinstance(filters, dict):
            for key, value in filters.items():
                if value:
                    conditions += f" AND la.{key} = '{frappe.db.escape(str(value))}'"
    
    query = f"""
        SELECT 
            la.name,
            la.member,
            la.member_name,
            la.loan_type,
            la.amount_requested,
            la.interest_rate,
            la.repayment_period,
            la.outstanding_principal,
            la.status,
            la.application_date,
            la.branch
        FROM `tabLoan Application` la
        {conditions}
        ORDER BY la.creation DESC
    """
    
    loans = frappe.db.sql(query, as_dict=True)
    
    if isinstance(loans, tuple):
        loans = list(loans)
    
    paginated = paginate_results(loans, int(page), int(page_size))
    
    log_api_call("/api/method/sacco_management.sacco.api.loan_api.get_loans", "GET")
    
    return api_response(
        success=True,
        data=paginated,
        message="Loans retrieved successfully"
    )


@frappe.whitelist()
@handle_api_exception
def get_loan(loan_id):
    """
    Get complete loan details including schedule and repayments
    
    Args:
        loan_id (str): Loan Application ID
    
    Returns:
        dict: Complete loan profile
    """
    if not loan_id:
        raise frappe.ValidationError(_("Loan ID is required"))
    
    loan = frappe.get_doc("Loan Application", loan_id)
    
    # Check permissions
    if not get_doc_permissions("Loan Application", loan_id)["read"]:
        raise frappe.PermissionError(_("You don't have permission to view this loan"))
    
    # Get repayment schedule
    schedule = frappe.get_all("Loan Repayment Schedule",
                             filters={"parent": loan_id, "parenttype": "Loan Application"},
                             fields=["name", "payment_date", "principal_amount", "interest_amount", 
                                    "paid_amount", "outstanding_balance", "status"])
    
    # Get actual repayments
    repayments = frappe.get_all("Loan Repayment",
                               filters={"loan_application": loan_id, "docstatus": 1},
                               fields=["name", "payment_date", "amount_paid", "principal_paid", 
                                      "interest_paid", "penalty_paid"])
    
    # Get guarantors
    guarantors = frappe.get_all("Loan Guarantor",
                               filters={"parent": loan_id, "parenttype": "Loan Application"},
                               fields=["guarantor_name", "guarantor_type", "amount_guaranteed"])
    
    # Get collateral
    collaterals = frappe.get_all("Loan Collateral",
                                filters={"parent": loan_id, "parenttype": "Loan Application"},
                                fields=["collateral_type", "description", "estimated_value"])
    
    loan_data = {
        "loan": loan.as_dict(),
        "repayment_schedule": schedule,
        "repayments": repayments,
        "guarantors": guarantors,
        "collaterals": collaterals,
        "permissions": get_doc_permissions("Loan Application", loan_id)
    }
    
    log_api_call(f"/api/method/sacco_management.sacco.api.loan_api.get_loan/{loan_id}", "GET")
    
    return api_response(
        success=True,
        data=loan_data,
        message="Loan details retrieved successfully"
    )


@frappe.whitelist()
@require_role(["SACCO Admin", "Loan Officer", "Member"])
@handle_api_exception
def create_loan_application(loan_data):
    """
    Create a new loan application
    
    Args:
        loan_data (dict): Loan information
    
    Returns:
        dict: Created loan application
    """
    # Validate required fields
    validate_request_data(["member", "loan_type", "amount_requested", "repayment_period"], loan_data)
    
    # Sanitize input
    loan_data = sanitize_input(loan_data)
    
    # Validate data
    validate_loan_data(loan_data)
    
    # Check if member exists
    if not frappe.db.exists("SACCO Member", loan_data["member"]):
        raise frappe.DoesNotExistError(_("Member {0} does not exist").format(loan_data["member"]))
    
    # Create loan application
    loan = frappe.new_doc("Loan Application")
    loan.update(loan_data)
    loan.insert(ignore_permissions=True)
    
    log_api_call("/api/method/sacco_management.sacco.api.loan_api.create_loan_application", "POST", loan_data)
    
    return api_response(
        success=True,
        data={"loan_id": loan.name, "loan": loan.as_dict()},
        message="Loan application created successfully"
    )


@frappe.whitelist()
@require_role(["SACCO Admin", "Loan Officer", "Credit Committee"])
@handle_api_exception
def approve_loan(loan_id, approval_details=None):
    """
    Approve a loan application
    
    Args:
        loan_id (str): Loan Application ID
        approval_details (dict): Approval information including comments, interest rate, etc.
    
    Returns:
        dict: Approved loan details
    """
    if not loan_id:
        raise frappe.ValidationError(_("Loan ID is required"))
    
    loan = frappe.get_doc("Loan Application", loan_id)
    
    if loan.status != "Pending Approval":
        raise frappe.ValidationError(_("Loan is not in pending approval status"))
    
    # Update approval details if provided
    if approval_details:
        if "approved_amount" in approval_details:
            loan.amount_approved = flt(approval_details["approved_amount"])
        if "interest_rate" in approval_details:
            loan.interest_rate = flt(approval_details["interest_rate"])
        if "repayment_period" in approval_details:
            loan.repayment_period = int(approval_details["repayment_period"])
        if "comments" in approval_details:
            loan.approval_comments = approval_details["comments"]
    
    # Set approval date and user
    loan.approved_date = nowdate()
    loan.approved_by = frappe.session.user
    
    # Update status
    loan.status = "Approved"
    loan.save(ignore_permissions=True)
    
    log_api_call(f"/api/method/sacco_management.sacco.api.loan_api.approve_loan/{loan_id}", "POST", approval_details)
    
    return api_response(
        success=True,
        data={"loan_id": loan.name, "loan": loan.as_dict()},
        message="Loan approved successfully"
    )


@frappe.whitelist()
@require_role(["SACCO Admin", "Loan Officer"])
@handle_api_exception
def disburse_loan(loan_id, disbursement_details=None):
    """
    Disburse an approved loan
    
    Args:
        loan_id (str): Loan Application ID
        disbursement_details (dict): Disbursement information
    
    Returns:
        dict: Disbursed loan details
    """
    if not loan_id:
        raise frappe.ValidationError(_("Loan ID is required"))
    
    loan = frappe.get_doc("Loan Application", loan_id)
    
    if loan.status != "Approved":
        raise frappe.ValidationError(_("Loan is not approved for disbursement"))
    
    # Create disbursement record
    from sacco_management.sacco.doctype.loan_disbursement.loan_disbursement import create_loan_disbursement
    
    disbursement = create_loan_disbursement(loan_id)
    
    if disbursement_details:
        if "disbursement_account" in disbursement_details:
            disbursement.disbursement_account = disbursement_details["disbursement_account"]
        if "payment_mode" in disbursement_details:
            disbursement.payment_mode = disbursement_details["payment_mode"]
        
        disbursement.save(ignore_permissions=True)
    
    disbursement.submit()
    
    log_api_call(f"/api/method/sacco_management.sacco.api.loan_api.disburse_loan/{loan_id}", "POST")
    
    return api_response(
        success=True,
        data={
            "loan_id": loan.name,
            "disbursement_id": disbursement.name,
            "loan": loan.as_dict()
        },
        message="Loan disbursed successfully"
    )


@frappe.whitelist()
@require_role(["SACCO Admin", "Loan Officer", "Accountant", "Member"])
@handle_api_exception
def process_repayment(loan_id, repayment_data):
    """
    Process a loan repayment
    
    Args:
        loan_id (str): Loan Application ID
        repayment_data (dict): Repayment information
    
    Returns:
        dict: Repayment confirmation
    """
    if not loan_id:
        raise frappe.ValidationError(_("Loan ID is required"))
    
    validate_request_data(["amount_paid", "payment_date", "payment_mode"], repayment_data)
    
    loan = frappe.get_doc("Loan Application", loan_id)
    
    # Validate amount
    if flt(repayment_data["amount_paid"]) <= 0:
        raise frappe.ValidationError(_("Repayment amount must be greater than zero"))
    
    # Create repayment record
    from sacco_management.sacco.doctype.loan_repayment.loan_repayment import create_loan_repayment
    
    repayment = create_loan_repayment(loan_id)
    repayment.amount_paid = flt(repayment_data["amount_paid"])
    repayment.payment_date = repayment_data["payment_date"]
    repayment.payment_mode = repayment_data["payment_mode"]
    
    if "payment_reference" in repayment_data:
        repayment.payment_reference = repayment_data["payment_reference"]
    
    repayment.insert(ignore_permissions=True)
    repayment.submit()
    
    log_api_call(f"/api/method/sacco_management.sacco.api.loan_api.process_repayment/{loan_id}", "POST", repayment_data)
    
    return api_response(
        success=True,
        data={
            "repayment_id": repayment.name,
            "loan_id": loan.name,
            "outstanding_balance": loan.outstanding_principal
        },
        message="Repayment processed successfully"
    )


@frappe.whitelist()
@handle_api_exception
def get_loan_schedule(loan_id):
    """
    Get loan repayment schedule
    
    Args:
        loan_id (str): Loan Application ID
    
    Returns:
        dict: Repayment schedule
    """
    if not loan_id:
        raise frappe.ValidationError(_("Loan ID is required"))
    
    schedule = frappe.get_all("Loan Repayment Schedule",
                             filters={"parent": loan_id, "parenttype": "Loan Application"},
                             order_by="payment_date ASC",
                             fields=["name", "payment_date", "principal_amount", "interest_amount",
                                    "total_payment", "paid_amount", "outstanding_balance", "status"])
    
    log_api_call(f"/api/method/sacco_management.sacco.api.loan_api.get_loan_schedule/{loan_id}", "GET")
    
    return api_response(
        success=True,
        data={"schedule": schedule, "count": len(schedule)},
        message="Repayment schedule retrieved successfully"
    )


@frappe.whitelist()
@handle_api_exception
def get_member_loans(member_id, status=None):
    """
    Get all loans for a member
    
    Args:
        member_id (str): Member ID
        status (str): Filter by status (optional)
    
    Returns:
        dict: Member's loans
    """
    if not member_id:
        raise frappe.ValidationError(_("Member ID is required"))
    
    filters = {"member": member_id, "docstatus": 1}
    if status:
        filters["status"] = status
    
    loans = frappe.get_all("Loan Application",
                          filters=filters,
                          fields=["name", "loan_type", "amount_requested", "outstanding_principal",
                                 "status", "application_date"],
                          order_by="creation DESC")
    
    log_api_call(f"/api/method/sacco_management.sacco.api.loan_api.get_member_loans/{member_id}", "GET")
    
    return api_response(
        success=True,
        data={"loans": loans, "count": len(loans)},
        message=f"Retrieved {len(loans)} loan(s) for member {member_id}"
    )
