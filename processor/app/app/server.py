#processor/app/app/server.py

from .server_fixed import *
from app.app.metrics import iso_requests, iso_approved

iso_requests.labels(mti=mti).inc()
if de39 == "00":
    iso_approved.inc()
