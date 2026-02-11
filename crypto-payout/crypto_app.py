# crypto_app.py
from fastapi import FastAPI
from prometheus_client import Counter

app = FastAPI(title="Crypto Payout Service")

# ✅ CRYPTO BUSINESS METRICS
crypto_payouts_total = Counter(
    "crypto_payouts_total",
    "Crypto payouts",
    ["asset", "network", "status"]
)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "crypto-payout"}

@app.post("/crypto/send")
async def send_crypto():
    try:
        # 🔒 real payout logic here
        crypto_payouts_total.labels(
            asset="USDT",
            network="ERC20",
            status="success"
        ).inc()

        return {"status": "sent"}

    except Exception:
        crypto_payouts_total.labels(
            asset="USDT",
            network="ERC20",
            status="failed"
        ).inc()
        raise
