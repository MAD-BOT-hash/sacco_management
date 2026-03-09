# Automated Fix Script - Quick Guide

## 🚀 Usage

### Option 1: Direct Python Execution

```bash
cd apps/sacco_management
python fix_sacco_management.py
```

### Option 2: Bench Execute (Recommended)

```bash
bench --site sitename execute sacco_management.fix_sacco_management.run_all_fixes
```

### Option 3: With Site Parameter

```bash
python fix_sacco_management.py erpmain
```

---

## ✨ What It Fixes

### 1. DocType Controllers (Auto-Creation)

**Scans all doctype folders and:**
- Creates missing Python controller files
- Fixes incorrect class names
- Updates `__init__.py` imports
- Follows Frappe naming conventions

**Example Output:**
```
✅ Created: loan_approval_history.py
🔧 Fixed: sacco_member.py
✅ Created: fine_payment_allocation.py
```

---

### 2. Utility Functions (Auto-Repair)

**Adds missing functions to `sacco/utils/loan_utils.py`:**

- `calculate_loan_summary()` - Loan statistics
- `get_loan_outstanding()` - Outstanding balance
- `process_loan_repayment()` - Repayment processing

**Example Output:**
```
✅ Added: calculate_loan_summary()
✅ Added: get_loan_outstanding()
```

---

### 3. Dashboard Charts (Safe Insertion)

**Creates 5 dashboard charts:**

1. System Performance Metrics
2. Member Growth
3. Loan Disbursement Trend
4. Savings Growth
5. Share Capital Growth

**Features:**
- Checks for duplicates before inserting
- Avoids `KeyError: 'name'` issue
- Auto-commits after each chart
- Logs errors for debugging

**Example Output:**
```
✅ Inserted: System Performance Metrics
⏭️  Exists: Member Growth
✅ Inserted: Loan Disbursement Trend
```

---

## 📊 Complete Output Example

```
============================================================
SACCO MANAGEMENT AUTO-FIX SCRIPT
============================================================

[1/3] Fixing DocType controllers...
✅ Created: loan_approval_history.py
🔧 Fixed: sacco_journal_entry.py
✅ Created: mobile_money_transaction.py

============================================================
Controllers Created: 3
Controllers Fixed: 5
Errors: 0
============================================================

[2/3] Ensuring utility functions...
✅ Added: calculate_loan_summary()
✅ Added: get_loan_outstanding()

============================================================
Functions Added: 2
============================================================

[3/3] Inserting dashboard charts...
✅ Connected to site: erpmain
✅ Inserted: System Performance Metrics
✅ Inserted: Member Growth
✅ Inserted: Loan Disbursement Trend
✅ Inserted: Savings Growth
✅ Inserted: Share Capital Growth

============================================================
Charts Inserted: 5
Charts Skipped: 0
Errors: 0
============================================================

============================================================
FIX SUMMARY
============================================================
✅ Controllers Created: 3
🔧 Controllers Fixed: 5
➕ Functions Added: 2
📊 Charts Inserted: 5
⏭️  Charts Skipped: 0
❌ Total Errors: 0
============================================================

📋 NEXT STEPS:
1. bench --site sitename clear-cache
2. bench restart
3. bench --site sitename migrate
```

---

## 🔧 Troubleshooting

### Issue: No site specified

**Error:**
```
⚠️  No site specified. Run with: bench --site sitename execute ...
```

**Solution:**
```bash
bench --site your-site execute sacco_management.fix_sacco_management.run_all_fixes
```

---

### Issue: App path not found

**Error:**
```
❌ App path not found: /path/to/apps/sacco_management
```

**Solution:**
- Ensure you're running from bench root
- Check that app is installed
- Verify path: `ls apps/sacco_management`

---

### Issue: Permission denied

**Error:**
```
PermissionError: [Errno 13] Permission denied
```

**Solution:**
```bash
# Make script executable
chmod +x fix_sacco_management.py

# Or run with sudo (if necessary)
sudo python fix_sacco_management.py
```

---

## 🛡️ Safety Features

### Idempotent Operation
- ✅ Safe to run multiple times
- ✅ Checks existence before creating
- ✅ Skips already-fixed items

### Error Handling
- ✅ Try/except on all operations
- ✅ Continues on non-critical errors
- ✅ Logs all errors to error log

### Database Safety
- ✅ Commits after each successful operation
- ✅ Rolls back on critical errors
- ✅ Closes connections properly

---

## 📝 Customization

### Add More Charts

Edit the `DASHBOARD_CHARTS` list in the script:

```python
DASHBOARD_CHARTS = [
    {
        "chart_name": "Your New Chart",
        "chart_type": "Standard",
        "doctype": "Dashboard Chart",
        # ... more fields
    }
]
```

### Add More Functions

Edit the `required_functions` dict:

```python
required_functions = {
    "your_function_name": "def your_function():\n    pass\n",
    # ... more functions
}
```

---

## 🎯 Best Practices

### Before Running
1. ✅ Backup your database
2. ✅ Stop bench services
3. ✅ Take a git snapshot

### After Running
1. ✅ Clear cache
2. ✅ Restart bench
3. ✅ Run migrate
4. ✅ Test in browser

---

## 📈 Success Metrics

**Successful run shows:**
```
✅ Controllers Created: >0 or 🔧 Controllers Fixed: >0
➕ Functions Added: >=0
📊 Charts Inserted: 5
❌ Total Errors: 0
```

**If errors occur:**
- Check error logs: `bench --site sitename show-errors`
- Review file permissions
- Verify app installation

---

## 🔄 When to Run

Run this script when:
- ✅ Fresh installation of sacco_management
- ✅ Migration errors occur
- ✅ Missing DocType errors appear
- ✅ Dashboard charts not showing
- ✅ Import errors in console

---

## 📞 Support

If issues persist:

1. **Check logs:**
   ```bash
   bench --site sitename show-errors
   ```

2. **Verify installation:**
   ```bash
   bench list-apps
   ```

3. **Re-run migration:**
   ```bash
   bench --site sitename migrate
   ```

---

## ✅ Summary

| Feature | Status |
|---------|--------|
| Auto-fix controllers | ✅ |
| Repair utilities | ✅ |
| Insert charts safely | ✅ |
| Error handling | ✅ |
| Idempotent | ✅ |
| Production ready | ✅ |

---

**Run once to fix all common issues automatically!** 🎉
