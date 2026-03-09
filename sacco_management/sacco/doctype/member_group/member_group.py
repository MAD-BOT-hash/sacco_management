import frappe
from frappe.model.document import Document


class MemberGroup(Document):
    def validate(self):
        self.validate_group_code()
        self.validate_leadership()
        
    def validate_group_code(self):
        """Ensure group code is uppercase"""
        if self.group_code:
            self.group_code = self.group_code.upper().strip()
    
    def validate_leadership(self):
        """Ensure leadership members belong to this group"""
        leadership_fields = ['chairperson', 'secretary', 'treasurer']
        for field in leadership_fields:
            member = getattr(self, field, None)
            if member:
                member_group = frappe.db.get_value("SACCO Member", member, "member_group")
                if member_group and member_group != self.name:
                    frappe.throw(f"The {field.replace('_', ' ')} must be a member of this group")
                    
    def on_update(self):
        self.update_statistics()
        
    def update_statistics(self):
        """Update group statistics"""
        self.total_members = frappe.db.count("SACCO Member", {
            "member_group": self.name, 
            "status": "Active"
        })
        
        # Calculate total contributions
        total_contrib = frappe.db.sql("""
            SELECT COALESCE(SUM(mc.amount), 0)
            FROM `tabMember Contribution` mc
            INNER JOIN `tabSACCO Member` sm ON mc.member = sm.name
            WHERE sm.member_group = %s AND mc.docstatus = 1
        """, self.name)[0][0] or 0
        self.total_contributions = total_contrib
        
        # Calculate total loans
        total_loans = frappe.db.sql("""
            SELECT COALESCE(SUM(la.disbursed_amount), 0)
            FROM `tabLoan Application` la
            INNER JOIN `tabSACCO Member` sm ON la.member = sm.name
            WHERE sm.member_group = %s AND la.docstatus = 1 AND la.status = 'Disbursed'
        """, self.name)[0][0] or 0
        self.total_loans = total_loans
        
        # Count active loans
        self.active_loans = frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabLoan Application` la
            INNER JOIN `tabSACCO Member` sm ON la.member = sm.name
            WHERE sm.member_group = %s AND la.docstatus = 1 
            AND la.status IN ('Disbursed', 'Active')
        """, self.name)[0][0] or 0
