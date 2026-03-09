"""
Member API Endpoints

RESTful API endpoints for SACCO Member operations:
- GET /api/method/sacco_management.sacco.api.member_api.get_members - List members with filters
- GET /api/method/sacco_management.sacco.api.member_api.get_member - Get single member details
- POST /api/method/sacco_management.sacco.api.member_api.create_member - Create new member
- PUT /api/method/sacco_management.sacco.api.member_api.update_member - Update member
- DELETE /api/method/sacco_management.sacco.api.member_api.delete_member - Delete member
- GET /api/method/sacco_management.sacco.api.member_api.search_members - Search members
- GET /api/method/sacco_management.sacco.api.member_api.get_member_statistics - Get member stats
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from sacco_management.sacco.api.api_utils import (
    api_response, require_auth, require_role, validate_request_data,
    sanitize_input, parse_filters, paginate_results, validate_member_data,
    get_doc_permissions, log_api_call, handle_api_exception
)


@frappe.whitelist()
@handle_api_exception
def get_members(filters=None, page=1, page_size=20):
    """
    Get list of members with optional filtering and pagination
    
    Args:
        filters (dict|str): Filter criteria
        page (int): Page number
        page_size (int): Items per page
    
    Returns:
        dict: Paginated member list
    """
    # Parse filters
    if isinstance(filters, str):
        filters = parse_filters(filters)
    
    # Build conditions
    conditions = "WHERE m.docstatus = 1"
    
    if filters:
        if isinstance(filters, dict):
            for key, value in filters.items():
                if value:
                    conditions += f" AND m.{key} = '{frappe.db.escape(str(value))}'"
        elif isinstance(filters, list):
            # Handle Frappe filter format
            for f in filters:
                if len(f) == 4:
                    doctype, field, operator, value = f
                    if value:
                        conditions += f" AND m.{field} {operator} '{frappe.db.escape(str(value))}'"
    
    # Execute query
    query = f"""
        SELECT 
            m.name,
            m.member_name,
            m.email,
            m.phone_number,
            m.date_of_birth,
            m.gender,
            m.marital_status,
            m.national_id,
            m.pin_number,
            m.joining_date,
            m.membership_type,
            m.membership_status,
            m.branch,
            m.employer_name,
            m.department,
            m.employee_number,
            m.total_savings,
            m.total_shares,
            m.total_dividend_received
        FROM `tabSACCO Member` m
        {conditions}
        ORDER BY m.creation DESC
    """
    
    members = frappe.db.sql(query, as_dict=True)
    
    # Convert to list if result is tuple
    if isinstance(members, tuple):
        members = list(members)
    
    # Paginate results
    paginated = paginate_results(members, int(page), int(page_size))
    
    log_api_call("/api/method/sacco_management.sacco.api.member_api.get_members", "GET")
    
    return api_response(
        success=True,
        data=paginated,
        message="Members retrieved successfully"
    )


@frappe.whitelist()
@handle_api_exception
def get_member(member_id):
    """
    Get complete member details including related records
    
    Args:
        member_id (str): Member ID/name
    
    Returns:
        dict: Complete member profile
    """
    if not member_id:
        raise frappe.ValidationError(_("Member ID is required"))
    
    member = frappe.get_doc("SACCO Member", member_id)
    
    # Check permissions
    if not get_doc_permissions("SACCO Member", member_id)["read"]:
        raise frappe.PermissionError(_("You don't have permission to view this member"))
    
    # Get related data
    savings_accounts = frappe.get_all("Savings Account",
                                     filters={"member": member_id, "docstatus": 1},
                                     fields=["name", "account_type", "current_balance", "status"])
    
    share_allocations = frappe.get_all("Share Allocation",
                                      filters={"member": member_id, "docstatus": 1, "status": "Allocated"},
                                      fields=["name", "share_type", "quantity", "total_amount", "allocation_date"])
    
    loans = frappe.get_all("Loan Application",
                          filters={"member": member_id, "docstatus": 1},
                          fields=["name", "loan_type", "amount_requested", "outstanding_principal", "status"])
    
    next_of_kin = frappe.get_all("Member Next of Kin",
                                filters={"parent": member_id, "parenttype": "SACCO Member"},
                                fields=["name", "full_name", "relationship", "contact_number"])
    
    nominees = frappe.get_all("Member Nominee",
                             filters={"parent": member_id, "parenttype": "SACCO Member"},
                             fields=["name", "nominee_name", "percentage", "relationship"])
    
    member_data = {
        "member": member.as_dict(),
        "savings_accounts": savings_accounts,
        "share_allocations": share_allocations,
        "loans": loans,
        "next_of_kin": next_of_kin,
        "nominees": nominees,
        "permissions": get_doc_permissions("SACCO Member", member_id)
    }
    
    log_api_call(f"/api/method/sacco_management.sacco.api.member_api.get_member/{member_id}", "GET")
    
    return api_response(
        success=True,
        data=member_data,
        message="Member details retrieved successfully"
    )


@frappe.whitelist()
@require_role(["SACCO Admin", "Loan Officer"])
@handle_api_exception
def create_member(member_data):
    """
    Create a new SACCO member
    
    Args:
        member_data (dict): Member information
    
    Returns:
        dict: Created member details
    """
    # Validate required fields
    validate_request_data(["member_name", "email", "membership_type"], member_data)
    
    # Sanitize input
    member_data = sanitize_input(member_data)
    
    # Validate data
    validate_member_data(member_data)
    
    # Check for duplicate email
    if frappe.db.exists("SACCO Member", {"email": member_data["email"]}):
        raise frappe.DuplicateEntryError(_("A member with email {0} already exists").format(member_data["email"]))
    
    # Check for duplicate national ID
    if "national_id" in member_data and member_data["national_id"]:
        if frappe.db.exists("SACCO Member", {"national_id": member_data["national_id"]}):
            raise frappe.DuplicateEntryError(_("A member with National ID {0} already exists").format(member_data["national_id"]))
    
    # Create member
    member = frappe.new_doc("SACCO Member")
    member.update(member_data)
    member.insert(ignore_permissions=True)
    
    log_api_call("/api/method/sacco_management.sacco.api.member_api.create_member", "POST", member_data)
    
    return api_response(
        success=True,
        data={"member_id": member.name, "member": member.as_dict()},
        message="Member created successfully"
    )


@frappe.whitelist()
@require_role(["SACCO Admin", "Loan Officer"])
@handle_api_exception
def update_member(member_id, member_data):
    """
    Update existing member information
    
    Args:
        member_id (str): Member ID
        member_data (dict): Updated member information
    
    Returns:
        dict: Updated member details
    """
    if not member_id:
        raise frappe.ValidationError(_("Member ID is required"))
    
    if not frappe.db.exists("SACCO Member", member_id):
        raise frappe.DoesNotExistError(_("Member {0} does not exist").format(member_id))
    
    # Sanitize input
    member_data = sanitize_input(member_data)
    
    # Validate data
    validate_member_data(member_data)
    
    # Check for duplicate email (excluding current member)
    if "email" in member_data and member_data["email"]:
        existing = frappe.db.exists("SACCO Member", {
            "email": member_data["email"],
            "name": ["!=", member_id]
        })
        if existing:
            raise frappe.DuplicateEntryError(_("A member with email {0} already exists").format(member_data["email"]))
    
    # Update member
    member = frappe.get_doc("SACCO Member", member_id)
    member.update(member_data)
    member.save(ignore_permissions=True)
    
    log_api_call(f"/api/method/sacco_management.sacco.api.member_api.update_member/{member_id}", "PUT", member_data)
    
    return api_response(
        success=True,
        data={"member_id": member.name, "member": member.as_dict()},
        message="Member updated successfully"
    )


@frappe.whitelist()
@require_role(["SACCO Admin"])
@handle_api_exception
def delete_member(member_id):
    """
    Delete a member (only if no transactions exist)
    
    Args:
        member_id (str): Member ID
    
    Returns:
        dict: Deletion confirmation
    """
    if not member_id:
        raise frappe.ValidationError(_("Member ID is required"))
    
    member = frappe.get_doc("SACCO Member", member_id)
    
    # Check if member has any transactions
    has_savings = frappe.db.exists("Savings Account", {"member": member_id, "docstatus": 1})
    has_loans = frappe.db.exists("Loan Application", {"member": member_id, "docstatus": 1})
    has_shares = frappe.db.exists("Share Allocation", {"member": member_id, "docstatus": 1})
    
    if has_savings or has_loans or has_shares:
        raise frappe.ValidationError(
            _("Cannot delete member with existing transactions. Please cancel all related records first.")
        )
    
    # Delete member
    frappe.delete_doc("SACCO Member", member_id, ignore_permissions=True)
    
    log_api_call(f"/api/method/sacco_management.sacco.api.member_api.delete_member/{member_id}", "DELETE")
    
    return api_response(
        success=True,
        message="Member deleted successfully"
    )


@frappe.whitelist()
@handle_api_exception
def search_members(query, limit=20):
    """
    Search members by name, email, or ID
    
    Args:
        query (str): Search term
        limit (int): Maximum results
    
    Returns:
        dict: Matching members
    """
    if not query:
        raise frappe.ValidationError(_("Search query is required"))
    
    search_term = f"%{query}%"
    
    members = frappe.db.sql("""
        SELECT 
            m.name,
            m.member_name,
            m.email,
            m.phone_number,
            m.membership_status,
            m.branch
        FROM `tabSACCO Member` m
        WHERE m.docstatus = 1
        AND (
            m.member_name LIKE %s
            OR m.email LIKE %s
            OR m.name LIKE %s
            OR m.phone_number LIKE %s
            OR m.national_id LIKE %s
        )
        LIMIT %s
    """, (search_term, search_term, search_term, search_term, search_term, limit), as_dict=True)
    
    log_api_call("/api/method/sacco_management.sacco.api.member_api.search_members", "GET", {"query": query})
    
    return api_response(
        success=True,
        data={"results": members, "count": len(members)},
        message=f"Found {len(members)} matching member(s)"
    )


@frappe.whitelist()
@handle_api_exception
def get_member_statistics(branch=None):
    """
    Get member statistics and demographics
    
    Args:
        branch (str): Filter by branch
    
    Returns:
        dict: Statistical breakdown
    """
    conditions = "WHERE m.docstatus = 1 AND m.membership_status = 'Active'"
    if branch:
        conditions += f" AND m.branch = '{frappe.db.escape(branch)}'"
    
    # Total active members
    total_members = frappe.db.sql(f"""
        SELECT COUNT(*) 
        FROM `tabSACCO Member` m
        {conditions}
    """)[0][0] or 0
    
    # Gender breakdown
    gender_stats = frappe.db.sql(f"""
        SELECT m.gender, COUNT(*) as count
        FROM `tabSACCO Member` m
        {conditions}
        GROUP BY m.gender
    """, as_dict=True)
    
    # Membership type breakdown
    type_stats = frappe.db.sql(f"""
        SELECT m.membership_type, COUNT(*) as count
        FROM `tabSACCO Member` m
        {conditions}
        GROUP BY m.membership_type
    """, as_dict=True)
    
    # Branch breakdown
    branch_stats = frappe.db.sql(f"""
        SELECT m.branch, COUNT(*) as count
        FROM `tabSACCO Member` m
        {conditions}
        GROUP BY m.branch
    """, as_dict=True)
    
    # New members this month
    new_members = frappe.db.sql(f"""
        SELECT COUNT(*)
        FROM `tabSACCO Member` m
        WHERE m.docstatus = 1
        AND MONTH(m.joining_date) = MONTH(CURDATE())
        AND YEAR(m.joining_date) = YEAR(CURDATE())
    """)[0][0] or 0
    
    statistics = {
        "total_active_members": total_members,
        "gender_breakdown": [{"gender": s.gender, "count": s.count} for s in gender_stats],
        "membership_type_breakdown": [{"type": t.membership_type, "count": t.count} for t in type_stats],
        "branch_breakdown": [{"branch": b.branch, "count": b.count} for b in branch_stats],
        "new_members_this_month": new_members
    }
    
    log_api_call("/api/method/sacco_management.sacco.api.member_api.get_member_statistics", "GET")
    
    return api_response(
        success=True,
        data=statistics,
        message="Statistics retrieved successfully"
    )
