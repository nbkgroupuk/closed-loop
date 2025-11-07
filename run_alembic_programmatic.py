import os, sys
from alembic.config import Config
from alembic import command

# DB URL used by your app (adjust to match your environment variable name)
DB_URL = os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI")
if not DB_URL:
    print("ERROR: set DATABASE_URL or SQLALCHEMY_DATABASE_URI env var", file=sys.stderr)
    sys.exit(2)

# try to find migrations script_location: look for env.py under /app or working dir
candidates = []
for root in ("/app", "/", "."):
    for dirpath, dirnames, filenames in os.walk(root):
        if "env.py" in filenames and "versions" in dirnames:
            candidates.append(dirpath)
# prefer /app/migrations, otherwise the first candidate
script_loc = candidates[0] if candidates else None
if not script_loc:
    print("Could not find alembic env.py/versions under /app or repo. Please provide ALEMBIC_SCRIPT_LOCATION.", file=sys.stderr)
    sys.exit(3)

print("Using migrations dir:", script_loc)

alembic_cfg = Config()
alembic_cfg.set_main_option("script_location", script_loc)
alembic_cfg.set_main_option("sqlalchemy.url", DB_URL)

# run upgrade
command.upgrade(alembic_cfg, "head")
print("Alembic upgrade head done")
