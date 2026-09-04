from __future__ import annotations
from fastapi import Request
from fastapi.responses import JSONResponse
from .scope import ScopeDenied, require_admission

async def enforce_scope(request: Request, call_next):
    path=request.url.path
    if request.method not in {"GET","HEAD","OPTIONS"}:
        try:
            if path == "/people/sync/immich":
                raise ScopeDenied("provider_seed_not_in_video_manifest")
            if path.startswith("/recognition/"):
                if path=="/recognition/seed": raise ScopeDenied("provider_seed_not_in_video_manifest")
                require_admission("face",archive=path=="/recognition/archive-pass" and request.query_params.get("full","").lower() in {"1","true","yes","on"})
            elif path.startswith("/speech/"):
                # The concrete service checks the requested lane/source/person too.
                from .scope import load_admission
                a=load_admission()
                lane="voice" if path in {"/speech/learn","/speech/moments/correct"} else ("transcribe" if "transcribe" in a.plan["lanes"] else "voice")
                require_admission(lane)
            elif path.startswith("/review/faces"):
                raise ScopeDenied("legacy_processing_has_no_reviewed_source_mapping")
        except ScopeDenied as exc:
            return JSONResponse(status_code=403,content={"ok":False,"error":str(exc)})
    return await call_next(request)
