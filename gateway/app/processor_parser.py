# gateway/app/processor_parser.py
# Lightweight best-effort parser for the simple hex/ASCII-style test messages we used.
# It decodes bytes, extracts MTI (first 4 ASCII chars) and looks for digit sequences
# that likely correspond to PAN, amount, STAN, processing code, terminal/merchant ids, etc.
#
# This parser is intentionally defensive / heuristic — your real ISO8583 parser will be more strict.

import re
from typing import Dict, Any

PRINTABLE_RE = re.compile(rb'[\x20-\x7E]+')  # printable ASCII runs
DIGITS_RE = re.compile(r'\d{6,20}')  # 6..20 digit runs (PAN, stan, etc)

def _to_printable(b: bytes) -> str:
    # Extract longest printable substring(s) joined by space
    parts = PRINTABLE_RE.findall(b)
    if not parts:
        return ""
    return b" ".join(parts).decode('utf-8', errors='replace')

def parse(hex_payload: bytes | str) -> Dict[str, Any]:
    """
    Accepts raw bytes, or a hex string (str). Returns dict with best-effort fields.
    """
    if isinstance(hex_payload, str):
        # assume hex string (maybe with newlines) -> bytes
        hex_payload = bytes.fromhex(hex_payload.strip())

    data = hex_payload
    out: Dict[str, Any] = {}

    # MTI heuristic: first 4 printable ASCII chars (e.g. '0100','0210')
    try:
        first4 = data[:4].decode('ascii', errors='ignore')
        if re.fullmatch(r'\d{4}', first4):
            out['mti'] = first4
        else:
            # fallback: try printable extraction
            printable = _to_printable(data[:8].ljust(8, b' '))
            out['mti'] = printable.strip()[:4]
    except Exception:
        out['mti'] = None

    # full printable dump
    printable = _to_printable(data)
    out['printable_dump'] = printable

    # find digit runs
    digits = DIGITS_RE.findall(printable)
    # heuristics:
    if digits:
        # choose probable PAN: first 13-19 digit long candidate
        pan = next((d for d in digits if 13 <= len(d) <= 19), None)
        if not pan and digits:
            pan = digits[0]
        out['pan'] = pan

        # choose STAN as 6-digit run (common)
        stan = next((d for d in digits if len(d) == 6), None)
        out['stan'] = stan

        # amount: look for 12-digit numeric typical '000000012300' or smaller numeric
        amt = next((d for d in digits if len(d) in (8,10,12) and d.endswith('00')), None)
        if not amt:
            # fallback: small numeric that looks like cents
            amt = next((d for d in digits if 1 <= len(d) <= 12 and int(d) > 0), None)
        out['amount_raw'] = amt
        if amt:
            try:
                # treat last 2 digits as cents if plausible
                val = int(amt)
                out['amount'] = val / 100.0
            except Exception:
                out['amount'] = None

        # processing code: 6-digit candidate
        proc = next((d for d in digits if len(d) == 6), None)
        out['processing_code'] = proc

    # try to extract small ASCII tokens (e.g. TERM, MERCH or auth_code)
    # search for word-like tokens
    words = re.findall(r'[A-Z0-9]{4,16}', printable)
    # remove numeric-only (we already have digits)
    words = [w for w in words if not w.isdigit()]
    out['tokens'] = words[:10]

    # Attempt to find an auth code: 4-6 alnum (common)
    auth = next((t for t in words if 4 <= len(t) <= 6), None)
    out['auth_code_guess'] = auth

    return out

# CLI helper
if __name__ == "__main__":
    import sys, argparse
    p = argparse.ArgumentParser()
    p.add_argument("hexfile", help="hex string or file containing hex (or raw bytes if --raw)")
    p.add_argument("--raw", action="store_true", help="treat input as raw bytes file instead of hex")
    args = p.parse_args()
    if args.raw:
        b = open(args.hexfile, "rb").read()
    else:
        txt = open(args.hexfile, "rb").read().decode('utf-8', errors='ignore').strip()
        # if file contains newlines and shell markers, sanitize
        txt = "".join(ch for ch in txt if ch in "0123456789abcdefABCDEF")
        b = bytes.fromhex(txt)
    import json
    print(json.dumps(parse(b), indent=2))
