# Minimal HTTP wrapper for crypto_payout_engine.py
# Expects crypto_payout_engine.process_settlement_and_trigger to be importable.
import os, json
from flask import Flask, request, jsonify
app = Flask(__name__)

# Optional environment config
RPC_URL = os.environ.get("RPC_URL")          # e.g. https://mainnet.infura.io/v3/...
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")  # the account used to send payouts (keep secret)
DEFAULT_CHAIN = os.environ.get("CHAIN", "ethereum")

try:
    import crypto_payout_engine as engine
except Exception as e:
    engine = None
    load_err = str(e)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status":"ok", "engine_loaded": engine is not None}), 200

@app.route("/payout", methods=["POST"])
def payout():
    if engine is None:
        return jsonify({"error":"engine import failed", "detail": load_err}), 500

    payload = request.get_json() or {}
    # expected shape (example): {"wallet":"0xdead...","amount_minor":1000000, "currency":"USDT"}
    # merge with env config
    cfg = {"rpc_url": RPC_URL, "private_key": PRIVATE_KEY, "chain": DEFAULT_CHAIN}
    try:
        # call engine function — adapt if your engine has a different API
        result = engine.process_settlement_and_trigger(payload, cfg=cfg)
        return jsonify({"status":"ok","result": result}), 200
    except TypeError:
        # fallback if engine expects different args (we attempt earlier dry_run)
        try:
            res = engine.process_settlement_and_trigger(payload, dry_run=False)
            return jsonify({"status":"ok","result":res}), 200
        except Exception as e:
            return jsonify({"error":"engine execution failed","detail": str(e)}), 500
    except Exception as e:
        return jsonify({"error":"engine execution failed","detail": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("FLASK_RUN_PORT", "9001")))
