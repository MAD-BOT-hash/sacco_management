# Copyright (c) 2024, SACCO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_time


class MeetingRegister(Document):
    def validate(self):
        self.validate_duplicate()
        self.validate_time()
        self.check_late_arrival()
    
    def validate_duplicate(self):
        """Check for duplicate attendance entry"""
        if self.is_new():
            existing = frappe.db.exists("Meeting Register", {
                "meeting": self.meeting,
                "member": self.member,
                "name": ["!=", self.name]
            })
            if existing:
                frappe.throw(_("Attendance already recorded for this member in this meeting"))
    
    def validate_time(self):
        """Validate time in/out"""
        if self.time_in and self.time_out:
            if get_time(self.time_out) < get_time(self.time_in):
                frappe.throw(_("Time Out cannot be before Time In"))
    
    def check_late_arrival(self):
        """Auto-mark as late if arrived after meeting start time"""
        if self.attendance_status == "Present" and self.time_in:
            meeting_start = frappe.db.get_value("SACCO Meeting", self.meeting, "scheduled_time")
            if meeting_start and get_time(self.time_in) > get_time(meeting_start):
                # Calculate late by minutes
                late_minutes = (get_time(self.time_in).hour * 60 + get_time(self.time_in).minute) - \
                              (get_time(meeting_start).hour * 60 + get_time(meeting_start).minute)
                
                # Get grace period from settings (default 15 minutes)
                grace_period = frappe.db.get_single_value("SACCO Settings", "meeting_grace_period") or 15
                
                if late_minutes > grace_period:
                    self.attendance_status = "Late"
                    if not self.notes:
                        self.notes = f"Arrived {late_minutes} minutes late"
    
    def on_submit(self):
        """Update meeting attendance summary on submit"""
        self.update_meeting_attendance()
    
    def on_cancel(self):
        """Update meeting attendance summary on cancel"""
        self.update_meeting_attendance()
    
    def update_meeting_attendance(self):
        """Update the parent meeting's attendance counts"""
        meeting = frappe.get_doc("SACCO Meeting", self.meeting)
        
        attendance = frappe.db.sql("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN attendance_status = 'Present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN attendance_status = 'Absent' THEN 1 ELSE 0 END) as absent,
                SUM(CASE WHEN attendance_status = 'Late' THEN 1 ELSE 0 END) as late,
                SUM(CASE WHEN attendance_status = 'Excused' THEN 1 ELSE 0 END) as excused
            FROM `tabMeeting Register`
            WHERE meeting = %s AND docstatus = 1
        """, (self.meeting,), as_dict=True)
        
        if attendance:
            data = attendance[0]
            frappe.db.set_value("SACCO Meeting", self.meeting, {
                "total_invited": data.get("total") or 0,
                "total_present": data.get("present") or 0,
                "total_absent": data.get("absent") or 0,
                "total_late": data.get("late") or 0,
                "quorum_present": (data.get("present") or 0) + (data.get("late") or 0)
            })
    
    @frappe.whitelist()
    def mark_present(self):
        """Quick action to mark member as present"""
        if self.docstatus != 0:
            frappe.throw(_("Cannot modify submitted attendance"))
        
        self.attendance_status = "Present"
        self.time_in = frappe.utils.now_datetime().time()
        self.save()
        frappe.msgprint(_("Marked as Present"))
    
    @frappe.whitelist()
    def mark_late(self):
        """Quick action to mark member as late"""
        if self.docstatus != 0:
            frappe.throw(_("Cannot modify submitted attendance"))
        
        self.attendance_status = "Late"
        self.time_in = frappe.utils.now_datetime().time()
        self.save()
        frappe.msgprint(_("Marked as Late"))
