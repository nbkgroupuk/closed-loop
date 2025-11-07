from pathlib import Path

p = Path("processor/app/server.py")
text = p.read_text().splitlines()
out = []
in_func = False

for line in text:
    out.append(line)
    if "def _start_iso_server_safe" in line:
        in_func = True
    elif in_func and "loop.create_task" in line:
        # Insert proper import inside try: block
        out.insert(len(out)-1, "        from app.iso_listener import start_server as start_iso_server  # ensure import inside loop")
        in_func = False

p.write_text("\n".join(out))
print("✅ Patched _start_iso_server_safe(): ensured local import of start_iso_server inside thread event loop.")
