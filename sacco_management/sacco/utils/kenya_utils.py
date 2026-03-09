"""
Advanced Features for Kenyan SACCO Compliance

This module provides features specifically designed for Kenyan SACCOs
to comply with SASRA (Sacco Societies Regulatory Authority) requirements.

Key Features:
- BOSA/FOSA Core Banking Integration
- Mobile Money Integration (M-Pesa, Airtel Money)
- CRB Reporting Integration
- Deposit Protection Insurance Fund (DPIF) Calculations
- Liquidity Ratio Monitoring
- Capital Adequacy Compliance
- Member Share Pledge Management
- Agency Banking Support
"""

import frappe
from frappe import _
from datetime import datetime, timedelta
import requests
import json


# =============================================================================
# MOBILE MONEY INTEGRATION
# =============================================================================

class MPesaIntegration:
    """
    M-Pesa Daraja API Integration for SACCO transactions
    
    Supports:
    - STK Push for member contributions
    - B2C for loan disbursements
    - C2B for paybill payments
    - Transaction status queries
    """
    
    def __init__(self):
        self.consumer_key = frappe.db.get_single_value("SACCO Settings", "mpesa_consumer_key")
        self.consumer_secret = frappe.db.get_single_value("SACCO Settings", "mpesa_consumer_secret")
        self.shortcode = frappe.db.get_single_value("SACCO Settings", "mpesa_shortcode")
        self.passkey = frappe.db.get_single_value("SACCO Settings", "mpesa_passkey")
        self.environment = frappe.db.get_single_value("SACCO Settings", "mpesa_environment")
        
        self.base_url = "https://api.safaricom.co.ke" if self.environment == "Production" else "https://sandbox.safaricom.co.ke"
        self.access_token = None
        self.token_expiry = None
    
    def get_access_token(self):
        """Get OAuth access token"""
        from frappe.utils import now_datetime
        
        # Return cached token if still valid
        if self.access_token and self.token_expiry > now_datetime():
            return self.access_token
        
        try:
            response = requests.get(
                f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials",
                auth=(self.consumer_key, self.consumer_secret),
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                self.access_token = result["access_token"]
                self.token_expiry = now_datetime() + timedelta(hours=1)
                return self.access_token
            else:
                frappe.log_error(f"M-Pesa Token Error: {response.text}")
                return None
                
        except Exception as e:
            frappe.log_error(f"M-Pesa Token Exception: {str(e)}")
            return None
    
    def stk_push(self, phone_number, amount, account_reference, transaction_type="Contribution"):
        """
        Initiate STK Push to member's phone
        
        Args:
            phone_number (str): Member phone (254XXXXXXXXX)
            amount (float): Amount to charge
            account_reference (str): Member ID or account number
            transaction_type (str): Type of transaction
        
        Returns:
            dict: STK push response
        """
        access_token = self.get_access_token()
        if not access_token:
            return {"error": "Failed to get access token"}
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = f"{self.shortcode}{self.passkey}{timestamp}"
        
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": frappe.generate_hash(password)[:64],  # Base64 encoded
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone_number,
            "PartyB": self.shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": f"{frappe.utils.get_url()}/api/method/sacco_management.sacco.utils.kenya_utils.mpesa_callback",
            "AccountReference": account_reference,
            "TransactionDesc": transaction_type
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            result = response.json()
            
            # Log transaction request
            self.log_mobile_transaction(result, "STK_PUSH_REQUEST")
            
            return result
            
        except Exception as e:
            frappe.log_error(f"STK Push Error: {str(e)}")
            return {"error": str(e)}
    
    def b2c_payment(self, phone_number, amount, payment_type="Loan Disbursement", recipient_name=None):
        """
        Send payment to member via B2C
        
        Args:
            phone_number (str): Recipient phone
            amount (float): Amount to send
            payment_type (str): Payment purpose
            recipient_name (str): Recipient name
        
        Returns:
            dict: B2C response
        """
        access_token = self.get_access_token()
        if not access_token:
            return {"error": "Failed to get access token"}
        
        payload = {
            "SecurityCredential": self.generate_security_credential(),
            "CommandID": "SalaryPayment" if payment_type == "Loan Disbursement" else "BusinessPayment",
            "Amount": int(amount),
            "PartyA": self.shortcode,
            "PartyB": phone_number,
            "Remarks": payment_type,
            "QueueTimeOutSeconds": 3700,
            "ResultType": "Completed",
            "Occasion": payment_type
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/mpesa/b2c/v1/paymentrequest",
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            result = response.json()
            self.log_mobile_transaction(result, "B2C_REQUEST")
            
            return result
            
        except Exception as e:
            frappe.log_error(f"B2C Payment Error: {str(e)}")
            return {"error": str(e)}
    
    def log_mobile_transaction(self, response_data, transaction_type):
        """Log mobile money transaction"""
        try:
            doc = frappe.new_doc("Mobile Money Transaction")
            doc.transaction_type = transaction_type
            doc.response_data = json.dumps(response_data)
            doc.status = "Pending"
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Transaction Logging Error: {str(e)}")
    
    def generate_security_credential(self):
        """Generate security credential for B2C"""
        # Implementation depends on your certificate setup
        return frappe.db.get_single_value("SACCO Settings", "b2c_security_credential")


# =============================================================================
# CRB REPORTING INTEGRATION
# =============================================================================

class CRBIntegration:
    """
    Credit Reference Bureau (CRB) Integration
    
    Supports integration with licensed CRBs in Kenya:
    - Metropol CRB
    - TransUnion
    - Creditinfo
    
    For loan applicant screening and reporting
    """
    
    def __init__(self, crb_provider="Metropol"):
        self.provider = crb_provider
        self.api_config = frappe.get_doc("CRB Provider Settings", crb_provider)
    
    def submit_loan_enquiry(self, member_id, national_id, loan_amount):
        """
        Submit loan enquiry to CRB
        
        Args:
            member_id (str): Member ID
            national_id (str): National ID number
            loan_amount (float): Loan amount applied for
        
        Returns:
            dict: CRB response with credit score and report
        """
        try:
            # Get member details
            member = frappe.get_doc("SACCO Member", member_id)
            
            payload = {
                "national_id": national_id,
                "full_name": member.member_name,
                "loan_amount": loan_amount,
                "institution_code": self.api_config.institution_code,
                "reference_id": member_id
            }
            
            response = requests.post(
                self.api_config.enquiry_endpoint,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            
            result = response.json()
            
            # Store CRB report
            self.store_crb_report(member_id, result)
            
            return result
            
        except Exception as e:
            frappe.log_error(f"CRB Enquiry Error: {str(e)}")
            return {"error": str(e)}
    
    def submit_monthly_returns(self, reporting_date):
        """
        Submit monthly returns to CRB
        
        Args:
            reporting_date (str): Date for which to report
        """
        # Get all active loans
        loans = frappe.get_all(
            "Loan Application",
            filters={
                "docstatus": 1,
                "status": ["in", ["Disbursed", "Active"]]
            },
            fields=["name", "member", "outstanding_principal", "overdue_amount"]
        )
        
        submissions = []
        for loan in loans:
            member = frappe.get_doc("SACCO Member", loan.member)
            
            submission_data = {
                "loan_account": loan.name,
                "member_name": member.member_name,
                "national_id": member.national_id,
                "loan_balance": loan.outstanding_principal,
                "arrears": loan.overdue_amount,
                "reporting_date": reporting_date,
                "status": "Active" if loan.overdue_amount == 0 else "Arrears"
            }
            
            try:
                response = requests.post(
                    self.api_config.monthly_returns_endpoint,
                    json=submission_data,
                    headers=self.api_config.get_headers()
                )
                
                submissions.append({
                    "loan": loan.name,
                    "success": response.status_code == 200,
                    "response": response.text
                })
                
            except Exception as e:
                submissions.append({
                    "loan": loan.name,
                    "success": False,
                    "error": str(e)
                })
        
        return submissions
    
    def store_crb_report(self, member_id, report_data):
        """Store CRB report in system"""
        try:
            doc = frappe.new_doc("CRB Report")
            doc.member = member_id
            doc.report_date = datetime.now()
            doc.credit_score = report_data.get("credit_score")
            doc.risk_band = report_data.get("risk_band")
            doc.total_exposure = report_data.get("total_exposure")
            doc.number_of_facilities = report_data.get("number_of_facilities")
            doc.raw_response = json.dumps(report_data)
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"CRB Report Storage Error: {str(e)}")


# =============================================================================
# REGULATORY COMPLIANCE
# =============================================================================

class SASRACompliance:
    """
    SASRA Regulatory Compliance Tools
    
    Monitors and ensures compliance with:
    - Liquidity Ratio (minimum 15%)
    - Capital Adequacy Ratio (minimum 10%)
    - Single Borrower Limit (max 20% of capital)
    - Connected Borrowing Limits
    - Deposit Protection Fund Contributions
    """
    
    @staticmethod
    def calculate_liquidity_ratio():
        """
        Calculate current liquidity ratio
        
        Formula: Liquid Assets / Total Deposits * 100
        
        Returns:
            float: Liquidity ratio percentage
        """
        # Liquid assets
        liquid_assets = frappe.db.sql("""
            SELECT 
                SUM(current_balance) as total
            FROM `tabSavings Account`
            WHERE account_type IN ('Cash', 'Bank Balance', 'Fixed Deposit')
            AND status = 'Active'
            AND docstatus = 1
        """)[0][0] or 0
        
        # Total deposits (member savings)
        total_deposits = frappe.db.sql("""
            SELECT 
                SUM(current_balance) as total
            FROM `tabSavings Account`
            WHERE account_type = 'Member Savings'
            AND status = 'Active'
            AND docstatus = 1
        """)[0][0] or 0
        
        if total_deposits == 0:
            return 0
        
        ratio = (liquid_assets / total_deposits) * 100
        
        # Log compliance status
        SASRACompliance.log_compliance_metric("Liquidity Ratio", ratio, 15.0)
        
        return ratio
    
    @staticmethod
    def calculate_capital_adequacy_ratio():
        """
        Calculate Capital Adequacy Ratio (CAR)
        
        Formula: Total Capital / Risk-Weighted Assets * 100
        
        Returns:
            float: CAR percentage
        """
        # Total capital (share capital + reserves)
        total_capital = frappe.db.sql("""
            SELECT 
                SUM(total_amount) as share_capital
            FROM `tabShare Allocation`
            WHERE docstatus = 1 AND status = 'Allocated'
        """)[0][0] or 0
        
        # Add retained earnings from GL
        retained_earnings = frappe.db.sql("""
            SELECT 
                SUM(debit - credit) as balance
            FROM `tabSACCO GL Entry`
            WHERE account LIKE '%Retained Earnings%'
        """)[0][0] or 0
        
        total_capital += abs(retained_earnings)
        
        # Risk-weighted assets (simplified)
        risk_weighted_assets = frappe.db.sql("""
            SELECT 
                SUM(outstanding_principal * 
                    CASE 
                        WHEN status = 'Non-Performing' THEN 1.5
                        WHEN overdue_amount > 0 THEN 1.2
                        ELSE 1.0
                    END
                ) as rwa
            FROM `tabLoan Application`
            WHERE docstatus = 1 AND status IN ('Disbursed', 'Active')
        """)[0][0] or 0
        
        if risk_weighted_assets == 0:
            return 0
        
        car = (total_capital / risk_weighted_assets) * 100
        
        SASRACompliance.log_compliance_metric("Capital Adequacy Ratio", car, 10.0)
        
        return car
    
    @staticmethod
    def check_single_borrower_limit(member_id, new_loan_amount):
        """
        Check if loan exceeds single borrower limit (20% of capital)
        
        Args:
            member_id (str): Member applying for loan
            new_loan_amount (float): Loan amount
        
        Returns:
            dict: Compliance check result
        """
        total_capital = frappe.db.sql("""
            SELECT SUM(total_amount) 
            FROM `tabShare Allocation`
            WHERE docstatus = 1 AND status = 'Allocated'
        """)[0][0] or 0
        
        max_allowed = total_capital * 0.20
        
        # Get existing loans for member
        existing_loans = frappe.db.sql("""
            SELECT SUM(outstanding_principal) 
            FROM `tabLoan Application`
            WHERE member = %s 
            AND docstatus = 1 
            AND status IN ('Disbursed', 'Active')
        """, (member_id,))[0][0] or 0
        
        total_exposure = existing_loans + new_loan_amount
        
        return {
            "compliant": total_exposure <= max_allowed,
            "existing_exposure": existing_loans,
            "new_loan": new_loan_amount,
            "total_exposure": total_exposure,
            "single_borrower_limit": max_allowed,
            "percentage_of_limit": (total_exposure / max_allowed * 100) if max_allowed > 0 else 0
        }
    
    @staticmethod
    def calculate_deposit_protection_fund(total_deposits):
        """
        Calculate monthly DPIF contribution
        
        Current rate: 0.2% of total deposit liabilities
        
        Args:
            total_deposits (float): Total member deposits
        
        Returns:
            float: Monthly contribution amount
        """
        dpif_rate = 0.002  # 0.2%
        return total_deposits * dpif_rate
    
    @staticmethod
    def log_compliance_metric(metric_name, actual_value, minimum_required):
        """Log compliance metric for regulatory reporting"""
        try:
            doc = frappe.new_doc("Regulatory Compliance Log")
            doc.metric_name = metric_name
            doc.actual_value = actual_value
            doc.minimum_required = minimum_required
            doc.is_compliant = actual_value >= minimum_required
            doc.reporting_date = datetime.now()
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Compliance Logging Error: {str(e)}")
    
    @staticmethod
    def generate_regulatory_report(report_type, period):
        """
        Generate regulatory reports for SASRA
        
        Args:
            report_type (str): Type of report (Monthly, Quarterly, Annual)
            period (str): Reporting period
        
        Returns:
            dict: Complete regulatory report
        """
        report = {
            "report_type": report_type,
            "period": period,
            "generated_date": datetime.now(),
            "metrics": {}
        }
        
        # Key performance indicators
        report["metrics"]["liquidity_ratio"] = {
            "value": SASRACompliance.calculate_liquidity_ratio(),
            "minimum": 15.0,
            "unit": "%"
        }
        
        report["metrics"]["capital_adequacy_ratio"] = {
            "value": SASRACompliance.calculate_capital_adequacy_ratio(),
            "minimum": 10.0,
            "unit": "%"
        }
        
        # Get total assets
        report["metrics"]["total_assets"] = {
            "value": frappe.db.sql("SELECT SUM(total_assets) FROM `tabSACCO Balance Sheet`")[0][0] or 0,
            "unit": "KES"
        }
        
        # Non-performing loans
        report["metrics"]["npl_ratio"] = {
            "value": SASRACompliance.calculate_npl_ratio(),
            "unit": "%"
        }
        
        return report
    
    @staticmethod
    def calculate_npl_ratio():
        """Calculate Non-Performing Loans ratio"""
        npl = frappe.db.sql("""
            SELECT SUM(outstanding_principal)
            FROM `tabLoan Application`
            WHERE docstatus = 1 
            AND status = 'Non-Performing'
        """)[0][0] or 0
        
        total_loans = frappe.db.sql("""
            SELECT SUM(outstanding_principal)
            FROM `tabLoan Application`
            WHERE docstatus = 1 
            AND status IN ('Disbursed', 'Active', 'Non-Performing')
        """)[0][0] or 0
        
        if total_loans == 0:
            return 0
        
        return (npl / total_loans) * 100


# =============================================================================
# SHARE PLEDGE MANAGEMENT
# =============================================================================

def create_share_pledge(member_id, loan_id, pledged_shares):
    """
    Create share pledge against a loan
    
    Args:
        member_id (str): Member pledging shares
        loan_id (str): Loan being secured
        pledged_shares (int): Number of shares being pledged
    
    Returns:
        doc: Share Pledge document
    """
    try:
        # Verify member owns the shares
        owned_shares = frappe.db.sql("""
            SELECT SUM(quantity) 
            FROM `tabShare Allocation`
            WHERE member = %s 
            AND docstatus = 1 
            AND status = 'Allocated'
            AND pledged = 0
        """, (member_id,))[0][0] or 0
        
        if owned_shares < pledged_shares:
            frappe.throw(
                f"Member owns {owned_shares} unpledged shares but attempting to pledge {pledged_shares} shares"
            )
        
        # Create pledge
        pledge = frappe.new_doc("Share Pledge")
        pledge.member = member_id
        pledge.loan = loan_id
        pledge.number_of_shares = pledged_shares
        pledge.pledge_date = datetime.now()
        pledge.status = "Active"
        
        # Calculate pledge value
        share_price = frappe.db.get_single_value("SACCO Settings", "share_price")
        pledge.total_value = pledged_shares * share_price
        
        pledge.insert(ignore_permissions=True)
        
        # Mark shares as pledged
        update_share_pledge_status(member_id, pledged_shares, "Pledged")
        
        frappe.db.commit()
        
        return pledge
        
    except Exception as e:
        frappe.log_error(f"Share Pledge Creation Error: {str(e)}")
        raise


def update_share_pledge_status(member_id, shares, status):
    """Update shares as pledged or released"""
    shares_to_update = frappe.db.sql("""
        SELECT name, quantity 
        FROM `tabShare Allocation`
        WHERE member = %s 
        AND docstatus = 1 
        AND status = 'Allocated'
        AND pledged = 0
        ORDER BY allocation_date ASC
    """, (member_id,), as_dict=True)
    
    remaining = shares
    for share_doc in shares_to_update:
        if remaining <= 0:
            break
        
        update_qty = min(remaining, share_doc.quantity)
        frappe.db.set_value(
            "Share Allocation",
            share_doc.name,
            "pledged",
            1 if status == "Pledged" else 0
        )
        remaining -= update_qty


# =============================================================================
# AGENCY BANKING SUPPORT
# =============================================================================

class AgencyBankingManager:
    """
    Manage agency banking network for rural outreach
    
    Features:
    - Agent registration and management
    - Cash-up process
    - Commission calculations
    - Transaction limits
    """
    
    @staticmethod
    def register_agent(agent_details):
        """Register new banking agent"""
        try:
            agent = frappe.new_doc("Banking Agent")
            agent.update(agent_details)
            agent.status = "Active"
            agent.registration_date = datetime.now()
            agent.insert(ignore_permissions=True)
            frappe.db.commit()
            return agent
        except Exception as e:
            frappe.log_error(f"Agent Registration Error: {str(e)}")
            return None
    
    @staticmethod
    def process_cash_up(agent_id, cash_amount, transaction_details):
        """
        Process cash-up from agent
        
        Args:
            agent_id (str): Agent ID
            cash_amount (float): Cash being deposited
            transaction_details (dict): Transaction breakdown
        
        Returns:
            doc: Cash-up transaction document
        """
        try:
            cash_up = frappe.new_doc("Agent Cash-Up")
            cash_up.agent = agent_id
            cash_up.amount = cash_amount
            cash_up.transaction_breakdown = json.dumps(transaction_details)
            cash_up.cash_up_date = datetime.now()
            cash_up.status = "Submitted"
            cash_up.insert(ignore_permissions=True)
            
            # Update agent balance
            current_balance = frappe.db.get_value("Banking Agent", agent_id, "current_balance")
            frappe.db.set_value(
                "Banking Agent",
                agent_id,
                "current_balance",
                current_balance - cash_amount
            )
            
            frappe.db.commit()
            return cash_up
            
        except Exception as e:
            frappe.log_error(f"Cash-Up Processing Error: {str(e)}")
            return None
    
    @staticmethod
    def calculate_agent_commission(agent_id, period_start, period_end):
        """
        Calculate commission for agent
        
        Args:
            agent_id (str): Agent ID
            period_start (str): Commission period start
            period_end (str): Commission period end
        
        Returns:
            float: Commission amount
        """
        transactions = frappe.get_all(
            "Agent Transaction",
            filters={
                "agent": agent_id,
                "transaction_date": ["between", [period_start, period_end]],
                "docstatus": 1
            },
            fields=["transaction_type", "amount"]
        )
        
        total_commission = 0
        commission_rates = frappe.get_doc("Commission Rates")
        
        for txn in transactions:
            rate = commission_rates.get_rate(txn.transaction_type)
            total_commission += txn.amount * rate
        
        return total_commission


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_sacco_financial_summary():
    """
    Get comprehensive financial summary for SACCO
    
    Returns:
        dict: Complete financial overview
    """
    return {
        "total_assets": frappe.db.sql("""
            SELECT SUM(total_assets) FROM `tabSACCO Balance Sheet`
        """)[0][0] or 0,
        
        "total_deposits": frappe.db.sql("""
            SELECT SUM(current_balance) 
            FROM `tabSavings Account`
            WHERE status = 'Active' AND docstatus = 1
        """)[0][0] or 0,
        
        "total_loans_disbursed": frappe.db.sql("""
            SELECT SUM(amount_approved) 
            FROM `tabLoan Application`
            WHERE status = 'Disbursed' AND docstatus = 1
        """)[0][0] or 0,
        
        "total_share_capital": frappe.db.sql("""
            SELECT SUM(total_amount) 
            FROM `tabShare Allocation`
            WHERE status = 'Allocated' AND docstatus = 1
        """)[0][0] or 0,
        
        "members_count": frappe.db.count("SACCO Member", {"membership_status": "Active"}),
        
        "liquidity_ratio": SASRACompliance.calculate_liquidity_ratio(),
        
        "capital_adequacy_ratio": SASRACompliance.calculate_capital_adequacy_ratio(),
        
        "npl_ratio": SASRACompliance.calculate_npl_ratio()
    }
