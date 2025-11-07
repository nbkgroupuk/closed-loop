# processor/app/iso_processing.py
import uuid
import json
import logging
import inspect
import asyncio
from datetime import datetime
from sqlalchemy import text

log = logging.getLogger("app.iso_processing")
logging.basicConfig(level=logging.INFO)

# Try to import a session factory. This factory may be:
# - an async context manager factory (async SQLAlchemy)
# - a sync context manager factory (sync SQLAlchemy or sqlite wrapper)
# If no such factory exists, we'll try to use storage.db.get_conn() as fallback.
_get_session = None
try:
    from .db import get_session as _get_session  # expected async or sync factory
except Exception:
    try:
        from .storage.db import get_session as _get_session
    except Exception:
        try:
            # storage.db in this repo provides get_conn(); prefer that if present
            from .storage import db as storage_db  # storage_db.get_conn()
            _get_session = None
        except Exception:
            try:
                from app.storage import db as storage_db
                _get_session = None
            except Exception:
                storage_db = None
                _get_session = None


async def _run_sync_persist_with_conn_factory(conn_factory, insert_sql, params):
    """
    Run DB insert in a thread using a sync connection factory.
    conn_factory should be a callable returning a connection/context manager.
    """
    def _blocking():
        conn = conn_factory()
        try:
            # If it's a sqlite3.Connection (has cursor/execute)
            try:
                cur = conn.cursor()
                # If insert_sql is sqlalchemy.text, convert to string
                sql_text = str(insert_sql)
                # params is a dict; sqlite3 requires tuple in order - use named param style if present
                try:
                    # Try named params
                    cur.execute(sql_text, params)
                except Exception:
                    # Fallback: positional params
                    ordered = tuple(params[k] for k in params)
                    cur.execute(sql_text, ordered)
                conn.commit()
            except Exception:
                # Fallback for sync SQLAlchemy Session
                try:
                    conn.execute(insert_sql, params)
                    conn.commit()
                except Exception:
                    # If it supports a session-like interface with context manager
                    raise
        finally:
            try:
                conn.close()
            except Exception:
                pass

    await asyncio.to_thread(_blocking)


async def persist_event(topic: str, payload: dict) -> dict:
    """
    Persist an event into processor_events table.
    Accepts either async session factory or sync connection factory fallback.
    """
    event_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    try:
        payload_json = json.dumps(payload, default=str, ensure_ascii=False)
    except Exception:
        payload_json = json.dumps({"repr": str(payload)}, ensure_ascii=False)

    insert_sql = text(
        "INSERT INTO processor_events (id, topic, payload, created_at) VALUES (:id, :topic, :payload, :created_at)"
    )
    params = {"id": event_id, "topic": topic, "payload": payload_json, "created_at": created_at}

    try:
        # If a get_session factory was imported, call it
        if _get_session:
            sess_obj = _get_session()
            # If call returned awaitable, await it
            if inspect.isawaitable(sess_obj):
                sess_obj = await sess_obj

            # Async context manager (async SQLAlchemy)
            if hasattr(sess_obj, "__aenter__"):
                async with sess_obj as session:
                    await session.execute(insert_sql, params)
                    await session.commit()
            # Sync context manager factory returned
            elif hasattr(sess_obj, "__enter__"):
                # run blocking work in a thread
                def _blocking_with_session():
                    with sess_obj as session:
                        session.execute(insert_sql, params)
                        try:
                            session.commit()
                        except Exception:
                            pass
                await asyncio.to_thread(_blocking_with_session)
            else:
                raise RuntimeError("get_session() returned unsupported object: %r" % (sess_obj,))
        else:
            # No get_session available; try storage_db.get_conn() fallback
            if storage_db and hasattr(storage_db, "get_conn"):
                # use conn factory inside thread
                await _run_sync_persist_with_conn_factory(storage_db.get_conn, insert_sql, params)
            else:
                raise RuntimeError(
                    "No DB session factory available (checked .db, .storage.db, app.storage.db)"
                )

        log.info("Persisted event topic=%s id=%s", topic, event_id)
        return {"event_id": event_id, "created_at": created_at}
    except Exception as e:
        log.exception("Failed to persist event: %s", e)
        raise


async def process_incoming_iso(fields: dict) -> dict:
    """
    Handle both ISO8583 card messages and ISO20022 payout JSONs.

    Validation rules added for production:
      - For type == 'iso20022' require a trusted protocol pattern and a numeric auth_code (3-6 digits)
      - Require payoutDetails.iban
    Returns a dict with de39 and other metadata suitable for the listener/app.
    """
    topic = "clearing.incoming"
    try:
        # ISO20022 payout flow (production validation)
        if fields.get("type") == "iso20022":
            protocol = (fields.get("protocol") or "").strip()
            auth_code = (fields.get("auth_code") or fields.get("authCode") or "").strip()
            payout_details = fields.get("payoutDetails") or {}

            # basic validations (tune regex / rules to your production policy)
            import re
            protocol_ok = bool(re.match(r"^101\.\d+$", protocol))
            auth_ok = bool(re.match(r"^\d{3,6}$", auth_code))
            iban_ok = bool(payout_details.get("iban"))

            if not protocol_ok or not auth_ok or not iban_ok:
                # Log reasons for audit
                reasons = []
                if not protocol_ok:
                    reasons.append(f"invalid_protocol:{protocol!s}")
                if not auth_ok:
                    reasons.append(f"invalid_auth_code:{auth_code!s}")
                if not iban_ok:
                    reasons.append("missing_iban")
                log.warning("Rejected ISO20022 payout due validation failure: %s", reasons)

                # Optionally persist the rejected attempt for audit / troubleshooting
                try:
                    await persist_event("payout.incoming.rejected", {
                        "reason": ";".join(reasons),
                        "incoming": fields,
                    })
                except Exception:
                    # don't mask the validation response on persistence failure
                    log.exception("Failed to persist rejected payout event")

                return {
                    "approved": False,
                    "de39": "05",  # do not honor (validation/decline)
                    "error": "validation_failed:" + ",".join(reasons),
                    "de38": None,
                    "gateway_txn_id": None,
                    "txn_id": fields.get("txn_id") or None,
                    "correlation_id": fields.get("correlation_id"),
                }

            # passed validation -> create payout record/event
            payout = {
                "txn_id": fields.get("txn_id") or str(uuid.uuid4()),
                "correlation_id": fields.get("correlation_id"),
                "type": "iso20022",
                "creditor_name": fields.get("creditor_name"),
                "amount": fields.get("amount"),
                "currency": fields.get("currency"),
                "pain_xml": fields.get("pain_xml"),
                "protocol": protocol,
                "auth_code": auth_code,
                "payoutDetails": payout_details,
            }
            rv = await persist_event("payout.incoming", payout)

            resp = {
                "approved": True,
                "de39": "00",
                "gateway_txn_id": f"ISS-{uuid.uuid4()}",
                "txn_id": payout["txn_id"],
                "correlation_id": payout.get("correlation_id"),
                "payout_event_id": rv.get("event_id"),
                "payout_created_at": rv.get("created_at"),
            }
            log.info("Processed ISO20022 payout (validated): txn=%s event=%s", resp["txn_id"], rv.get("event_id"))
            return resp

        # Card auth / ISO8583 fallback (existing behavior)
        card = str(fields.get("2") or fields.get("cardNumber") or "")
        if card.startswith(("4", "5", "6")) and len(card) in (15, 16, 19):
            resp = {
                "approved": True,
                "de39": "00",
                "gateway_txn_id": f"ISS-{uuid.uuid4()}",
                "txn_id": fields.get("txn_id") or str(uuid.uuid4()),
                "correlation_id": fields.get("correlation_id"),
            }
            await persist_event(topic, {**fields, **{"response": resp}})
            log.info("Approved card transaction: %s", resp["txn_id"])
            return resp

        # default: unknown -> reject
        result = {
            "approved": False,
            "de39": "96",
            "error": None,
            "de38": None,
            "gateway_txn_id": None,
            "txn_id": fields.get("txn_id"),
            "correlation_id": fields.get("correlation_id"),
        }
        await persist_event(topic, {**fields, **{"response": result}})
        log.warning("Unhandled ISO message, rejecting: %s", result)
        return result

    except Exception as e:
        log.exception("Unexpected error in process_incoming_iso: %s", e)
        try:
            fn = globals().get("debug_iso_decision")
            if callable(fn):
                try:
                    fn({"fields": fields, "error_reason": str(e)})
                except Exception:
                    pass
        except Exception:
            pass

        return {
            "approved": False,
            "de39": "96",
            "error": str(e),
            "de38": None,
            "gateway_txn_id": None,
            "txn_id": fields.get("txn_id"),
            "correlation_id": fields.get("correlation_id"),
        }

