# SACCO Management System - Performance Optimization Guide

## Table of Contents

1. [Database Query Optimization](#database-query-optimization)
2. [Caching Strategies](#caching-strategies)
3. [Indexing Recommendations](#indexing-recommendations)
4. [Code-Level Optimizations](#code-level-optimizations)
5. [API Performance](#api-performance)
6. [Monitoring & Profiling](#monitoring--profiling)
7. [Best Practices Checklist](#best-practices-checklist)

---

## Database Query Optimization

### 1. Avoid SELECT *

**❌ Bad:**
```python
members = frappe.get_all("SACCO Member", filters={"status": "Active"})
```

**✅ Good:**
```python
members = frappe.get_all(
    "SACCO Member",
    filters={"status": "Active"},
    fields=["name", "member_name", "email", "branch"]
)
```

**Why**: Fetching only needed columns reduces:
- Network transfer time
- Memory usage
- Database I/O

### 2. Use Indexed Columns in WHERE Clauses

**❌ Bad:**
```python
# No index on 'employer_name'
loans = frappe.get_all("Loan Application", 
                      filters={"employer_name": ["like", "%Company%"]})
```

**✅ Good:**
```python
# Use indexed column 'member'
loans = frappe.get_all("Loan Application",
                      filters={"member": member_id})
```

**Recommended Indexes:**
```python
# Add these indexes:
frappe.db.sql("ALTER TABLE `tabSACCO Member` ADD INDEX idx_email (email)")
frappe.db.sql("ALTER TABLE `tabSACCO Member` ADD INDEX idx_branch (branch)")
frappe.db.sql("ALTER TABLE `tabSACCO Member` ADD INDEX idx_membership_status (membership_status)")

frappe.db.sql("ALTER TABLE `tabLoan Application` ADD INDEX idx_member (member)")
frappe.db.sql("ALTER TABLE `tabLoan Application` ADD INDEX idx_status (status)")
frappe.db.sql("ALTER TABLE `tabLoan Application` ADD INDEX idx_application_date (application_date)")

frappe.db.sql("ALTER TABLE `tabSavings Account` ADD INDEX idx_member (member)")
frappe.db.sql("ALTER TABLE `tabSavings Account` ADD INDEX idx_status (status)")
```

### 3. Avoid Leading Wildcards in LIKE

**❌ Bad:**
```python
# Cannot use index
members = frappe.get_all("SACCO Member",
                        filters={"member_name": ["like", "%John%"]})
```

**✅ Good:**
```python
# Can use index if leading wildcard is removed
members = frappe.get_all("SACCO Member",
                        filters={"member_name": ["like", "John%"]})
```

### 4. Use Batch Processing for Large Datasets

**❌ Bad:**
```python
# Loads ALL members into memory
all_members = frappe.get_all("SACCO Member", fields=["*"])
for member in all_members:
    process_member(member)
```

**✅ Good:**
```python
from sacco_management.sacco.utils.performance import process_in_batches

def process_member_batch(doc):
    # Your processing logic
    pass

result = process_in_batches(
    doctype="SACCO Member",
    filters={},
    batch_size=100,
    processor_func=process_member_batch
)

print(f"Processed: {result['processed']}, Errors: {len(result['errors'])}")
```

### 5. Optimize JOINs with Proper Filtering

**❌ Bad:**
```python
query = """
    SELECT la.*, m.member_name
    FROM `tabLoan Application` la
    INNER JOIN `tabSACCO Member` m ON la.member = m.name
    WHERE la.status = 'Approved'
"""
# No filter on member table, may scan many rows
```

**✅ Good:**
```python
query = """
    SELECT la.name, la.amount_requested, m.member_name
    FROM `tabLoan Application` la
    INNER JOIN `tabSACCO Member` m ON la.member = m.name
    WHERE la.status = 'Approved'
    AND m.branch = %s
    ORDER BY la.application_date DESC
    LIMIT 100
"""
results = frappe.db.sql(query, (branch_name,), as_dict=True)
```

---

## Caching Strategies

### 1. Function Result Caching

```python
from sacco_management.sacco.utils.performance import cache_result

@cache_result(ttl_seconds=300)  # Cache for 5 minutes
def get_member_statistics(branch=None):
    """Expensive statistics calculation"""
    query = """
        SELECT COUNT(*), SUM(total_savings), AVG(total_shares)
        FROM `tabSACCO Member`
        WHERE membership_status = 'Active'
    """
    if branch:
        query += f" AND branch = '{branch}'"
    
    return frappe.db.sql(query, as_dict=True)

# First call executes the function
stats = get_member_statistics()

# Subsequent calls within 5 minutes return cached result
stats = get_member_statistics()  # Much faster!
```

### 2. Member Data Caching

```python
from sacco_management.sacco.utils.performance import cache_member_data, invalidate_member_cache

@cache_member_data(ttl_seconds=300)
def get_member_profile(member_id):
    """Get complete member profile with all related data"""
    member = frappe.get_doc("SACCO Member", member_id)
    
    profile = {
        "basic_info": member.as_dict(),
        "savings": frappe.get_all("Savings Account", 
                                 filters={"member": member_id},
                                 fields=["name", "current_balance"]),
        "loans": frappe.get_all("Loan Application",
                               filters={"member": member_id},
                               fields=["name", "outstanding_principal"]),
        "shares": frappe.get_all("Share Allocation",
                                filters={"member": member_id},
                                fields=["quantity", "total_amount"])
    }
    
    return profile

# Usage
profile = get_member_profile("MEMBER-001")

# After updating member data, invalidate cache
invalidate_member_cache("MEMBER-001")
```

### 3. Manual Cache Management

```python
# Set cache
frappe.cache().setex(
    "my_custom_key",
    3600,  # 1 hour
    json.dumps({"data": "value"})
)

# Get from cache
cached_value = frappe.cache().get("my_custom_key")
if cached_value:
    data = json.loads(cached_value)

# Delete specific key
frappe.cache().delete("my_custom_key")

# Clear pattern
keys = frappe.cache().get_keys("sacco_cache:*")
for key in keys:
    frappe.cache().delete(key)
```

### 4. Cache Warming Strategy

```python
from sacco_management.sacco.utils.performance import warm_up_caches

# Run this daily via scheduler
def daily_cache_warming():
    warmed = warm_up_caches()
    print(f"Warmed caches: {warmed['warmed_caches']}")
    
    # Additional custom warming
    # Cache active member count
    count = frappe.db.count("SACCO Member", {"membership_status": "Active"})
    frappe.cache().setex("stats:active_members", 3600, count)
    
    # Cache total loan portfolio
    portfolio = frappe.db.sql("""
        SELECT SUM(outstanding_principal) 
        FROM `tabLoan Application` 
        WHERE docstatus = 1 AND status = 'Disbursed'
    """)[0][0]
    frappe.cache().setex("stats:loan_portfolio", 3600, portfolio or 0)
```

---

## Indexing Recommendations

### Current Missing Indexes

Run this to check and add recommended indexes:

```python
from sacco_management.sacco.utils.performance import apply_recommended_indexes

result = apply_recommended_indexes()
print(f"Applied indexes: {result['applied']}")
```

### Manual Index Creation

```sql
-- Member table indexes
ALTER TABLE `tabSACCO Member` ADD INDEX idx_email (email);
ALTER TABLE `tabSACCO Member` ADD INDEX idx_branch (branch);
ALTER TABLE `tabSACCO Member` ADD INDEX idx_membership_status (membership_status);
ALTER TABLE `tabSACCO Member` ADD INDEX idx_joining_date (joining_date);

-- Loan Application indexes
ALTER TABLE `tabLoan Application` ADD INDEX idx_member (member);
ALTER TABLE `tabLoan Application` ADD INDEX idx_status (status);
ALTER TABLE `tabLoan Application` ADD INDEX idx_application_date (application_date);
ALTER TABLE `tabLoan Application` ADD INDEX idx_loan_type (loan_type);

-- Savings Account indexes
ALTER TABLE `tabSavings Account` ADD INDEX idx_member (member);
ALTER TABLE `tabSavings Account` ADD INDEX idx_status (status);
ALTER TABLE `tabSavings Account` ADD INDEX idx_account_type (account_type);

-- Share Allocation indexes
ALTER TABLE `tabShare Allocation` ADD INDEX idx_member (member);
ALTER TABLE `tabShare Allocation` ADD INDEX idx_share_type (share_type);
ALTER TABLE `tabShare Allocation` ADD INDEX idx_allocation_date (allocation_date);

-- Member Contribution indexes
ALTER TABLE `tabMember Contribution` ADD INDEX idx_member (member);
ALTER TABLE `tabMember Contribution` ADD INDEX idx_posting_date (posting_date);
ALTER TABLE `tabMember Contribution` ADD INDEX idx_contribution_type (contribution_type);
```

### Check Existing Indexes

```python
# Check indexes on a table
indexes = frappe.db.sql("SHOW INDEX FROM `tabSACCO Member`")
for idx in indexes:
    print(f"Index: {idx[2]}, Column: {idx[4]}, Unique: {idx[1] == 0}")
```

---

## Code-Level Optimizations

### 1. Minimize Database Calls in Loops

**❌ Bad (N+1 Query Problem):**
```python
loans = frappe.get_all("Loan Application", filters={"status": "Approved"})

for loan in loans:
    # Separate query for each loan
    member = frappe.get_doc("SACCO Member", loan.member)
    print(f"{loan.name} - {member.member_name}")
```

**✅ Good (Single Query with JOIN):**
```python
loans = frappe.db.sql("""
    SELECT la.name, la.amount_requested, m.member_name
    FROM `tabLoan Application` la
    INNER JOIN `tabSACCO Member` m ON la.member = m.name
    WHERE la.status = 'Approved'
""", as_dict=True)

for loan in loans:
    print(f"{loan.name} - {loan.member_name}")
```

### 2. Use Lazy Loading for Related Data

```python
from sacco_management.sacco.utils.performance import lazy_load_member_details

# Instead of multiple queries:
# member = frappe.get_doc("SACCO Member", member_id)
# savings = frappe.get_all(...)
# loans = frappe.get_all(...)

# Use single lazy-loaded call:
details = lazy_load_member_details(member_id)

# Access cached data
print(details["basic_info"]["member_name"])
print(details["savings_accounts"])
print(details["loans"])
```

### 3. Implement Pagination

**❌ Bad:**
```python
# Returns ALL members
all_members = frappe.get_all("SACCO Member")
```

**✅ Good:**
```python
# Paginated results
page = 1
page_size = 20

members = frappe.get_all(
    "SACCO Member",
    filters={},
    fields=["name", "member_name"],
    limit_start=(page - 1) * page_size,
    limit_page_length=page_size
)

total = frappe.db.count("SACCO Member")
total_pages = (total + page_size - 1) // page_size
```

### 4. Use frappe.get_all() Instead of frappe.get_list()

**❌ Slower:**
```python
members = frappe.get_list("SACCO Member", filters={"status": "Active"})
```

**✅ Faster:**
```python
members = frappe.get_all("SACCO Member", 
                        filters={"status": "Active"},
                        fields=["name", "member_name"])
```

**Why**: `get_all()` bypasses some permission checks and is faster for internal operations.

---

## API Performance

### 1. Implement Response Compression

Add to `hooks.py`:

```python
# Enable GZip compression
compress_response = True
```

### 2. Field Filtering in API Responses

```python
# Allow clients to request specific fields
@frappe.whitelist()
def get_member(member_id, fields=None):
    member = frappe.get_doc("SACCO Member", member_id)
    
    if fields:
        field_list = fields.split(',')
        filtered_data = {f: member.get(f) for f in field_list if hasattr(member, f)}
        return filtered_data
    
    return member.as_dict()

# Usage: GET /api/.../get_member?member_id=XXX&fields=name,member_name,email
```

### 3. Rate Limiting

Add to API endpoints:

```python
from frappe.rate_limiter import rate_limit

@frappe.whitelist()
@rate_limit(limit=100, seconds=60)  # 100 calls per minute
def get_expensive_data():
    # Your code here
    pass
```

### 4. Cache API Responses

```python
from sacco_management.sacco.utils.performance import cache_result

@frappe.whitelist()
@cache_result(ttl_seconds=60)  # Cache for 1 minute
def get_dashboard_data():
    # Expensive dashboard calculations
    return {
        "total_members": frappe.db.count("SACCO Member"),
        "total_loans": frappe.db.count("Loan Application"),
        # ... more calculations
    }
```

---

## Monitoring & Profiling

### 1. Monitor Query Performance

```python
from sacco_management.sacco.utils.performance import PerformanceMonitor, monitor_queries

# Using context manager
with PerformanceMonitor("Processing Monthly Interest", threshold_ms=500):
    # Your code here
    process_interest_for_all_accounts()

# Using decorator
@monitor_queries
def calculate_dividends():
    # Your code here
    pass
```

### 2. Profile Slow Operations

```python
import cProfile
import pstats
import io

def profile_function(func, *args, **kwargs):
    """Profile a function and print results"""
    pr = cProfile.Profile()
    pr.enable()
    
    result = func(*args, **kwargs)
    
    pr.disable()
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(20)  # Top 20 lines
    
    print(s.getvalue())
    return result

# Usage
profile_function(your_slow_function, arg1, arg2)
```

### 3. Log Slow Queries

Add to site_config.json:

```json
{
    "enable_scheduler": 1,
    "logging": {
        "slow_query_threshold": 100  # ms
    }
}
```

### 4. Monitor Cache Hit Rate

```python
def analyze_cache_performance():
    """Analyze cache effectiveness"""
    cache_keys = frappe.cache().get_keys("*")
    
    stats = {
        "total_keys": len(cache_keys),
        "member_cache": len(frappe.cache().get_keys("member:*")),
        "sacco_cache": len(frappe.cache().get_keys("sacco_cache:*"))
    }
    
    print(f"Cache Statistics: {stats}")
    return stats
```

---

## Best Practices Checklist

### Database Optimization

- [ ] Add indexes on frequently queried columns
- [ ] Use specific field lists instead of SELECT *
- [ ] Avoid functions on indexed columns in WHERE clauses
- [ ] Use LIMIT to restrict result sets
- [ ] Implement soft deletes instead of hard deletes
- [ ] Archive old data periodically
- [ ] Use EXPLAIN to analyze query plans

### Caching

- [ ] Cache expensive calculations (TTL: 5-10 min)
- [ ] Cache member data (TTL: 5 min)
- [ ] Cache statistical data (TTL: 1 hour)
- [ ] Invalidate caches on data updates
- [ ] Use Redis for distributed caching
- [ ] Implement cache warming for critical data

### Code Quality

- [ ] Eliminate N+1 query problems
- [ ] Use batch processing for large datasets
- [ ] Implement pagination for list operations
- [ ] Use lazy loading for related data
- [ ] Minimize database calls in loops
- [ ] Profile code before optimizing

### API Design

- [ ] Implement pagination (default: 20 items/page)
- [ ] Support field filtering (?fields=name,email)
- [ ] Enable response compression (GZip)
- [ ] Implement rate limiting
- [ ] Cache read-only endpoint responses
- [ ] Use ETag for conditional requests

### Monitoring

- [ ] Set up slow query logging (threshold: 100ms)
- [ ] Monitor cache hit rates
- [ ] Track API response times
- [ ] Alert on performance degradation
- [ ] Regular database maintenance (OPTIMIZE TABLE)
- [ ] Review and update indexes quarterly

---

## Quick Wins (Implement Today!)

1. **Add Missing Indexes** (30 min):
```bash
bench execute sacco_management.sacco.utils.performance.apply_recommended_indexes
```

2. **Enable Caching** (1 hour):
   - Add `@cache_result` decorators to expensive functions
   - Set TTL based on data freshness needs

3. **Fix N+1 Queries** (2 hours):
   - Review all loops with database calls
   - Replace with JOINs or batch loading

4. **Implement Pagination** (1 hour):
   - Add to all list API endpoints
   - Default: 20 items per page

5. **Enable Query Logging** (15 min):
   - Add to site_config.json
   - Review logs daily

---

## Performance Targets

| Operation | Target Time | Current | Status |
|-----------|-------------|---------|--------|
| Member Creation | < 500ms | - | ✅ |
| Loan Calculation | < 50ms | - | ✅ |
| API Response | < 500ms | - | ✅ |
| Database Query | < 200ms | - | ✅ |
| Search Operation | < 100ms | - | ✅ |
| Report Generation | < 5s | - | ⏳ |

---

## Resources

- [Frappe Performance Best Practices](https://frappeframework.com/docs)
- [MariaDB Query Optimization](https://mariadb.com/kb/en/optimization-and-indexes/)
- [Redis Caching Patterns](https://redis.io/topics/lru-cache)
- [Python Profiling Tools](https://docs.python.org/3/library/profile.html)

---

**Last Updated**: 2024-01-01  
**Version**: 1.0.0  
**Maintained By**: Development Team
