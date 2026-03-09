# Copyright (c) 2024, SACCO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, get_time, time_diff_in_hours, today


class SACCOMeeting(Document):
    def validate(self):
        self.validate_dates()
        self.calculate_duration()
        self.set_status()
    
    def validate_dates(self):
        """Validate meeting dates"""
        if self.scheduled_date and getdate(self.scheduled_date) < getdate(today()):
            if self.status == "Draft":
                frappe.msgprint(_("Meeting date is in the past. Please verify."))
    
    def calculate_duration(self):
        """Calculate meeting duration from start and end time"""
        if self.scheduled_time and self.end_time:
            self.duration_hours = flt(time_diff_in_hours(self.end_time, self.scheduled_time), 1)
    
    def set_status(self):
        """Set status based on docstatus"""
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 1 and self.status == "Draft":
            self.status = "Scheduled"
    
    def on_submit(self):
        """Actions on submit"""
        self.db_set("status", "Scheduled")
    
    def on_cancel(self):
        """Actions on cancel"""
        self.db_set("status", "Cancelled")
    
    @frappe.whitelist()
    def start_meeting(self):
        """Mark meeting as in progress"""
        if self.status != "Scheduled":
            frappe.throw(_("Only Scheduled meetings can be started"))
        
        self.db_set("status", "In Progress")
        frappe.msgprint(_("Meeting started"))
    
    @frappe.whitelist()
    def complete_meeting(self):
        """Mark meeting as completed and process attendance"""
        if self.status != "In Progress":
            frappe.throw(_("Only In Progress meetings can be completed"))
        
        # Update attendance summary
        self.update_attendance_summary()
        
        # Generate attendance fines
        self.generate_attendance_fines()
        
        self.db_set("status", "Completed")
        frappe.msgprint(_("Meeting completed. Attendance fines have been generated."))
    
    @frappe.whitelist()
    def postpone_meeting(self, new_date=None, new_time=None, reason=None):
        """Postpone the meeting"""
        if self.status not in ["Scheduled", "In Progress"]:
            frappe.throw(_("Only Scheduled or In Progress meetings can be postponed"))
        
        self.db_set("status", "Postponed")
        
        if reason:
            frappe.db.set_value("SACCO Meeting", self.name, "notes", 
                f"{self.notes or ''}\n\nPostponed: {reason}")
        
        frappe.msgprint(_("Meeting has been postponed"))
    
    def update_attendance_summary(self):
        """Update attendance counts from Meeting Register"""
        attendance = frappe.db.sql("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN attendance_status = 'Present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN attendance_status = 'Absent' THEN 1 ELSE 0 END) as absent,
                SUM(CASE WHEN attendance_status = 'Late' THEN 1 ELSE 0 END) as late
            FROM `tabMeeting Register`
            WHERE meeting = %s AND docstatus = 1
        """, (self.name,), as_dict=True)
        
        if attendance:
            data = attendance[0]
            self.db_set({
                "total_invited": data.get("total") or 0,
                "total_present": data.get("present") or 0,
                "total_absent": data.get("absent") or 0,
                "total_late": data.get("late") or 0,
                "quorum_present": (data.get("present") or 0) + (data.get("late") or 0)
            })
    
    def generate_attendance_fines(self):
        """Generate fines for absent and late members"""
        # Get attendance records that haven't been fined yet
        attendance_records = frappe.get_all("Meeting Register",
            filters={
                "meeting": self.name,
                "docstatus": 1,
                "attendance_status": ["in", ["Absent", "Late"]],
                "fine_generated": 0
            },
            fields=["name", "member", "attendance_status"]
        )
        
        fines_created = 0
        
        for record in attendance_records:
            # Get the fine type for this attendance status
            fine_type_name = "Meeting Absentee" if record.attendance_status == "Absent" else "Meeting Late"
            
            # Check if fine type exists
            fine_type = frappe.db.get_value("Attendance Fine Type", 
                {"attendance_type": record.attendance_status},
                ["name", "amount", "gl_account"],
                as_dict=True
            )
            
            if not fine_type:
                continue
            
            # Create the attendance fine
            try:
                attendance_fine = frappe.get_doc({
                    "doctype": "Member Attendance Fine",
                    "member": record.member,
                    "fine_type": fine_type.name,
                    "meeting": self.name,
                    "amount": fine_type.amount,
                    "posting_date": today(),
                    "status": "Unpaid"
                })
                attendance_fine.insert()
                attendance_fine.submit()
                
                # Mark attendance record as fined
                frappe.db.set_value("Meeting Register", record.name, "fine_generated", 1)
                fines_created += 1
                
            except Exception as e:
                frappe.log_error(f"Error creating attendance fine for {record.member}: {str(e)}")
        
        if fines_created:
            frappe.msgprint(_("{0} attendance fines have been created").format(fines_created))
    
    @frappe.whitelist()
    def create_attendance_register(self):
        """Create attendance register for all eligible members"""
        if self.status != "Scheduled":
            frappe.throw(_("Attendance register can only be created for scheduled meetings"))
        
        # Determine which members to invite based on meeting type
        filters = {"status": "Active"}
        
        if self.branch:
            filters["branch"] = self.branch
        if self.member_group:
            filters["member_group"] = self.member_group
        
        members = frappe.get_all("SACCO Member", 
            filters=filters, 
            fields=["name", "member_name"]
        )
        
        created = 0
        for member in members:
            # Check if already registered
            exists = frappe.db.exists("Meeting Register", {
                "meeting": self.name,
                "member": member.name
            })
            
            if not exists:
                register = frappe.get_doc({
                    "doctype": "Meeting Register",
                    "meeting": self.name,
                    "member": member.name,
                    "attendance_status": "Absent"  # Default to absent
                })
                register.insert()
                created += 1
        
        frappe.msgprint(_("{0} members added to attendance register").format(created))
        return created


def get_permission_query_conditions(user):
    """Permission query for branch-based filtering"""
    if not user:
        user = frappe.session.user
    
    if "System Manager" in frappe.get_roles(user) or "SACCO Admin" in frappe.get_roles(user):
        return ""
    
    # Get user's branch
    member = frappe.db.get_value("SACCO Member", {"email": user}, "branch")
    if member:
        return f"(`tabSACCO Meeting`.branch = '{member}' or `tabSACCO Meeting`.branch IS NULL)"
    
    return ""


def has_permission(doc, ptype, user):
    """Check permission based on branch"""
    if not user:
        user = frappe.session.user
    
    if "System Manager" in frappe.get_roles(user) or "SACCO Admin" in frappe.get_roles(user):
        return True
    
    if not doc.branch:
        return True
    
    member = frappe.db.get_value("SACCO Member", {"email": user}, "branch")
    return member == doc.branch
