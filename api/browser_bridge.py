"""Token-protected writes from the optional local browser extension."""
import hmac
import json
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from export.browser_import import bridge_token, import_bundle

router = APIRouter(prefix="/bridge", tags=["Browser extension"])
MAX_REQUEST_BYTES = 2 * 1024 * 1024


def authorize(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer ") or not hmac.compare_digest(authorization[7:], bridge_token()):
        raise HTTPException(status_code=401, detail="Pair the extension using the app's browser bridge token.")


@router.get("/status", dependencies=[Depends(authorize)])
def status():
    return {"status": "ready", "schema_version": 1, "max_records_per_request": 500}


@router.post("/import", dependencies=[Depends(authorize)])
async def import_browser_data(request: Request):
    size, parts = 0, []
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_REQUEST_BYTES:
            raise HTTPException(status_code=413, detail="Browser import exceeds 2 MB; send smaller batches.")
        parts.append(chunk)
    try:
        bundle = json.loads(b"".join(parts))
        return await run_in_threadpool(import_bundle, bundle, 500)
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
