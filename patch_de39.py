from pathlib import Path
p = Path("/app/app/server.py")
if not p.exists():
    print("❌ ERROR: /app/app/server.py not found"); raise SystemExit(2)

s = p.read_text()
changed = False

if "_extract_de39(" not in s:
    helper = """
def _extract_de39(result):
    try:
        if isinstance(result, dict):
            if result.get("de39") is not None:
                return str(result.get("de39"))
            f = result.get("fields") or {}
            if isinstance(f, dict) and (f.get("39") is not None):
                return str(f.get("39"))
    except Exception:
        pass
    return "96"

"""
    s = s.replace("\n\n", "\n\n" + helper, 1)
    changed = True

if '"de39":' not in s and '"processor_result": {' in s:
    s = s.replace(
        '"processor_result": {',
        '"de39": str(_extract_de39(result)),\n            "processor_result": {',
        1
    )
    changed = True

p.write_text(s)
print(f"✅ patched={changed} : /app/app/server.py updated")
