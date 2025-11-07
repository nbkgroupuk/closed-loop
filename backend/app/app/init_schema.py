from sqlalchemy import create_engine
from app import models
import os

# Convert async URL to sync (needed for create_engine)
url = os.getenv("DATABASE_URL").replace("+asyncpg", "")
print("Connecting to", url)
engine = create_engine(url)

print("Creating tables...")
models.Base.metadata.create_all(bind=engine)
print("Done.")
