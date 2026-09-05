"""Local owner annotation boundary; never opens a processing admission."""
from __future__ import annotations
import ipaddress
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict
from memorybox.speech import annotations

router=APIRouter(prefix='/annotations/transcript')
class Assignment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    provider_key: str=Field(min_length=1,max_length=80)
    source_id: str=Field(min_length=1,max_length=500)
    version_id: UUID
    expected_head: UUID | None
    word_ids: list[UUID]=Field(min_length=1,max_length=500)
    person_id: UUID | None=None
    speaker_state: Literal['person','unknown','no_match']
    action: Literal['assign','withdraw']='assign'
    correction: str | None=Field(None,max_length=8000)
    reason: str=Field(min_length=1,max_length=1000)
    supersedes: UUID | None=None
    request_id: UUID

def owner(request: Request):
    # Existing MB is a local single-owner application, not an authenticated
    # multi-user service. Never trust a caller-provided actor or proxy header.
    try: local=ipaddress.ip_address(request.client.host).is_loopback
    except (ValueError,AttributeError): local=False
    if not local or request.url.hostname not in {'127.0.0.1','localhost','::1'}:
        raise HTTPException(403,'local_owner_only')
    origin=request.headers.get('origin')
    if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
        raise HTTPException(403,'same_origin_required')
    if request.method=='POST' and request.headers.get('x-mb-annotation')!='1':
        raise HTTPException(403,'annotation_request_required')
    from memorybox.profile.owner import get_owner_person_id
    actor=get_owner_person_id()
    if not actor: raise HTTPException(403,'owner_not_configured')
    return actor

@router.post('')
def save(body: Assignment, request: Request):
    actor=owner(request)
    data=body.model_dump(mode='json')
    provider=data.pop('provider_key');source=data.pop('source_id')
    if not data['reason'].strip(): raise HTTPException(422,'reason_required')
    try: return annotations.save_annotation(provider,source,actor,data)
    except annotations.AnnotationError as exc: raise HTTPException(409,str(exc)) from exc

@router.get('/coverage')
def coverage(request: Request):
    owner(request)
    return annotations.export_coverage()
