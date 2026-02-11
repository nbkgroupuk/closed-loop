from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import text
from app.storage.db import AsyncSessionLocal

router = APIRouter(prefix="/api/iso20022", tags=["iso20022"])

@router.get("/{transaction_id}")
async def get_iso20022_xml(transaction_id: str):
    """
    Return the latest ISO20022 XML for a given transaction_id.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                """
                SELECT xml
                FROM iso20022_messages
                WHERE transaction_id = :tid
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"tid": transaction_id},
        )
        row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="ISO20022 XML not found")

    xml = row[0]
    return Response(content=xml, media_type="application/xml")
