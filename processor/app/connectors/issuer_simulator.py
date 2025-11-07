# processor/app/connectors/issuer_simulator.py
import asyncio
import logging
from uuid import uuid4

logger = logging.getLogger("app.issuer_simulator")
logger.setLevel(logging.INFO)

async def authorize(payload: dict) -> dict:
    """
    Very small simulator: approve when authCode exists and does NOT end with '0'.
    """
    try:
        auth = None
        if payload is None:
            payload = {}
        # support both lowercase or camelCase keys
        for k in ("authCode", "auth_code", "auth"):
            if k in payload:
                auth = payload.get(k)
                break

        if auth is None:
            return {"approved": False, "de39": "96", "gateway_txn_id": f"ISS-{uuid4()}"}

        await asyncio.sleep(0.05)

        if str(auth).endswith("0"):
            return {"approved": False, "de39": "05", "gateway_txn_id": f"ISS-{uuid4()}"}
        else:
            return {"approved": True, "de39": "00", "gateway_txn_id": f"ISS-{uuid4()}"}
    except Exception:
        logger.exception("issuer_simulator.authorize raised")
        return {"approved": False, "de39": "96", "gateway_txn_id": f"ISS-{uuid4()}"}
