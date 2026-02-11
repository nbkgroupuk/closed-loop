# backend/app/telemetry/business_metrics.py

from prometheus_client import Counter, Histogram

# -------------------------------
# ISO8583 metrics
# -------------------------------
iso8583_tx_total = Counter(
    "iso8583_transactions_total",
    "Total ISO8583 transactions",
    ["mti", "response_code"]
)

iso8583_latency = Histogram(
    "iso8583_latency_seconds",
    "ISO8583 processing latency",
    buckets=(0.05, 0.1, 0.2, 0.5, 1, 2, 5)
)

# -------------------------------
# Stripe metrics
# -------------------------------
stripe_requests_total = Counter(
    "stripe_requests_total",
    "Total Stripe API requests",
    ["operation", "status"]
)

stripe_amount_total = Counter(
    "stripe_amount_total_minor",
    "Total Stripe amount processed (minor units)",
    ["currency"]
)

# -------------------------------
# Crypto payout metrics
# -------------------------------
crypto_payouts_total = Counter(
    "crypto_payouts_total",
    "Total crypto payouts",
    ["asset", "network", "status"]
)
