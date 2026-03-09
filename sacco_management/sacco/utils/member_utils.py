"""
Member Utilities for SACCO Management System
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def get_member_statement(member, from_date=None, to_date=None):
    """
    Generate comprehensive member statement
    
    Args:
        member: Member docname
        from_date: Start date filter
        to_date: End date filter
        
    Returns:
        dict with all member transactions
    """
    if not from_date:
        from_date = frappe.db.get_value("SACCO Member", member, "join_date")
    if not to_date:
        to_date = nowdate()
        
    statement = {
        "member": member,
        "from_date": from_date,
        "to_date": to_date,
        "contributions": [],
        "loans": [],
        "loan_repayments": [],
        "shares": [],
        "fines": [],
        "summary": {}
    }
    
    # Get member details
    member_doc = frappe.get_doc("SACCO Member", member)
    statement["member_name"] = member_doc.member_name
    statement["branch"] = member_doc.branch
    statement["join_date"] = member_doc.join_date
    
    # Contributions
    statement["contributions"] = frappe.db.sql("""
        SELECT 
            name, contribution_date, contribution_type, amount, payment_mode
        FROM `tabMember Contribution`
        WHERE member = %s AND docstatus = 1
        AND contribution_date BETWEEN %s AND %s
        ORDER BY contribution_date DESC
    """, (member, from_date, to_date), as_dict=True)
    
    # Loans
    statement["loans"] = frappe.db.sql("""
        SELECT 
            name, application_date, loan_type, disbursed_amount,
            interest_rate, tenure_months, status, outstanding_amount
        FROM `tabLoan Application`
        WHERE member = %s AND docstatus = 1
        AND application_date BETWEEN %s AND %s
        ORDER BY application_date DESC
    """, (member, from_date, to_date), as_dict=True)
    
    # Loan Repayments
    statement["loan_repayments"] = frappe.db.sql("""
        SELECT 
            name, loan, payment_date, amount_paid,
            principal_paid, interest_paid, penalty_paid
        FROM `tabLoan Repayment`
        WHERE member = %s AND docstatus = 1
        AND payment_date BETWEEN %s AND %s
        ORDER BY payment_date DESC
    """, (member, from_date, to_date), as_dict=True)
    
    # Share Allocations
    statement["shares"] = frappe.db.sql("""
        SELECT 
            name, share_type, quantity, total_amount, allocation_date, status
        FROM `tabShare Allocation`
        WHERE member = %s AND docstatus = 1
        AND allocation_date BETWEEN %s AND %s
        ORDER BY allocation_date DESC
    """, (member, from_date, to_date), as_dict=True)
    
    # Fines
    statement["fines"] = frappe.db.sql("""
        SELECT 
            name, fine_type, fine_date, amount, paid_amount, status, reason
        FROM `tabMember Fine`
        WHERE member = %s AND docstatus = 1
        AND fine_date BETWEEN %s AND %s
        ORDER BY fine_date DESC
    """, (member, from_date, to_date), as_dict=True)
    
    # Calculate summary
    statement["summary"] = {
        "total_contributions": sum(flt(c.amount) for c in statement["contributions"]),
        "total_loans_taken": sum(flt(l.disbursed_amount) for l in statement["loans"]),
        "total_repayments": sum(flt(r.amount_paid) for r in statement["loan_repayments"]),
        "total_shares": sum(flt(s.total_amount) for s in statement["shares"]),
        "total_fines": sum(flt(f.amount) for f in statement["fines"]),
        "current_contributions": member_doc.total_contributions,
        "current_savings": member_doc.total_savings,
        "current_shares": member_doc.share_value,
        "current_loan_balance": member_doc.outstanding_loan_balance,
        "current_unpaid_fines": member_doc.unpaid_fines
    }
    
    return statement


@frappe.whitelist()
def search_members(txt, branch=None, status=None):
    """
    Search members by name, ID number, or phone
    
    Args:
        txt: Search text
        branch: Optional branch filter
        status: Optional status filter
        
    Returns:
        List of matching members
    """
    conditions = "1=1"
    values = {"txt": f"%{txt}%"}
    
    if branch:
        conditions += " AND branch = %(branch)s"
        values["branch"] = branch
        
    if status:
        conditions += " AND status = %(status)s"
        values["status"] = status
        
    members = frappe.db.sql(f"""
        SELECT 
            name, member_name, id_number, phone, branch, status
        FROM `tabSACCO Member`
        WHERE {conditions}
        AND (
            member_name LIKE %(txt)s
            OR id_number LIKE %(txt)s
            OR phone LIKE %(txt)s
            OR name LIKE %(txt)s
        )
        LIMIT 20
    """, values, as_dict=True)
    
    return members


def validate_member_eligibility(member, transaction_type):
    """
    Validate if member is eligible for a transaction
    
    Args:
        member: Member docname
        transaction_type: Type of transaction (contribution, loan, share, etc.)
        
    Returns:
        dict with eligibility status and reasons
    """
    member_doc = frappe.get_doc("SACCO Member", member)
    
    eligibility = {
        "eligible": True,
        "reasons": []
    }
    
    # Check member status
    if member_doc.status != "Active":
        eligibility["eligible"] = False
        eligibility["reasons"].append(f"Member status is {member_doc.status}")
        
    # Check membership fee for certain transactions
    if transaction_type in ["loan", "share"] and not member_doc.membership_fee_paid:
        eligibility["eligible"] = False
        eligibility["reasons"].append("Membership fee not paid")
        
    # Check unpaid fines for loans
    if transaction_type == "loan" and flt(member_doc.unpaid_fines) > 0:
        eligibility["eligible"] = False
        eligibility["reasons"].append(f"Outstanding fines: {member_doc.unpaid_fines}")
        
    return eligibility


def get_member_dashboard(member):
    """
    Get dashboard data for a member
    
    Args:
        member: Member docname
        
    Returns:
        dict with dashboard data
    """
    member_doc = frappe.get_doc("SACCO Member", member)
    member_doc.update_balances()
    
    # Recent transactions
    recent_contributions = frappe.get_all(
        "Member Contribution",
        filters={"member": member, "docstatus": 1},
        fields=["name", "contribution_date", "contribution_type", "amount"],
        order_by="contribution_date desc",
        limit=5
    )
    
    recent_repayments = frappe.get_all(
        "Loan Repayment",
        filters={"member": member, "docstatus": 1},
        fields=["name", "payment_date", "loan", "amount_paid"],
        order_by="payment_date desc",
        limit=5
    )
    
    # Active loans
    active_loans = frappe.get_all(
        "Loan Application",
        filters={"member": member, "docstatus": 1, "status": ["in", ["Disbursed", "Active"]]},
        fields=["name", "loan_type", "disbursed_amount", "outstanding_amount", "monthly_installment"]
    )
    
    # Upcoming payments
    from frappe.utils import add_days
    today = getdate(nowdate())
    next_week = add_days(today, 7)
    
    upcoming_payments = frappe.db.sql("""
        SELECT 
            lrs.due_date,
            lrs.total_due,
            lrs.paid_amount,
            la.name as loan,
            la.loan_type
        FROM `tabLoan Repayment Schedule` lrs
        INNER JOIN `tabLoan Application` la ON lrs.parent = la.name
        WHERE la.member = %s AND la.docstatus = 1
        AND la.status IN ('Disbursed', 'Active')
        AND lrs.status IN ('Pending', 'Partial')
        AND lrs.due_date BETWEEN %s AND %s
        ORDER BY lrs.due_date
    """, (member, today, next_week), as_dict=True)
    
    return {
        "member": member_doc.as_dict(),
        "recent_contributions": recent_contributions,
        "recent_repayments": recent_repayments,
        "active_loans": active_loans,
        "upcoming_payments": upcoming_payments,
        "balances": {
            "total_contributions": member_doc.total_contributions,
            "total_savings": member_doc.total_savings,
            "total_shares": member_doc.total_shares,
            "share_value": member_doc.share_value,
            "outstanding_loan_balance": member_doc.outstanding_loan_balance,
            "unpaid_fines": member_doc.unpaid_fines
        }
    }
