CASE_FACTS = {
    "customer_id":        "CUST-7823",
    "order_id":           "ORD-12345",   # needed to process the refund
    "item":               "Blue Wireless Headphones",
    "refund_amount":      149.99,         # exact — never summarize amounts
    "order_date":         "2026-05-03",
    "policy_window_days": 30,
    "days_since_order":   29,             # CRITICAL: day 29 of 30 — expiring soon
    "customer_request":   "full_refund",
    "verified":           True
}