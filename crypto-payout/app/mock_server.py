from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

@app.post("/iso20022")
async def iso20022(req: Request):
    data = await req.body()
    return JSONResponse({"status":"ok","message":"mock accepted","echo_length": len(data)})

@app.post("/crypto/payout")
async def crypto_payout(req: Request):
    data = await req.json()
    return JSONResponse({"status":"ok","message":"crypto accepted","received": data})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5002)
