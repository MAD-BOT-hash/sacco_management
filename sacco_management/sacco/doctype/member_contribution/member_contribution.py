import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class MemberContribution(Document):
    def validate(self):
        self.validate_amount()
        self.validate_member_status()
        self.validate_one_time_contribution()
        
    def validate_amount(self):
        """Validate contribution amount against type limits"""
        if flt(self.amount) <= 0:
            frappe.throw(_("Amount must be greater than zero"))
            
        contrib_type = frappe.get_doc("Contribution Type", self.contribution_type)
        
        if contrib_type.minimum_amount and flt(self.amount) < flt(contrib_type.minimum_amount):
            frappe.throw(_("Minimum amount for {0} is {1}").format(
                self.contribution_type, contrib_type.minimum_amount
            ))
            
        if contrib_type.maximum_amount and flt(contrib_type.maximum_amount) > 0:
            if flt(self.amount) > flt(contrib_type.maximum_amount):
                frappe.throw(_("Maximum amount for {0} is {1}").format(
                    self.contribution_type, contrib_type.maximum_amount
                ))
                
    def validate_member_status(self):
        """Ensure member is active"""
        status = frappe.db.get_value("SACCO Member", self.member, "status")
        if status != "Active":
            frappe.throw(_("Cannot accept contribution for {0} member").format(status))
            
    def validate_one_time_contribution(self):
        """Check if one-time contribution already paid"""
        contrib_type = frappe.get_doc("Contribution Type", self.contribution_type)
        
        if contrib_type.is_one_time:
            existing = frappe.db.exists(
                "Member Contribution",
                {
                    "member": self.member,
                    "contribution_type": self.contribution_type,
                    "docstatus": 1,
                    "name": ("!=", self.name)
                }
            )
            if existing:
                frappe.throw(_("One-time contribution {0} has already been paid by this member").format(
                    self.contribution_type
                ))
    
    def on_submit(self):
        """Post to GL and update member balance"""
        self.post_to_gl()
        self.update_member_balance()
        
    def on_cancel(self):
        """Reverse GL entry and update member balance"""
        self.reverse_gl_entry()
        self.update_member_balance()
        
    def post_to_gl(self):
        """Post contribution to General Ledger"""
        from sacco_management.sacco.utils.gl_utils import post_contribution_to_gl
        
        je = post_contribution_to_gl(self)
        self.db_set("journal_entry", je.name)
        self.db_set("gl_posted", 1)
        
    def reverse_gl_entry(self):
        """Reverse GL entry on cancellation"""
        from sacco_management.sacco.utils.gl_utils import reverse_gl_entry
        
        if self.journal_entry:
            reverse_gl_entry("Member Contribution", self.name)
            self.db_set("gl_posted", 0)
            
    def update_member_balance(self):
        """Update member's contribution balance"""
        member = frappe.get_doc("SACCO Member", self.member)
        member.update_contribution_balance()
        member.db_update()


def on_submit(doc, method):
    """Hook called on submit"""
    pass  # Handled in class method


def on_cancel(doc, method):
    """Hook called on cancel"""
    pass  # Handled in class method


def get_permission_query_conditions(user):
    """Branch-based permission query"""
    if not user:
        user = frappe.session.user
        
    roles = frappe.get_roles(user)
    if "System Manager" in roles or "SACCO Admin" in roles:
        return ""
        
    user_branch = frappe.db.get_value("User", user, "branch")
    if user_branch:
        return f"""(`tabMember Contribution`.member IN 
            (SELECT name FROM `tabSACCO Member` WHERE branch = '{user_branch}'))"""
    
    return ""


def has_permission(doc, ptype, user):
    """Check branch-based permission"""
    if not user:
        user = frappe.session.user
        
    roles = frappe.get_roles(user)
    if "System Manager" in roles or "SACCO Admin" in roles:
        return True
        
    member_branch = frappe.db.get_value("SACCO Member", doc.member, "branch")
    user_branch = frappe.db.get_value("User", user, "branch")
    
    if user_branch and member_branch == user_branch:
        return True
        
    return False


@frappe.whitelist()
def get_contribution_summary(member, from_date=None, to_date=None):
    """Get contribution summary for a member"""
    conditions = "mc.member = %(member)s AND mc.docstatus = 1"
    values = {"member": member}
    
    if from_date:
        conditions += " AND mc.contribution_date >= %(from_date)s"
        values["from_date"] = from_date
        
    if to_date:
        conditions += " AND mc.contribution_date <= %(to_date)s"
        values["to_date"] = to_date
    
    summary = frappe.db.sql(f"""
        SELECT 
            mc.contribution_type,
            COUNT(*) as count,
            SUM(mc.amount) as total_amount,
            MIN(mc.contribution_date) as first_date,
            MAX(mc.contribution_date) as last_date
        FROM `tabMember Contribution` mc
        WHERE {conditions}
        GROUP BY mc.contribution_type
    """, values, as_dict=True)
    
    return summary


@frappe.whitelist()
def get_monthly_contributions(member, year=None):
    """Get monthly contribution breakdown for a member"""
    from frappe.utils import nowdate, getdate
    
    if not year:
        year = getdate(nowdate()).year
        
    contributions = frappe.db.sql("""
        SELECT 
            MONTH(contribution_date) as month,
            contribution_type,
            SUM(amount) as total
        FROM `tabMember Contribution`
        WHERE member = %(member)s 
        AND YEAR(contribution_date) = %(year)s
        AND docstatus = 1
        GROUP BY MONTH(contribution_date), contribution_type
        ORDER BY month
    """, {"member": member, "year": year}, as_dict=True)
    
    return contributions
