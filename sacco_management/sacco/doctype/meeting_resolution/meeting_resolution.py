# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class MeetingResolution(Document):
    def validate(self):
        self.validate_meeting()
        self.calculate_voting_results()
        self.validate_signatures()
        
    def validate_meeting(self):
        """Validate meeting exists"""
        if not self.sacco_meeting:
            frappe.throw(_("SACCO Meeting is required"))
    
    def calculate_voting_results(self):
        """Calculate voting results"""
        if self.voting_required:
            self.total_votes_cast = flt(self.votes_in_favor) + flt(self.votes_against) + flt(self.votes_abstained)
            
            # Determine result
            if flt(self.votes_in_favor) > flt(self.votes_against):
                self.result = "Passed"
            elif flt(self.votes_against) > flt(self.votes_in_favor):
                self.result = "Rejected"
            else:
                self.result = "Tie"
    
    def validate_signatures(self):
        """Validate required signatures"""
        if self.docstatus == 1 and self.status == "Passed":
            if not self.approved_by_chairperson:
                frappe.throw(_("Chairperson approval is required for passed resolutions"))
    
    def before_submit(self):
        """Set status based on voting result"""
        if self.voting_required and self.result == "Rejected":
            self.status = "Rejected"
        elif self.voting_required and self.result == "Passed":
            self.status = "Passed"
        else:
            self.status = "Passed"  # Non-voted resolutions are considered passed
    
    def on_submit(self):
        """Create meeting minute entry"""
        self.create_minute_entry()
    
    def create_minute_entry(self):
        """Create entry in meeting minutes"""
        try:
            meeting = frappe.get_doc("SACCO Meeting", self.sacco_meeting)
            
            # Add resolution to meeting minutes
            if not meeting.meeting_minutes:
                meeting.meeting_minutes = f"<h3>Resolution {self.resolution_number}</h3><p>{self.resolution_title}</p>"
            else:
                meeting.meeting_minutes += f"<br><br><h3>Resolution {self.resolution_number}</h3><p>{self.resolution_title}</p>"
            
            meeting.save(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(
                message=f"Error creating minute entry for resolution {self.name}: {str(e)}",
                title="Meeting Resolution Error"
            )
