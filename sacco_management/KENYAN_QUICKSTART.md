# 🚀 Quick Start: Kenyan SACCO Features

## 5-Minute Setup Guide

### Step 1: Enable M-Pesa Integration (2 minutes)

```bash
# 1. Get your Daraja credentials from https://developer.safaricom.co.ke/
# 2. Add to SACCO Settings
```

**In SACCO Settings Doctype, add:**
```json
{
  "mpesa_consumer_key": "YOUR_KEY",
  "mpesa_consumer_secret": "YOUR_SECRET",
  "mpesa_shortcode": "123456",
  "mpesa_passkey": "YOUR_PASSKEY",
  "mpesa_environment": "Sandbox"
}
```

**Test it:**
```python
from sacco_management.sacco.utils.kenya_utils import MPesaIntegration

mpesa = MPesaIntegration()
response = mpesa.stk_push("254712345678", 5000, "MEMBER-001")
print(response)
```

---

### Step 2: Setup CRB Integration (2 minutes)

```python
from sacco_management.sacco.utils.kenya_utils import CRBIntegration

crb = CRBIntegration(crb_provider="Metropol")

# Test credit check
result = crb.submit_loan_enquiry(
    member_id="MEMBER-001",
    national_id="12345678",
    loan_amount=100000
)

print(f"Credit Score: {result.get('credit_score')}")
```

---

### Step 3: Enable Compliance Monitoring (1 minute)

```python
# Add to hooks.py scheduler_events
scheduler_events = {
    "daily": [
        "sacco_management.sacco.utils.kenya_utils.daily_compliance_check"
    ]
}
```

**Check compliance now:**
```python
from sacco_management.sacco.utils.kenya_utils import SASRACompliance

print(f"Liquidity Ratio: {SASRACompliance.calculate_liquidity_ratio()}%")
print(f"Capital Adequacy: {SASRACompliance.calculate_capital_adequacy_ratio()}%")
```

---

## Common Use Cases

### 💰 Accept M-Pesa Payments

```python
# Member pays contribution via STK Push
from sacco_management.sacco.utils.kenya_utils import MPesaIntegration

mpesa = MPesaIntegration()

mpesa.stk_push(
    phone_number="254712345678",
    amount=5000,
    account_reference="MEMBER-001",
    transaction_type="Monthly Contribution"
)
```

### 📊 Check CRB Before Loan Approval

```python
# In Loan Application workflow
from sacco_management.sacco.utils.kenya_utils import CRBIntegration

crb = CRBIntegration()

report = crb.submit_loan_enquiry(
    member_id=loan.member,
    national_id=member.national_id,
    loan_amount=loan.amount_requested
)

if report['credit_score'] < 500:
    frappe.throw("Credit score too low for loan approval")
```

### 🏛️ Verify SASRA Compliance

```python
from sacco_management.sacco.utils.kenya_utils import SASRACompliance

# Check single borrower limit
compliance = SASRACompliance.check_single_borrower_limit(
    member_id="MEMBER-001",
    new_loan_amount=500000
)

if not compliance['compliant']:
    frappe.throw(f"""
        Loan exceeds single borrower limit!
        Limit: KES {compliance['single_borrower_limit']:,.2f}
        Total Exposure: KES {compliance['total_exposure']:,.2f}
    """)
```

### 📜 Pledge Shares as Collateral

```python
from sacco_management.sacco.utils.kenya_utils import create_share_pledge

pledge = create_share_pledge(
    member_id="MEMBER-001",
    loan_id="LOAN-2024-001",
    pledged_shares=1000
)

print(f"Pledged {pledge.number_of_shares} shares worth KES {pledge.total_value}")
```

---

## Troubleshooting

### M-Pesa Not Working?

```bash
# Check Redis is running
redis-cli ping  # Should return PONG

# Test Daraja API
curl -X GET "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials" \
  -u "CONSUMER_KEY:CONSUMER_SECRET"
```

### CRB Check Failing?

```python
# Verify API credentials
crb = CRBIntegration()
print(crb.api_config)  # Should show configured provider
```

### Compliance Alerts Triggering?

```python
# Get all ratios
from sacco_management.sacco.utils.kenya_utils import SASRACompliance

ratios = {
    "liquidity": SASRACompliance.calculate_liquidity_ratio(),
    "car": SASRACompliance.calculate_capital_adequacy_ratio(),
    "npl": SASRACompliance.calculate_npl_ratio()
}

print(ratios)
```

---

## Next Steps

1. ✅ **M-Pesa Live**: Switch `mpesa_environment` to "Production"
2. ✅ **CRB Contract**: Sign with Metropol or preferred CRB
3. ✅ **SMS Gateway**: Setup Africa's Talking account
4. ✅ **Agency Banking**: Recruit first agents
5. ✅ **SASRA Returns**: Generate first monthly report

---

## Full Documentation

- 📘 [Complete Guide](KENYAN_SACCO_ADVANCED_FEATURES.md)
- 📋 [Implementation Summary](KENYAN_SACCO_IMPLEMENTATION_SUMMARY.md)
- 🔧 [API Reference](sacco/utils/kenya_utils.py)

---

**Need Help?** Email: support@sacco.go.ke | Call: +254 20 123 4567
