"""Production-grade ISO20022 pain.001→pain.002 endpoint with XSD validation."""
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import PlainTextResponse
import xml.etree.ElementTree as ET, datetime, os, logging, sqlite3
from pathlib import Path
import xmlschema

log = logging.getLogger('gateway.iso20022')
router = APIRouter(prefix='/payouts', tags=['payouts'])

STRICT = os.getenv('ISO20022_STRICT','1')=='1'
VERBOSE = os.getenv('ISO20022_VERBOSE','0')=='1'
MAX_BYTES = int(os.getenv('ISO20022_MAX_BYTES','200000'))
API_KEY = os.getenv('ISO20022_API_KEY')
DATA_DIR = Path(os.getenv('ISO20022_DATA_DIR','/workspace/gateway/data'))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR/'iso20022.db'
XSD_PATH = Path('/workspace/gateway/xsd/pain.001.001.03.xsd')

# Cache schema
try:
    ISO_SCHEMA = xmlschema.XMLSchema(str(XSD_PATH))
    log.info('Loaded ISO20022 schema %s', XSD_PATH)
except Exception as e:
    ISO_SCHEMA = None
    log.warning('Schema load failed: %s', e)

def init_db():
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pain001_records(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        msgid TEXT UNIQUE,e2e TEXT,recv_ts TEXT,raw_xml TEXT,ack_xml TEXT,status TEXT)''')
    conn.commit(); conn.close()
init_db()

def ns_strip(tag): return tag.split('}',1)[-1] if tag and '}' in tag else tag
def findtext(root,name):
    for e in root.iter():
        if ns_strip(e.tag)==name: return e.text
    return None
def build_ack(msgid,ts):
    return f'''<?xml version=1.0 encoding=UTF-8?>
<Document xmlns=urn:iso:std:iso:20022:tech:xsd:pain.002.001.09>
  <CstmrPmtStsRpt>
    <GrpHdr><MsgId>{msgid}</MsgId><CreDtTm>{ts}</CreDtTm></GrpHdr>
    <OrgnlGrpInfAndSts><OrgnlMsgId>{msgid}</OrgnlMsgId><GrpSts>ACCP</GrpSts></OrgnlGrpInfAndSts>
  </CstmrPmtStsRpt>
</Document>'''

@router.post('/iso20022',response_class=PlainTextResponse)
async def accept_iso(request:Request):
    if 'xml' not in request.headers.get('content-type','').lower():
        raise HTTPException(415,'Content-Type must be application/xml')
    if API_KEY:
        key=request.headers.get('x-api-key') or request.headers.get('authorization')
        if not key: raise HTTPException(401,'Missing API key')
        if key.startswith('Bearer '): key=key.split(None,1)[1]
        if key!=API_KEY: raise HTTPException(403,'Invalid API key')
    body=await request.body()
    if not body: raise HTTPException(400,'empty body')
    if len(body)>MAX_BYTES: raise HTTPException(413,'payload too large')
    try:
        if STRICT and ISO_SCHEMA is not None:
            ISO_SCHEMA.validate(body)
        root=ET.fromstring(body)
    except xmlschema.validators.exceptions.XMLSchemaValidationError as e:
        raise HTTPException(400, f'XSD validation failed: {e.reason}')
    except ET.ParseError:
        raise HTTPException(400,'invalid xml')
    msgid=findtext(root,'MsgId') or f'MSG-{datetime.datetime.utcnow().isoformat()}'
    e2e=findtext(root,'EndToEndId') or 'UNKNOWN'
    now=datetime.datetime.utcnow().replace(microsecond=0).isoformat()
    if STRICT:
        if not any(ns_strip(e.tag)=='PmtInf' for e in root.iter())            or not any(ns_strip(e.tag)=='CdtTrfTxInf' for e in root.iter()):
            raise HTTPException(400,'invalid pain.001 structure')
    ack=build_ack(msgid,now)
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    try:
        c.execute('INSERT INTO pain001_records(msgid,e2e,recv_ts,raw_xml,ack_xml,status) VALUES(?,?,?,?,?,?)',
            (msgid,e2e,now,body.decode("utf-8","ignore"),ack,'ACCP')); conn.commit()
    except sqlite3.IntegrityError:
        c.execute('UPDATE pain001_records SET ack_xml=?,recv_ts=? WHERE msgid=?',(ack,now,msgid)); conn.commit()
    finally: conn.close()
    log.info('Accepted pain.001 %s',msgid)
    return Response(content=ack,media_type='application/xml')
