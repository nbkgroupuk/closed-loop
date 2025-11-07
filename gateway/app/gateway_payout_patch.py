from fastapi import APIRouter, Request
import httpx, logging, json

LOG = logging.getLogger("gateway.payout.proxy")
router = APIRouter()

@router.post("/payouts/payout")
async def proxy_payout(request: Request):
    """Forward payout request to processor"""
    payload = await request.json()
    LOG.info("proxy_payout called payload=%s", json.dumps(payload))
    async with httpx.AsyncClient() as client:
        r = await client.post("http://project-processor-1:8000/payout", json=payload)
    LOG.info("proxy_payout -> processor status=%s body=%s", r.status_code, r.text)
    try:
        return r.json()
    except Exception:
        return {"detail": "processor error", "status_code": r.status_code, "raw": r.text}

@router.get("/payout/{job_id}")
async def proxy_payout_status(job_id: str):
    """Fetch payout status from processor"""
    LOG.info("proxy_payout_status called job_id=%s", job_id)
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"http://project-processor-1:8000/payout/{job_id}", timeout=10.0)
        except Exception as e:
            LOG.exception("error calling processor for payout status")
            raise
    LOG.info("proxy_payout_status -> processor status=%s body=%s", r.status_code, r.text)
    try:
        return r.json()
    except Exception:
        return {"detail": "processor error", "status_code": r.status_code, "raw": r.text}
