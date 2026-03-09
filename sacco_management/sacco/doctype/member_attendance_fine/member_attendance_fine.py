# Copyright (c) 2024, SACCO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today


class MemberAttendanceFine(Document):
    def validate(self):
        self.validate_waiver()
        self.calculate_net_amount()
        self.validate_member_meeting()
    
    def validate_waiver(self):
        """Validate waiver amount"""
        if flt(self.waived_amount) > flt(self.amount):
            frappe.throw(_("Waived amount cannot exceed fine amount"))
        
        if flt(self.waived_amount) > 0:
            # Check if waiver is allowed for this fine type
            fine_type = frappe.get_doc("Attendance Fine Type", self.fine_type)
            if not fine_type.waiver_allowed:
                frappe.throw(_("Waiver is not allowed for this fine type"))
            
            # Check max waiver percentage
            max_waiver = flt(self.amount) * flt(fine_type.max_waiver_percent) / 100
            if flt(self.waived_amount) > max_waiver:
                frappe.throw(_("Waiver amount exceeds maximum allowed ({0}%)").format(fine_type.max_waiver_percent))
            
            if not self.waiver_reason:
                frappe.throw(_("Please provide a reason for waiver"))
    
    def calculate_net_amount(self):
        """Calculate net amount after waiver"""
        self.net_amount = flt(self.amount) - flt(self.waived_amount)
    
    def validate_member_meeting(self):
        """Validate member was part of the meeting"""
        if self.meeting:
            attendance = frappe.db.exists("Meeting Register", {
                "meeting": self.meeting,
                "member": self.member
            })
            if not attendance:
                frappe.throw(_("No attendance record found for this member in this meeting"))
    
    def on_submit(self):
        """Post to GL on submit"""
        self.post_to_gl()
        
        # Update status
        if flt(self.waived_amount) >= flt(self.amount):
            self.db_set("status", "Waived")
        else:
            self.db_set("status", "Unpaid")
        
        # Update member's fine balance
        self.update_member_fine_balance()
        
        # Link to meeting register
        self.link_to_meeting_register()
    
    def on_cancel(self):
        """Reverse GL entry on cancel"""
        self.reverse_gl_entry()
        self.db_set("status", "Cancelled")
        self.update_member_fine_balance()
    
    def post_to_gl(self):
        """Post attendance fine to General Ledger"""
        if flt(self.net_amount) <= 0:
            return
        
        fine_type = frappe.get_doc("Attendance Fine Type", self.fine_type)
        
        # Get GL accounts
        receivable_account = fine_type.receivable_account or \
                            frappe.db.get_value("SACCO GL Account", 
                                {"account_type": "Asset", "account_name": ["like", "%Receivable%"]}, "name")
        
        income_account = fine_type.gl_account or \
                        frappe.db.get_value("SACCO GL Account", 
                            {"account_type": "Income", "account_name": ["like", "%Fine%"]}, "name")
        
        if not receivable_account or not income_account:
            frappe.throw(_("Please configure GL accounts for attendance fine type"))
        
        from sacco_management.sacco.utils.gl_utils import create_gl_entry
        
        accounts = [
            {
                "account": receivable_account,
                "debit": flt(self.net_amount),
                "credit": 0,
                "party_type": "SACCO Member",
                "party": self.member,
                "reference_type": "Member Attendance Fine",
                "reference_name": self.name
            },
            {
                "account": income_account,
                "debit": 0,
                "credit": flt(self.net_amount),
                "party_type": "SACCO Member",
                "party": self.member,
                "reference_type": "Member Attendance Fine",
                "reference_name": self.name
            }
        ]
        
        meeting_title = frappe.db.get_value("SACCO Meeting", self.meeting, "title") if self.meeting else ""
        
        gl_entry = create_gl_entry(
            voucher_type="Member Attendance Fine",
            voucher_no=self.name,
            accounts=accounts,
            posting_date=self.posting_date,
            remarks=f"Attendance fine for {self.member_name} - Meeting: {meeting_title}"
        )
        
        if gl_entry:
            self.db_set("gl_entry", gl_entry)
    
    def reverse_gl_entry(self):
        """Reverse the GL entry on cancellation"""
        if self.gl_entry:
            je = frappe.get_doc("SACCO Journal Entry", self.gl_entry)
            if je.docstatus == 1:
                je.cancel()
    
    def update_member_fine_balance(self):
        """Update member's outstanding fine balance"""
        member = frappe.get_doc("SACCO Member", self.member)
        
        # Calculate total outstanding attendance fines
        outstanding = frappe.db.sql("""
            SELECT COALESCE(SUM(net_amount), 0) as total
            FROM `tabMember Attendance Fine`
            WHERE member = %s AND docstatus = 1 AND status = 'Unpaid'
        """, (self.member,), as_dict=True)
        
        total_outstanding = flt(outstanding[0].total if outstanding else 0)
        
        # Also include regular fines
        regular_fines = frappe.db.sql("""
            SELECT COALESCE(SUM(amount - COALESCE(waived_amount, 0) - COALESCE(paid_amount, 0)), 0) as total
            FROM `tabMember Fine`
            WHERE member = %s AND docstatus = 1 AND status IN ('Unpaid', 'Partially Paid')
        """, (self.member,), as_dict=True)
        
        total_outstanding += flt(regular_fines[0].total if regular_fines else 0)
        
        # Update member record
        frappe.db.set_value("SACCO Member", self.member, "fine_balance", total_outstanding)
    
    def link_to_meeting_register(self):
        """Link this fine to the meeting register entry"""
        if self.meeting:
            register = frappe.db.get_value("Meeting Register", {
                "meeting": self.meeting,
                "member": self.member
            }, "name")
            
            if register:
                frappe.db.set_value("Meeting Register", register, {
                    "fine_generated": 1,
                    "fine_reference": self.name
                })
    
    @frappe.whitelist()
    def waive_fine(self, waiver_amount, reason):
        """Waive part or all of the fine"""
        if self.docstatus != 1:
            frappe.throw(_("Can only waive submitted fines"))
        
        if self.status in ["Paid", "Waived", "Cancelled"]:
            frappe.throw(_("Cannot waive a fine that is already {0}").format(self.status))
        
        fine_type = frappe.get_doc("Attendance Fine Type", self.fine_type)
        if not fine_type.waiver_allowed:
            frappe.throw(_("Waiver is not allowed for this fine type"))
        
        waiver_amount = flt(waiver_amount)
        max_waiver = flt(self.amount) * flt(fine_type.max_waiver_percent) / 100
        
        if waiver_amount > max_waiver:
            frappe.throw(_("Waiver amount exceeds maximum allowed ({0})").format(max_waiver))
        
        self.db_set({
            "waived_amount": waiver_amount,
            "waiver_reason": reason,
            "net_amount": flt(self.amount) - waiver_amount
        })
        
        if waiver_amount >= flt(self.amount):
            self.db_set("status", "Waived")
        
        frappe.msgprint(_("Fine waived successfully"))


def on_submit(doc, method):
    """Hook for on_submit event"""
    doc.post_to_gl()


def on_cancel(doc, method):
    """Hook for on_cancel event"""
    doc.reverse_gl_entry()
