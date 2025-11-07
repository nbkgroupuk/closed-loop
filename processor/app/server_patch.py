from pathlib import Path

p = Path("processor/app/server.py")
s = p.read_text().splitlines()
out = []
in_func = False

for line in s:
    out.append(line)
    if "def _start_iso_server_safe" in line:
        in_func = True
    elif in_func and line.strip().startswith("try:"):
        # Inject the loop creation inside try:
        out.append("        import asyncio")
        out.append("        loop = asyncio.new_event_loop()")
        out.append("        asyncio.set_event_loop(loop)")
        out.append("        loop.create_task(start_iso_server(host='0.0.0.0', port=int(os.environ.get('ISO_PORT', '9000'))))")
        out.append("        loop.run_forever()")
        in_func = False

p.write_text("\n".join(out))
print("✅ Patched _start_iso_server_safe() with dedicated asyncio loop.")
