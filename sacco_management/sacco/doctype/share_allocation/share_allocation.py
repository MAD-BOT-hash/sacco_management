import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class ShareAllocation(Document):
    def validate(self):
        self.validate_member_status()
        self.validate_share_type()
        self.validate_quantity()
        self.calculate_total()
        
    def validate_member_status(self):
        """Ensure member is active"""
        status = frappe.db.get_value("SACCO Member", self.member, "status")
        if status != "Active":
            frappe.throw(_("Cannot allocate shares to {0} member").format(status))
            
    def validate_share_type(self):
        """Validate share type is active"""
        is_active = frappe.db.get_value("Share Type", self.share_type, "is_active")
        if not is_active:
            frappe.throw(_("Share Type {0} is not active").format(self.share_type))
            
    def validate_quantity(self):
        """Validate share quantity"""
        if self.quantity <= 0:
            frappe.throw(_("Quantity must be greater than zero"))
            
        share_type = frappe.get_doc("Share Type", self.share_type)
        
        if self.quantity < share_type.min_shares:
            frappe.throw(_("Minimum shares for {0} is {1}").format(
                self.share_type, share_type.min_shares
            ))
            
        if share_type.max_shares > 0:
            # Get existing shares
            existing = frappe.db.sql("""
                SELECT COALESCE(SUM(quantity), 0)
                FROM `tabShare Allocation`
                WHERE member = %s AND share_type = %s AND docstatus = 1 
                AND status = 'Allocated' AND name != %s
            """, (self.member, self.share_type, self.name or ""))[0][0]
            
            total = flt(existing) + self.quantity
            if total > share_type.max_shares:
                frappe.throw(
                    _("Maximum shares allowed is {0}. Current: {1}, Requested: {2}").format(
                        share_type.max_shares, existing, self.quantity
                    )
                )
                
    def calculate_total(self):
        """Calculate total amount"""
        share_type = frappe.get_doc("Share Type", self.share_type)
        self.price_per_share = share_type.price_per_share
        self.total_amount = flt(self.quantity) * flt(self.price_per_share)
        
    def on_submit(self):
        """Handle share allocation submission"""
        self.db_set("status", "Allocated")
        self.post_to_gl()
        self.update_member_shares()
        
    def on_cancel(self):
        """Handle cancellation"""
        self.reverse_gl_entry()
        self.update_member_shares()
        
    def post_to_gl(self):
        """Post share allocation to GL"""
        from sacco_management.sacco.utils.gl_utils import post_share_allocation_to_gl
        
        je = post_share_allocation_to_gl(self)
        self.db_set("journal_entry", je.name)
        self.db_set("gl_posted", 1)
        
    def reverse_gl_entry(self):
        """Reverse GL entry"""
        from sacco_management.sacco.utils.gl_utils import reverse_gl_entry
        
        if self.journal_entry:
            reverse_gl_entry("Share Allocation", self.name)
            self.db_set("gl_posted", 0)
            
    def update_member_shares(self):
        """Update member's share balance"""
        member = frappe.get_doc("SACCO Member", self.member)
        member.update_share_balance()
        member.db_update()


def on_submit(doc, method):
    """Hook called on submit"""
    pass


def on_cancel(doc, method):
    """Hook called on cancel"""
    pass


@frappe.whitelist()
def get_member_shares(member, share_type=None):
    """Get member's share holdings"""
    conditions = "member = %(member)s AND docstatus = 1 AND status = 'Allocated'"
    values = {"member": member}
    
    if share_type:
        conditions += " AND share_type = %(share_type)s"
        values["share_type"] = share_type
        
    holdings = frappe.db.sql(f"""
        SELECT 
            share_type,
            SUM(quantity) as total_shares,
            SUM(total_amount) as total_value
        FROM `tabShare Allocation`
        WHERE {conditions}
        GROUP BY share_type
    """, values, as_dict=True)
    
    return holdings
