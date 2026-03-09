"""
Fine Management Utilities for SACCO Management System

This module provides utility functions for fine management:
- Automatic fine application based on rules
- Fine calculation engines
- Fine payment processing
- Fine waiver processing
- Meeting attendance fine automation

"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, date_diff


def apply_fine_rules(context_data):
    """
    Apply applicable fine rules based on trigger event
    
    Args:
        context_data: dict with contextual information
                     Must include: trigger_event, member, and event-specific data
    
    Returns:
        list of created Member Fine documents
    """
    created_fines = []
    
    # Get active fine rules for this trigger event, ordered by priority
    rules = frappe.get_all("Fine Rule",
                          filters={
                              "trigger_event": context_data.get("trigger_event"),
                              "status": "Active",
                              "is_active": 1
                          },
                          order_by="priority ASC")
    
    for rule_data in rules:
        rule = frappe.get_doc("Fine Rule", rule_data.name)
        
        # Check if rule should be applied
        if not should_apply_rule(rule, context_data):
            continue
        
        # Calculate fine amount
        fine_amount = rule.calculate_fine(context_data)
        
        if fine_amount > 0:
            # Create Member Fine
            fine = create_member_fine(rule, context_data, fine_amount)
            created_fines.append(fine.name)
    
    return created_fines


def should_apply_rule(rule, context_data):
    """
    Determine if a fine rule should be applied based on conditions
    
    Args:
        rule: Fine Rule document
        context_data: Contextual data
    
    Returns:
        bool: Whether rule should be applied
    """
    # Check grace period
    if rule.condition_type == "After Grace Period" and rule.grace_period_days:
        if context_data.get("days_overdue", 0) <= rule.grace_period_days:
            return False
    
    # Check threshold
    if rule.condition_type == "Threshold Based" and rule.threshold_value:
        if context_data.get("threshold_value", 0) < rule.threshold_value:
            return False
    
    # Check member type applicability
    if not rule.applicable_to_all_members and rule.member_types:
        member_type = frappe.db.get_value("SACCO Member", context_data.get("member"), "member_type")
        if member_type not in rule.member_types:
            return False
    
    # Check branch applicability
    if rule.branches:
        member_branch = frappe.db.get_value("SACCO Member", context_data.get("member"), "branch")
        if member_branch not in rule.branches:
            return False
    
    return True


def create_member_fine(rule, context_data, amount):
    """
    Create Member Fine document
    
    Args:
        rule: Fine Rule document
        context_data: Contextual data
        amount: Fine amount
    
    Returns:
        Created Member Fine document
    """
    try:
        fine = frappe.new_doc("Member Fine")
        fine.member = context_data.get("member")
        fine.fine_type = rule.fine_type
        fine.amount = amount
        fine.posting_date = context_data.get("posting_date", nowdate())
        fine.reason = f"Auto-applied via Fine Rule: {rule.name} - {rule.description or ''}"
        fine.reference_doctype = context_data.get("reference_doctype")
        fine.reference_document = context_data.get("reference_document")
        
        fine.insert(ignore_permissions=True)
        fine.submit()
        
        frappe.log_error(
            message=f"Fine of {amount} applied to {context_data.get('member')} for {rule.trigger_event}",
            title="Fine Auto-Applied"
        )
        
        return fine
        
    except Exception as e:
        frappe.log_error(
            message=f"Error creating fine for {context_data.get('member')}: {str(e)}",
            title="Fine Creation Error"
        )
        raise


def auto_apply_meeting_fines(meeting_name):
    """
    Automatically apply fines for meeting attendance
    
    Args:
        meeting_name: SACCO Meeting name
    
    Returns:
        dict with statistics
    """
    stats = {
        "absent_fines": 0,
        "late_fines": 0,
        "total_fines": 0
    }
    
    # Get all attendance records for the meeting
    attendances = frappe.get_all("Meeting Register",
                                filters={"meeting": meeting_name},
                                fields=["name", "member", "attendance_status", "time_in"])
    
    meeting = frappe.get_doc("SACCO Meeting", meeting_name)
    meeting_start_time = meeting.scheduled_time or "09:00:00"
    
    for attendance in attendances:
        context_data = {
            "member": attendance.member,
            "posting_date": meeting.meeting_date,
            "reference_doctype": "Meeting Register",
            "reference_document": attendance.name
        }
        
        # Handle absence
        if attendance.attendance_status == "Absent":
            context_data["trigger_event"] = "Meeting Absence"
            context_data["days_overdue"] = 0
            
            fines = apply_fine_rules(context_data)
            if fines:
                stats["absent_fines"] += 1
                stats["total_fines"] += len(fines)
        
        # Handle late arrival
        elif attendance.attendance_status == "Late" and attendance.time_in:
            context_data["trigger_event"] = "Meeting Late Arrival"
            
            # Calculate minutes late
            from datetime import datetime
            scheduled = datetime.strptime(f"{meeting.meeting_date} {meeting_start_time}", "%Y-%m-%d %H:%M:%S")
            actual = datetime.strptime(f"{meeting.meeting_date} {attendance.time_in}", "%Y-%m-%d %H:%M:%S")
            minutes_late = (actual - scheduled).seconds // 60
            
            context_data["minutes_late"] = minutes_late
            context_data["days_overdue"] = 0
            
            fines = apply_fine_rules(context_data)
            if fines:
                stats["late_fines"] += 1
                stats["total_fines"] += len(fines)
    
    return stats


def get_member_outstanding_fines(member_name):
    """
    Get outstanding fines for a member
    
    Args:
        member_name: Member ID
    
    Returns:
        dict with fine breakdown
    """
    fines = frappe.db.sql("""
        SELECT 
            mf.name,
            mf.fine_type,
            mf.amount,
            mf.amount_paid,
            mf.status,
            mf.posting_date,
            mf.reason
        FROM `tabMember Fine` mf
        WHERE mf.member = %s 
        AND mf.docstatus = 1
        AND mf.status != 'Paid'
        ORDER BY mf.posting_date ASC
    """, (member_name,), as_dict=True)
    
    total_outstanding = sum([flt(f.amount) - flt(f.amount_paid) for f in fines])
    total_paid = sum([flt(f.amount_paid) for f in fines])
    total_original = sum([flt(f.amount) for f in fines])
    
    return {
        "fines": fines,
        "total_outstanding": flt(total_outstanding, 2),
        "total_paid": flt(total_paid, 2),
        "total_original": flt(total_original, 2),
        "count": len(fines)
    }


def process_automatic_fine_application():
    """
    Process automatic fine application for all pending events
    This runs daily via scheduler
    """
    stats = {
        "loan_penalties": 0,
        "meeting_absences": 0,
        "contribution_defaults": 0
    }
    
    # 1. Apply loan payment penalties
    overdue_loans = frappe.get_all("Loan Repayment Schedule",
                                  filters={
                                      "payment_date": ["<", nowdate()],
                                      "status": ["in", ["Pending", "Partial"]]
                                  },
                                  fields=["parent", "member", "payment_date"])
    
    for loan_schedule in overdue_loans:
        days_overdue = date_diff(nowdate(), loan_schedule.payment_date)
        
        context_data = {
            "trigger_event": "Late Loan Payment",
            "member": loan_schedule.member,
            "days_overdue": days_overdue,
            "reference_doctype": "Loan Application",
            "reference_document": loan_schedule.parent
        }
        
        fines = apply_fine_rules(context_data)
        if fines:
            stats["loan_penalties"] += len(fines)
    
    # 2. Apply meeting absence fines (for meetings held yesterday)
    from frappe.utils import add_days
    yesterday = add_days(nowdate(), -1)
    
    meetings = frappe.get_all("SACCO Meeting",
                             filters={
                                 "scheduled_date": yesterday,
                                 "docstatus": 1
                             })
    
    for meeting in meetings:
        result = auto_apply_meeting_fines(meeting.name)
        stats["meeting_absences"] += result["total_fines"]
    
    return stats
