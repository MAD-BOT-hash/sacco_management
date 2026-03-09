"""
Daily Scheduled Tasks for SACCO Management System

These tasks run daily via Frappe scheduler:
- Calculate loan penalties for overdue payments
- Send payment reminders to members
- Update overdue status on loan schedules
"""

import frappe
from frappe import _
from frappe.utils import nowdate, getdate, add_days, date_diff, flt


def calculate_loan_penalties():
    """
    Calculate and apply penalties for overdue loan payments
    Runs daily to check all active loans
    """
    today = getdate(nowdate())
    
    # Get all active loans with overdue schedules
    overdue_schedules = frappe.db.sql("""
        SELECT 
            lrs.name as schedule_name,
            lrs.parent as loan,
            lrs.due_date,
            lrs.total_due,
            lrs.paid_amount,
            la.member,
            la.loan_type,
            lt.penalty_rate,
            lt.grace_period_days
        FROM `tabLoan Repayment Schedule` lrs
        INNER JOIN `tabLoan Application` la ON lrs.parent = la.name
        INNER JOIN `tabLoan Type` lt ON la.loan_type = lt.name
        WHERE la.docstatus = 1 
        AND la.status IN ('Disbursed', 'Active')
        AND lrs.status IN ('Pending', 'Partial')
        AND lrs.due_date < %(today)s
    """, {"today": today}, as_dict=True)
    
    penalties_applied = 0
    
    for schedule in overdue_schedules:
        days_overdue = date_diff(today, schedule.due_date)
        
        if days_overdue > (schedule.grace_period_days or 7):
            # Check if penalty already applied for this schedule
            existing_fine = frappe.db.exists("Member Fine", {
                "member": schedule.member,
                "fine_type": "Late Payment Penalty",
                "reason": ("like", f"%{schedule.schedule_name}%"),
                "docstatus": 1
            })
            
            if not existing_fine:
                # Calculate penalty
                overdue_amount = flt(schedule.total_due) - flt(schedule.paid_amount)
                penalty_amount = overdue_amount * flt(schedule.penalty_rate) / 100
                
                if penalty_amount > 0:
                    try:
                        # Create penalty fine
                        fine = frappe.new_doc("Member Fine")
                        fine.member = schedule.member
                        fine.fine_type = "Late Payment Penalty"
                        fine.amount = penalty_amount
                        fine.reason = f"Late payment penalty for loan {schedule.loan}, schedule {schedule.schedule_name}. {days_overdue} days overdue."
                        fine.insert(ignore_permissions=True)
                        fine.submit()
                        
                        penalties_applied += 1
                        
                    except Exception as e:
                        frappe.log_error(
                            message=str(e),
                            title=f"Error applying penalty for {schedule.loan}"
                        )
                        
        # Update schedule status to overdue
        frappe.db.set_value(
            "Loan Repayment Schedule",
            schedule.schedule_name,
            "status",
            "Overdue",
            update_modified=False
        )
    
    frappe.db.commit()
    
    if penalties_applied > 0:
        frappe.log_error(
            message=f"Applied {penalties_applied} loan penalties",
            title="Daily Penalty Calculation Complete"
        )
    
    return penalties_applied


def send_payment_reminders():
    """
    Send payment reminders to members with upcoming or overdue payments
    """
    today = getdate(nowdate())
    reminder_days = 3  # Days before due date to send reminder
    
    # Get upcoming payments
    upcoming_payments = frappe.db.sql("""
        SELECT 
            la.member,
            la.name as loan,
            la.loan_type,
            sm.member_name,
            sm.email,
            sm.phone,
            lrs.due_date,
            lrs.total_due,
            lrs.paid_amount
        FROM `tabLoan Repayment Schedule` lrs
        INNER JOIN `tabLoan Application` la ON lrs.parent = la.name
        INNER JOIN `tabSACCO Member` sm ON la.member = sm.name
        WHERE la.docstatus = 1 
        AND la.status IN ('Disbursed', 'Active')
        AND lrs.status IN ('Pending', 'Partial')
        AND lrs.due_date BETWEEN %(today)s AND %(reminder_date)s
    """, {
        "today": today,
        "reminder_date": add_days(today, reminder_days)
    }, as_dict=True)
    
    reminders_sent = 0
    
    for payment in upcoming_payments:
        try:
            # Create notification
            amount_due = flt(payment.total_due) - flt(payment.paid_amount)
            
            if payment.email:
                frappe.sendmail(
                    recipients=[payment.email],
                    subject=f"SACCO Payment Reminder - Due on {payment.due_date}",
                    message=f"""
                    Dear {payment.member_name},
                    
                    This is a reminder that your {payment.loan_type} loan payment of {amount_due} 
                    is due on {payment.due_date}.
                    
                    Please ensure timely payment to avoid late payment penalties.
                    
                    Loan Reference: {payment.loan}
                    
                    Thank you for your cooperation.
                    
                    SACCO Management
                    """
                )
                reminders_sent += 1
                
        except Exception as e:
            frappe.log_error(
                message=str(e),
                title=f"Error sending reminder to {payment.member}"
            )
    
    return reminders_sent


def update_member_balances():
    """
    Update all member balance fields
    """
    members = frappe.get_all("SACCO Member", filters={"status": "Active"}, pluck="name")
    
    for member_name in members:
        try:
            member = frappe.get_doc("SACCO Member", member_name)
            member.update_balances()
            member.db_update()
        except Exception as e:
            frappe.log_error(
                message=str(e),
                title=f"Error updating balance for {member_name}"
            )
    
    frappe.db.commit()
    return len(members)
