import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class MemberFine(Document):
    def validate(self):
        self.validate_amount()
        self.calculate_balance()
        
    def validate_amount(self):
        """Validate fine amount"""
        if flt(self.amount) <= 0:
            frappe.throw(_("Amount must be greater than zero"))
            
    def calculate_balance(self):
        """Calculate outstanding balance"""
        self.balance = flt(self.amount) - flt(self.paid_amount) - flt(self.waived_amount)
        
        # Update status
        if flt(self.balance) <= 0:
            if flt(self.waived_amount) >= flt(self.amount):
                self.status = "Waived"
            else:
                self.status = "Paid"
        elif flt(self.paid_amount) > 0:
            self.status = "Partially Paid"
        else:
            self.status = "Unpaid"
            
    def on_submit(self):
        """Post to GL"""
        self.post_to_gl()
        self.update_member_fines()
        
    def on_cancel(self):
        """Reverse GL entry"""
        self.reverse_gl_entry()
        self.update_member_fines()
        
    def post_to_gl(self):
        """Post fine to GL"""
        from sacco_management.sacco.utils.gl_utils import post_fine_to_gl
        
        je = post_fine_to_gl(self)
        self.db_set("journal_entry", je.name)
        self.db_set("gl_posted", 1)
        
    def reverse_gl_entry(self):
        """Reverse GL entry"""
        from sacco_management.sacco.utils.gl_utils import reverse_gl_entry
        
        if self.journal_entry:
            reverse_gl_entry("Member Fine", self.name)
            self.db_set("gl_posted", 0)
            
    def update_member_fines(self):
        """Update member's fine balance"""
        member = frappe.get_doc("SACCO Member", self.member)
        member.update_fine_balance()
        member.db_update()


def on_submit(doc, method):
    pass


def on_cancel(doc, method):
    pass


@frappe.whitelist()
def waive_fine(fine, waive_amount, reason):
    """Waive a fine or part of it"""
    doc = frappe.get_doc("Member Fine", fine)
    
    if flt(waive_amount) > flt(doc.balance):
        frappe.throw(_("Waive amount cannot exceed balance"))
        
    doc.waived_amount = flt(doc.waived_amount) + flt(waive_amount)
    doc.remarks = (doc.remarks or "") + f"\nWaived {waive_amount}: {reason}"
    doc.calculate_balance()
    doc.save()
    
    return doc
