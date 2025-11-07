# app/hsm.py
"""
HSM integration stubs. Replace these with real HSM library calls.
Important functions:
- encrypt_pin_block(pan, pin, key_id)
- calculate_mac(message_bytes, key_id)
- derive_session_key(terminal_id, ksn)
"""

import logging
logger = logging.getLogger(__name__)

async def encrypt_pin_block(pan: str, pin: str, key_id: str) -> str:
    """
    Return a hex string representing encrypted PIN block.
    Replace with HSM call; keep no plaintext PIN in logs.
    """
    logger.debug("HSM.encrypt_pin_block called (stub) for key %s", key_id)
    # stub: return masked hex (do NOT use in prod)
    masked = ("{:02x}".format(len(pin)) * 8)[:16]
    return masked

async def calculate_mac(payload: bytes, key_id: str) -> str:
    """
    Calculate MAC (e.g. 3DES MAC) over payload using HSM key.
    """
    logger.debug("HSM.calculate_mac (stub)")
    # stub: return 16 hex chars
    return "DEADBEEFDEADBEEF"

async def derive_session_key(terminal_id: str, ksn: str) -> str:
    logger.debug("HSM.derive_session_key (stub)")
    return "SESSIONKEY123456"
