# Performance Optimization - Quick Reference Card

## 🚀 Quick Start (5 Minutes)

### 1. Apply Indexes
```bash
bench execute sacco_management.sacco.patches.add_performance_indexes
```

### 2. Enable Caching (Already configured in hooks.py)
- Daily cache warming: ✅ Configured
- Weekly cleanup: ✅ Configured
- GZip compression: ✅ Enabled

---

## 📦 Use Cached Functions

```python
from sacco_management.sacco.utils.optimized_utils import (
    get_member_profile_cached,
    get_loan_portfolio_stats,
    get_total_savings_by_type,
    get_share_capital_summary_cached,
    get_optimized_dashboard_data
)

# Example
member_data = get_member_profile_cached("MEMBER-001")
loan_stats = get_loan_portfolio_stats()
```

---

## ⚡ Query Optimization Cheat Sheet

### DO ✅
```python
# Specific fields only
frappe.get_all("SACCO Member", fields=["name", "email"])

# Use indexed columns in filters
frappe.get_all("Loan Application", filters={"member": member_id})

# Add pagination
frappe.get_all(..., limit_start=0, limit_page_length=20)

# Batch processing for large datasets
process_in_batches("SACCO Member", batch_size=100, processor_func=your_func)

# JOIN instead of N+1 queries
frappe.db.sql("""
    SELECT la.*, m.member_name 
    FROM `tabLoan Application` la
    INNER JOIN `tabSACCO Member` m ON la.member = m.name
""")
```

### DON'T ❌
```python
# SELECT *
frappe.get_all("SACCO Member")  # Bad

# Leading wildcard in LIKE
filters={"member_name": ["like", "%John%"]}  # Bad

# Queries in loops
for loan in loans:
    member = frappe.get_doc("SACCO Member", loan.member)  # Bad

# No pagination on large lists
frappe.get_all("SACCO Member")  # Bad
```

---

## 🔧 Common Patterns

### Cache Your Function
```python
from sacco_management.sacco.utils.performance import cache_result

@cache_result(ttl_seconds=300)
def your_expensive_function():
    # Your code here
    return result
```

### Monitor Performance
```python
from sacco_management.sacco.utils.performance import PerformanceMonitor

with PerformanceMonitor("Your Operation", threshold_ms=100):
    # Your code here
    pass
```

### Invalidate Member Cache
```python
from sacco_management.sacco.utils.performance import invalidate_member_cache

invalidate_member_cache("MEMBER-001")
```

---

## 📊 Performance Targets

| Operation | Target | Current Benchmark |
|-----------|--------|-------------------|
| Member Creation | < 500ms | ✅ |
| Loan Calculation | < 50ms | ✅ |
| API Response | < 500ms | ✅ |
| Database Query | < 200ms | ✅ |
| Search | < 100ms | ✅ |
| Dashboard | < 2s | ✅ |

---

## 🎯 Indexed Columns

### SACCO Member
- ✅ email
- ✅ membership_status
- ✅ branch
- ✅ joining_date

### Loan Application
- ✅ member
- ✅ status
- ✅ application_date
- ✅ loan_type
- ✅ disbursement_date

### Savings Account
- ✅ member
- ✅ status
- ✅ account_type

### Share Allocation
- ✅ member
- ✅ share_type
- ✅ allocation_date

---

## 🛠️ Troubleshooting

### Slow Query?
```sql
-- Run EXPLAIN to see if index is used
EXPLAIN SELECT ... FROM ... WHERE ...
```

### Cache Not Working?
```bash
# Check Redis
redis-cli ping  # Should return PONG

# Check cached keys
frappe.cache().get_keys("*")
```

### High Memory?
```python
# Clear caches
from sacco_management.sacco.utils.optimized_utils import clear_all_sacco_caches
clear_all_sacco_caches()
```

---

## 📚 Documentation

- **Full Guide**: [PERFORMANCE_OPTIMIZATION_GUIDE.md](PERFORMANCE_OPTIMIZATION_GUIDE.md)
- **Implementation**: [PERFORMANCE_IMPLEMENTATION_SUMMARY.md](PERFORMANCE_IMPLEMENTATION_SUMMARY.md)
- **Test Suite**: [tests/](tests/)

---

## 🔗 Quick Links

### Files
- `sacco/utils/performance.py` - Core utilities
- `sacco/utils/optimized_utils.py` - Cached functions
- `sacco/patches/add_performance_indexes.py` - Index migration

### Commands
```bash
# Run performance tests
python -m tests.run_tests --performance

# Apply indexes
bench execute sacco_management.sacco.patches.add_performance_indexes

# Warm up caches
bench execute sacco_management.sacco.utils.optimized_utils.scheduled_cache_warming
```

---

**Remember**: Profile first, optimize second, measure always! 📈
