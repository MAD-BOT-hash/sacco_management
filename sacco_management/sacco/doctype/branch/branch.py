import frappe
from frappe.model.document import Document


class Branch(Document):
    def validate(self):
        self.validate_branch_code()
        
    def validate_branch_code(self):
        """Ensure branch code is uppercase and alphanumeric"""
        if self.branch_code:
            self.branch_code = self.branch_code.upper().strip()
            
    def on_update(self):
        self.update_statistics()
        
    def update_statistics(self):
        """Update branch statistics"""
        # Count total members
        self.total_members = frappe.db.count("SACCO Member", {"branch": self.name, "status": "Active"})
        
        # Sum total contributions
        total_contrib = frappe.db.sql("""
            SELECT COALESCE(SUM(mc.amount), 0)
            FROM `tabMember Contribution` mc
            INNER JOIN `tabSACCO Member` sm ON mc.member = sm.name
            WHERE sm.branch = %s AND mc.docstatus = 1
        """, self.name)[0][0] or 0
        self.total_contributions = total_contrib
        
        # Sum total loans disbursed
        total_loans = frappe.db.sql("""
            SELECT COALESCE(SUM(la.disbursed_amount), 0)
            FROM `tabLoan Application` la
            INNER JOIN `tabSACCO Member` sm ON la.member = sm.name
            WHERE sm.branch = %s AND la.docstatus = 1 AND la.status = 'Disbursed'
        """, self.name)[0][0] or 0
        self.total_loans_disbursed = total_loans


@frappe.whitelist()
def get_branch_summary(branch):
    """Get summary statistics for a branch"""
    doc = frappe.get_doc("Branch", branch)
    doc.update_statistics()
    doc.save()
    
    return {
        "total_members": doc.total_members,
        "total_contributions": doc.total_contributions,
        "total_loans_disbursed": doc.total_loans_disbursed
    }
