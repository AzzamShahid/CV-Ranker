"""TextileHR local FastAPI interface; all semantic work belongs to worker."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit
import ipaddress
import json
import os
import secrets
import time
import re

from fastapi import FastAPI, Request, Response, Depends, UploadFile, File, HTTPException, Header
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, HTMLResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, ConfigDict

from backend.storage import Store, Conflict, NotFound, uid
from backend.contracts import (
    WorkspaceDTO,WorkspacesDTO,DocumentDTO,DocumentsDTO,JobSnapshotDTO,JobsDTO,
    JobEventsDTO,WeightsDTO,RankingsDTO,CandidateDetailDTO,ExportDTO,ExportsDTO,
    HistoricalListDTO,ConfirmDeletion,DeleteResultDTO,UnknownRecoveryRequest,WorkspaceDelete,
    CandidateWeightedDTO, JDRowDTO, JDDraftDTO,
    FocusedReviewRequest, FocusedReviewDTO, ReviewHistoryDTO,
    SemanticShadowRequest, SemanticShadowDTO, JobUsageDTO,
    RetentionSummaryDTO, RetentionPurgeRequest, RetentionPurgeResultDTO
)

APP_VERSION = '0.2.1-migration-checkpoint'
MAX_UPLOAD=int(os.getenv('TEXTILEHR_MAX_UPLOAD_BYTES','20971520'))
COOKIE='textilehr_local_session'


@dataclass
class Services:
    store: Store
    secret: bytes


def make_services(root: Path | None = None):
    store=Store(root)
    file=store.root/'session-secret.bin'
    if not file.exists():
        fd=os.open(file,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as out:out.write(secrets.token_bytes(32))
    secret=file.read_bytes()
    if len(secret)<32:raise RuntimeError('Local session secret is invalid')
    return Services(store,secret)


class WorkspaceCreate(BaseModel):
    title: str = Field(min_length=2,max_length=120)


class SubmitJob(BaseModel):
    model_config = ConfigDict(extra='forbid')
    candidate_ids: list[str] = Field(min_length=1,max_length=200)
    approved_revision_id: str
    provider: str = 'ollama'
    use_llm: bool = True
    unified: bool = True
    yake_top_k: int = Field(default=40,ge=1,le=150)
    openrouter_context_tokens: int | None = Field(default=None,ge=2048,le=262144)
    openrouter_output_tokens: int | None = Field(default=None,ge=1,le=65535)
    openrouter_max_requests_per_assessment: int | None = Field(default=None,ge=1,le=1000)


class ExtractionRequest(BaseModel):
    document_id: str
    provider: str = 'ollama'
    use_llm: bool = True
    yake_top_k: int = Field(default=40,ge=1,le=150)
    openrouter_context_tokens: int | None = Field(default=None,ge=2048,le=262144)
    openrouter_output_tokens: int | None = Field(default=None,ge=1,le=65535)
    openrouter_max_requests_per_assessment: int | None = Field(default=None,ge=1,le=1000)


class JDReviewEdit(BaseModel):
    draft_id: str
    revision: int
    rows: list[JDRowDTO] = Field(min_length=1)


class WeightsUpdate(BaseModel):
    revision: int
    weights: dict


class SimpleCommand(BaseModel):
    action: str


class ExportRequest(BaseModel):
    revision: int
    weight_revision: int


def create_app(store: Store | None = None, *, serve_frontend: bool=True) -> FastAPI:
    # Creating app imports NO semantic engine and makes NO provider calls.
    services=make_services(store.root if store else None) if store else make_services()
    testing=os.getenv('TEXTILEHR_TESTING')=='1'
    allowed=['localhost','127.0.0.1','[::1]'] + (['testserver'] if testing else [])
    app=FastAPI(title='TextileHR AI Local API',version=APP_VERSION,
                docs_url=None,redoc_url=None,openapi_url='/api/v1/openapi.json')
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed)
    app.state.services=services

    @app.exception_handler(NotFound)
    async def notfound(_request,exc):
        return JSONResponse(status_code=404,content={'code':'not_found','message':str(exc)})

    @app.exception_handler(Conflict)
    async def conflict(_request,exc):
        return JSONResponse(status_code=409,content={'code':'revision_conflict','message':str(exc)})

    @app.exception_handler(ValueError)
    async def validation(_request,exc):
        # A validator message can contain user-supplied text; expose only to
        # same-origin authenticated user, never logs or cross-origin callers.
        return JSONResponse(status_code=422,content={'code':'input_invalid','message':str(exc)[:300]})

    @app.exception_handler(RequestValidationError)
    async def request_validation(_request,exc):
        return JSONResponse(status_code=422,content={'code':'request_invalid',
                        'message':'Check required fields and value formats. Do not submit file paths or verdicts.'})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request,exc):
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(status_code=exc.status_code,content={'code':'http_error','message':detail,'detail':detail})

    @app.exception_handler(Exception)
    async def unhandled_exception(_request,exc):
        return JSONResponse(status_code=500,content={'code':'server_error','message':f'Server error: {str(exc)}'})

    def _origin_check(request: Request, mutation: bool):
        # Reverse-proxy/public hosting is unsupported. Trust only direct local
        # access and a single explicitly configured Vite development origin.
        client=request.client.host if request.client else ''
        try:local=ipaddress.ip_address(client).is_loopback
        except ValueError:local=(client=='testclient' and testing)
        if not local:raise HTTPException(403,'Local operator access only')
        host=request.url.hostname
        if host not in ('localhost','127.0.0.1','::1') and not (testing and host=='testserver'):
            raise HTTPException(403,'Unrecognized local host')
        if mutation:
            source=request.headers.get('origin')
            expected=f'{request.url.scheme}://{request.headers.get("host","")}'
            permitted={expected}
            dev=os.getenv('TEXTILEHR_ALLOWED_DEV_ORIGIN','').strip()
            if dev:permitted.add(dev)
            if source not in permitted:raise HTTPException(403,'Invalid request origin')

    def _cookie_value(services, session: str):
        return hmac_new(services.secret, session.encode(), 'sha256').hexdigest()

    def session_guard(request: Request):
        _origin_check(request,False)
        raw=request.cookies.get(COOKIE,'')
        if '.' not in raw:raise HTTPException(401,'Start a local session first')
        nonce,sig=raw.rsplit('.',1)
        if len(nonce)<20 or not compare_digest(_cookie_value(services,nonce),sig):
            raise HTTPException(401,'Local session expired or invalid')
        return nonce

    def mutation_guard(request: Request, session: str=Depends(session_guard)):
        _origin_check(request,True)
        expected=_cookie_value(services,'csrf:'+session)
        if not compare_digest(request.headers.get('x-csrf-token',''),expected):
            raise HTTPException(403,'CSRF validation failed')
        return session

    read=Depends(session_guard)
    write=Depends(mutation_guard)

    @app.get('/api/v1/health')
    def health():
        from cv_ranker.build_info import BUILD_ID,ASSESSMENT_PROTOCOL_VERSION
        return {'status':'alive','api_version':APP_VERSION,'engine_build':BUILD_ID,
                'assessment_protocol':ASSESSMENT_PROTOCOL_VERSION,'schema_version':4,
                'worker':'separate_process_required','installation_id':services.store.installation_id,
                'frontend_built':(Path(__file__).resolve().parents[1]/'frontend'/'dist'/'index.html').is_file()}

    @app.get('/api/v1/session')
    def bootstrap(request: Request,response:Response):
        _origin_check(request,False)
        # Bootstrap is read-only; it authorizes only a browser on this local
        # origin. A malicious other-origin script cannot read the CSRF value.
        previous=request.cookies.get(COOKIE,'')
        nonce=''
        if '.' in previous:
            candidate,sig=previous.rsplit('.',1)
            if len(candidate)>=20 and compare_digest(_cookie_value(services,candidate),sig):
                nonce=candidate
        # Reuse a valid local session when a second tab connects. Resetting
        # the cookie on every bootstrap invalidated the first tab's CSRF token.
        if not nonce:
            nonce=secrets.token_urlsafe(32)
            cookie=nonce+'.'+_cookie_value(services,nonce)
            response.set_cookie(COOKIE,cookie,httponly=True,secure=False,samesite='strict',path='/')
        response.headers['Cache-Control']='no-store'
        return {'csrf_token':_cookie_value(services,'csrf:'+nonce),
                'boundary':'single-operator-loopback','api_version':APP_VERSION}

    @app.get('/api/v1/workspaces',dependencies=[read],response_model=WorkspacesDTO)
    def workspaces():return {'items':services.store.list_workspaces()}

    @app.post('/api/v1/workspaces',status_code=201,dependencies=[write],response_model=WorkspaceDTO)
    def create_workspace(body:WorkspaceCreate):return services.store.create_workspace(body.title.strip())

    @app.get('/api/v1/workspaces/{workspace_id}',dependencies=[read],response_model=WorkspaceDTO)
    def workspace(workspace_id:str):return services.store.workspace(workspace_id)

    @app.get('/api/v1/workspaces/{workspace_id}/documents',dependencies=[read],response_model=DocumentsDTO)
    def documents(workspace_id:str):return {'items':services.store.documents(workspace_id),
       'formats':['.txt','.md','.pdf','.docx'],'max_upload_bytes':MAX_UPLOAD}

    @app.post('/api/v1/workspaces/{workspace_id}/documents',status_code=201,dependencies=[write],response_model=DocumentDTO)
    async def upload(workspace_id:str,kind:str,file:UploadFile=File(...)):
        from cv_ranker.documents import SUPPORTED_EXTENSIONS
        if kind not in ('cv','jd'):raise ValueError('Document kind must be cv or jd')
        title=(file.filename or 'unnamed').replace('\\','/').split('/')[-1]
        title=title.replace('\x00','')[:180]
        suffix=Path(title).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:raise ValueError('Only TXT, MD, PDF and DOCX are accepted')
        chunks=[];size=0
        try:
            while True:
                data=await file.read(min(1048576,MAX_UPLOAD-size+1))
                if not data:break
                size+=len(data)
                if size>MAX_UPLOAD:raise HTTPException(413,'Document exceeds configured upload limit')
                chunks.append(data)
        finally:
            await file.close()
        content=b''.join(chunks)
        if not content:raise ValueError('The uploaded document is empty')
        if suffix=='.pdf' and not content.startswith(b'%PDF-'):raise ValueError('PDF content signature is invalid')
        if suffix=='.docx':
            if not content.startswith(b'PK\x03\x04'):
                raise ValueError('DOCX content signature is invalid')
            # Guard against compressed oversized OOXML before python-docx
            # opens it. No uploaded archive is ever extracted by this API.
            from io import BytesIO
            from zipfile import ZipFile, BadZipFile
            try:
                with ZipFile(BytesIO(content)) as archive:
                    if len(archive.infolist())>2500 or sum(i.file_size for i in archive.infolist())>80*1024*1024:
                        raise ValueError('DOCX internal content exceeds safety limits')
            except BadZipFile as exc:
                raise ValueError('Invalid DOCX ZIP structure') from exc
        if suffix=='.pdf':
            import fitz
            try:
                with fitz.open(stream=content,filetype='pdf') as pdf:
                    if pdf.page_count>250:raise ValueError('PDF page count exceeds the local processing limit')
            except ValueError:raise
            except Exception as exc:raise ValueError('PDF structure could not be inspected') from exc
        if suffix in ('.txt','.md') and b'\x00' in content[:4096]:raise ValueError('Plain-text file appears to contain binary data')
        return services.store.add_document(workspace_id,kind,title,suffix,content)

    @app.get('/api/v1/workspaces/{workspace_id}/documents/{document_id}/download',dependencies=[read])
    def download_document(workspace_id:str,document_id:str):
        document=services.store.document(workspace_id,document_id)
        return FileResponse(services.store.document_path(workspace_id,document_id),
             media_type='application/octet-stream',filename=document['filename'],
             headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @app.get('/api/v1/workspaces/{workspace_id}/jd',dependencies=[read])
    def jd(workspace_id:str):
        return {'draft':services.store.latest_draft(workspace_id),
                'approved':services.store.latest_approval(workspace_id)}

    @app.get('/api/v1/workspaces/{workspace_id}/jd/drafts/{draft_id}',dependencies=[read],response_model=JDDraftDTO)
    def jd_draft(workspace_id:str,draft_id:str):
        from backend.engine_service import editable_rows
        result=services.store.draft(workspace_id,draft_id)
        return {**result,'rows':editable_rows(result['body'])}

    def frozen_settings(provider:str,use_llm:bool,unified:bool,yake_top_k:int,
                        context_tokens:int|None=None,output_tokens:int|None=None,
                        request_ceiling:int|None=None):
        from cv_ranker.config import Settings
        # No network access or generation occurs here. Cloud credentials
        # stay server-side: only settings needed to reproduce model choices
        # are stored in the durable job request.
        source=Settings(llm_provider=provider if use_llm else 'ollama')
        # The operator may REDUCE the installed provider limits per run, but
        # not increase them to defeat a server-side safety budget.
        if (context_tokens is not None and context_tokens>source.openrouter_context_tokens
             or output_tokens is not None and output_tokens>source.openrouter_output_tokens
             or request_ceiling is not None and request_ceiling>source.openrouter_max_requests_per_assessment):
            raise ValueError('A run cannot exceed configured provider context, output or request ceilings')
        actual_context=context_tokens if context_tokens is not None else source.openrouter_context_tokens
        actual_output=output_tokens if output_tokens is not None else source.openrouter_output_tokens
        if actual_output>=actual_context:raise ValueError('Output budget must be below context budget')
        return {'provider':provider,'use_llm':use_llm,'unified':unified,'yake_top_k':yake_top_k,
                'model_name':source.model_name,'ollama_model':source.ollama_model,
                'openrouter_model':source.openrouter_model,'embedding_model':source.embedding_model,
                'openrouter_context_tokens':actual_context,'openrouter_output_tokens':actual_output,
                'openrouter_max_requests_per_assessment':(request_ceiling if request_ceiling is not None
                    else source.openrouter_max_requests_per_assessment)}

    @app.post('/api/v1/workspaces/{workspace_id}/jd/extraction-jobs',status_code=202,dependencies=[write],response_model=JobSnapshotDTO)
    def start_extract(workspace_id:str,body:ExtractionRequest,idempotency_key:Annotated[str|None,Header(alias='Idempotency-Key')]=None):
        document=services.store.document(workspace_id,body.document_id)
        if document['kind']!='jd':raise ValueError('Select a job description document')
        if body.provider not in ('ollama','openrouter'):raise ValueError('Unsupported model provider')
        request={'document_id':body.document_id,'settings':frozen_settings(body.provider,body.use_llm,False,body.yake_top_k,
                     body.openrouter_context_tokens,body.openrouter_output_tokens,
                     body.openrouter_max_requests_per_assessment)}
        return services.store.make_job(workspace_id,'jd_extract',request,idempotency_key or '')

    def validate_years(rows:list[JDRowDTO], approved):
        # A human may correct JD scope/quote; the source-bound Python
        # classifier remains authoritative about any numeric minimum.
        for index,(edit,requirement) in enumerate(zip(rows,approved.requirements),1):
            if edit.minimum_years is not None:
                inferred=requirement.constraint.minimum_years
                if inferred is None or abs(float(inferred)-edit.minimum_years)>1e-9:
                    raise ValueError(f'JD row {index}: Minimum years must agree with the exact JD quotation')

    @app.post('/api/v1/workspaces/{workspace_id}/jd/approve',dependencies=[write])
    def approve(workspace_id:str,body:JDReviewEdit):
        from backend.engine_service import validate_approved_revision
        from cv_ranker.documents import extract_text
        from cv_ranker.config import Settings
        draft=services.store.draft(workspace_id,body.draft_id)
        try:
            doc_path=services.store.document_path(workspace_id,draft['document_id'])
        except NotFound:
            raise HTTPException(status_code=404, detail="The original JD file is unavailable in server storage. Please re-upload the JD document to proceed.")
        approved=validate_approved_revision(draft['body'],extract_text(doc_path),
                    [row.model_dump(by_alias=True) for row in body.rows],Settings(llm_provider='ollama').max_requirements)
        validate_years(body.rows,approved)
        return services.store.approve(workspace_id,body.draft_id,body.revision,approved.model_dump(mode='json'))

    @app.put('/api/v1/workspaces/{workspace_id}/jd/drafts/{draft_id}',dependencies=[write])
    def revise(workspace_id:str,draft_id:str,body:JDReviewEdit):
        # A previously approved revision is never mutated; edits create a new
        # version after the same source-bound validation as an approval.
        from backend.engine_service import validate_approved_revision
        from cv_ranker.documents import extract_text
        from cv_ranker.config import Settings
        if draft_id!=body.draft_id:raise ValueError('Draft ID mismatch')
        draft=services.store.draft(workspace_id,draft_id)
        try:
            doc_path=services.store.document_path(workspace_id,draft['document_id'])
        except NotFound:
            raise HTTPException(status_code=404, detail="The original JD file is unavailable in server storage. Please re-upload the JD document to proceed.")
        text=extract_text(doc_path)
        edited=validate_approved_revision(draft['body'],text,[row.model_dump(by_alias=True) for row in body.rows],Settings(llm_provider='ollama').max_requirements)
        validate_years(body.rows,edited)
        return services.store.revise_draft(workspace_id,draft_id,body.revision,
               edited.model_copy(update={'approved':False}).model_dump(mode='json'))

    @app.get('/api/v1/workspaces/{workspace_id}/weights',dependencies=[read],response_model=WeightsDTO)
    def weights(workspace_id:str):return services.store.weights(workspace_id)

    @app.post('/api/v1/workspaces/{workspace_id}/weights/rebalance',dependencies=[write])
    def rebalance(workspace_id:str,body:dict):
        from cv_ranker.schemas import ValidatedRequirement
        from cv_ranker.weighted_scoring import even_requirement_shares,rebalance_requirement_share
        approval=services.store.latest_approval(workspace_id)
        if not approval:raise ValueError('Approve a JD before allocating requirement shares')
        requirements=[ValidatedRequirement.model_validate(row) for row in approval['body']['requirements']]
        proposed=body.get('shares')
        if not isinstance(proposed,dict) or set(proposed)!={r.requirement_id for r in requirements}:
            proposed=even_requirement_shares(requirements)
        changed=body.get('requirement_id')
        if changed is not None:
            proposed=rebalance_requirement_share(requirements,proposed,changed,float(body.get('new_share')))
        return {'shares':proposed}

    @app.put('/api/v1/workspaces/{workspace_id}/weights',dependencies=[write],response_model=WeightsDTO)
    def update_weights(workspace_id:str,body:WeightsUpdate):
        from backend.engine_service import score_weights
        from cv_ranker.weighted_scoring import allocation_bucket
        from math import isclose
        canonical=score_weights(body.weights)
        approved=services.store.latest_approval(workspace_id)
        if canonical.requirement_shares:
            if not approved:raise ValueError('Approve a JD before allocating requirement shares')
            reqs=approved['body']['requirements']
            expected={r['requirement_id']:allocation_bucket(__import__('cv_ranker.schemas',fromlist=['ValidatedRequirement']).ValidatedRequirement.model_validate(r)) for r in reqs}
            shares=dict(canonical.requirement_shares)
            if set(shares)!=set(expected):raise ValueError('Every frozen requirement must have exactly one share')
            for cat in set(expected.values()):
                if not isclose(sum(shares[k] for k in shares if expected[k]==cat),100.0,abs_tol=0.03):
                    raise ValueError('Requirement shares must total 100% within each category')
        return services.store.set_weights(workspace_id,body.revision,canonical.as_dict())

    @app.post('/api/v1/workspaces/{workspace_id}/assessment-jobs',status_code=202,dependencies=[write],response_model=JobSnapshotDTO)
    def start_assessment(workspace_id:str,body:SubmitJob,
                         idempotency_key:Annotated[str|None,Header(alias='Idempotency-Key')]=None):
        if len(set(body.candidate_ids))!=len(body.candidate_ids):raise ValueError('Duplicate candidate ID')
        services.store.approval(workspace_id,body.approved_revision_id)
        for candidate in body.candidate_ids:
            doc=services.store.document(workspace_id,candidate)
            if doc['kind']!='cv':raise ValueError('Assessment requires CV documents')
        if body.provider not in ('ollama','openrouter'):raise ValueError('Unsupported provider')
        if body.unified and not body.use_llm:raise ValueError('Unified evaluation requires a configured model; choose legacy fallback explicitly')
        request={'candidate_ids':body.candidate_ids,'approved_revision_id':body.approved_revision_id,
                 'settings':frozen_settings(body.provider,body.use_llm,body.unified,body.yake_top_k,
                     body.openrouter_context_tokens,body.openrouter_output_tokens,
                     body.openrouter_max_requests_per_assessment)}
        return services.store.make_job(workspace_id,'assess',request,idempotency_key or '')

    @app.get('/api/v1/workspaces/{workspace_id}/submissions/{intent_key}',
             dependencies=[read],response_model=JobSnapshotDTO)
    def submission_recovery(workspace_id:str,intent_key:str):
        # Read-only replay after a lost HTTP response. Never a model dispatch.
        return services.store.submission(workspace_id,intent_key)

    @app.get('/api/v1/workspaces/{workspace_id}/jobs',dependencies=[read],response_model=JobsDTO)
    def jobs(workspace_id:str):return {'items':services.store.jobs(workspace_id)}

    @app.get('/api/v1/workspaces/{workspace_id}/jobs/{job_id}',dependencies=[read],response_model=JobSnapshotDTO)
    def job(workspace_id:str,job_id:str):return services.store.job(workspace_id,job_id)

    @app.post('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/cancel',dependencies=[write],response_model=JobSnapshotDTO)
    def cancel_job(workspace_id:str,job_id:str):
        return services.store.control(workspace_id,job_id,'cancel')

    @app.post('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/resume',dependencies=[write],response_model=JobSnapshotDTO)
    def resume_job(workspace_id:str,job_id:str):
        return services.store.control(workspace_id,job_id,'resume')

    @app.get('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/event-history',dependencies=[read],response_model=JobEventsDTO)
    def event_history(workspace_id:str,job_id:str,after:int=0,limit:int=100):
        consistent=services.store.event_snapshot(workspace_id,job_id)
        return {'items':services.store.events(workspace_id,job_id,max(0,after),limit),
                'snapshot':consistent['snapshot']}

    @app.get('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/events',dependencies=[read])
    async def events(workspace_id:str,job_id:str,request:Request,after:int=0):
        consistent=services.store.event_snapshot(workspace_id,job_id)
        latest=consistent['snapshot']
        raw=request.headers.get('last-event-id',str(after))
        if not raw.isdecimal():
            raise HTTPException(422,'Last-Event-ID must be a nonnegative sequence number')
        last=int(raw)
        if last>latest['sequence']:
            last=latest['sequence']
        # A new subscriber starts after the atomic snapshot watermark. An
        # existing subscriber receives prior events by Last-Event-ID.
        cursor=last if last>0 else latest['sequence']
        expired=last>0 and last<consistent['earliest']-1
        if expired:
            cursor=latest['sequence']
        async def stream():
            nonlocal cursor
            yield 'event: snapshot\ndata: '+json.dumps(latest,ensure_ascii=False)+'\n\n'
            if expired:
                yield 'event: replay_expired\ndata: '+json.dumps({'sequence':latest['sequence']})+'\n\n'
            heartbeat_at=time.monotonic()
            while not await request.is_disconnected():
                new=services.store.events(workspace_id,job_id,cursor)
                for item in new:
                    cursor=item['seq']
                    yield (f'id: {cursor}\nevent: {item["kind"]}\ndata: '+
                           json.dumps(item['payload'],ensure_ascii=False)+'\n\n')
                if time.monotonic()-heartbeat_at>12:
                    yield ': heartbeat\n\n'; heartbeat_at=time.monotonic()
                await asyncio.sleep(1.5)
        return StreamingResponse(stream(),media_type='text/event-stream',headers={
            'Cache-Control':'no-store','X-Accel-Buffering':'no','Connection':'keep-alive'})

    @app.get('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/rankings',dependencies=[read],response_model=RankingsDTO)
    def rankings(workspace_id:str,job_id:str,limit:int=50,offset:int=0,search:str='',
                 expected_result_revision:int|None=None,expected_weight_revision:int|None=None):
        from backend.engine_service import projection
        snapshot=services.store.assessment_snapshot(workspace_id,job_id)
        if (expected_result_revision is not None and
                expected_result_revision != snapshot['result_revision'] or
                expected_weight_revision is not None and
                expected_weight_revision != snapshot['weight_revision']):
            raise Conflict('Rankings changed between pages; restart from the first page')
        report=snapshot['report']
        if (snapshot['job']['kind'] != 'assess' or report is None or
                not isinstance(report, dict) or 'candidates' not in report):
            return {'items':[],'total':0,'ready':False,
                    'offset':offset,'limit':limit,'search':search,
                    'weight_revision':snapshot['weight_revision'],
                    'result_revision':snapshot['result_revision'],
                    'official_count':0,'unfinished_count':0}
        items=projection(report,snapshot['weights'])
        for item in items:
            idx=int(item['candidate_index'])
            item['candidate_id']=report['candidates'][idx]['candidate_source']
        comparative_summary = None
        try:
            from cv_ranker.ranking_reasoning import comparative_reasoning
            from backend.engine_service import score_weights, report_from_json
            comparison = comparative_reasoning(report_from_json(report), score_weights(snapshot['weights']))
            comparative_summary = comparison.get('summary')
            cand_map = {c.get('candidate_index'): c for c in comparison.get('candidates', [])}
            by_other = {c.get('against_candidate_index'): c for c in comparison.get('comparisons', [])}
            for item in items:
                idx = int(item['candidate_index'])
                c_entry = cand_map.get(idx)
                if c_entry:
                    item['placement_reason'] = c_entry.get('placement_reason')
                    diff = by_other.get(idx)
                    if diff:
                        item['score_gap'] = diff.get('score_gap')
        except Exception:
            pass
        # Search is server-wide; a later-page candidate must still be found.
        if search:
            items=[row for row in items if search.casefold() in row['candidate'].casefold()]
        official_count = sum(1 for row in items if row.get('weighted_score') is not None)
        unfinished_count = sum(1 for row in items if row.get('weighted_score') is None)
        return {'items':items[max(0,offset):max(0,offset)+max(1,min(200,limit))],
                'total':len(items),'ready':True,'offset':max(0,offset),'limit':max(1,min(200,limit)),
                'search':search,'weight_revision':snapshot['weight_revision'],
                'result_revision':snapshot['result_revision'],
                'official_count':official_count,
                'unfinished_count':unfinished_count,
                'comparative_summary':comparative_summary}

    @app.get('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/candidates/{doc_id}/weighted',
             dependencies=[read],response_model=CandidateWeightedDTO)
    def weighted_candidate(workspace_id:str,job_id:str,doc_id:str):
        from backend.engine_service import projection
        snapshot=services.store.assessment_snapshot(workspace_id,job_id)
        report=snapshot['report']
        if report is None:raise NotFound('Candidate result unavailable')
        items=projection(report,snapshot['weights'])
        for row in items:
            index=int(row['candidate_index'])
            source=report['candidates'][index]['candidate_source']
            if source==doc_id:
                row['candidate_id']=source
                return {'candidate_id':source,'result_revision':snapshot['result_revision'],
                        'weight_revision':snapshot['weight_revision'],'result':row}
        raise NotFound('Candidate not present in the saved result')

    @app.get('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/candidates/{doc_id}',dependencies=[read],response_model=CandidateDetailDTO)
    def candidate_detail(workspace_id:str,job_id:str,doc_id:str):
        from backend.engine_service import candidate_projection
        snapshot=services.store.assessment_snapshot(workspace_id,job_id)
        report=snapshot['report']
        if report is None:raise NotFound('Candidate details are not ready')
        services.store.document(workspace_id,doc_id)
        index=next((i for i,c in enumerate(report['candidates']) if c['candidate_source']==doc_id),-1)
        if index<0:raise NotFound('Candidate has not completed its assessment')
        ledger=next((json.loads(r['source_ledger_json']).get('segments',[]) for r in snapshot['ledgers']
                   if r['document_id']==doc_id),[])
        ranking_reasoning = None
        try:
            from cv_ranker.ranking_reasoning import comparative_reasoning
            from backend.engine_service import score_weights, report_from_json
            comparison = comparative_reasoning(report_from_json(report), score_weights(snapshot['weights']))
            cand_entry = next((c for c in comparison.get('candidates', []) if c.get('candidate_index') == index), None)

            def _to_reasoning_item(raw: dict) -> dict:
                pts = raw.get('earned_points')
                if pts is None:
                    pts = raw.get('possible_points')
                return {
                    'requirement_id': raw.get('requirement_id', ''),
                    'requirement': raw.get('requirement', ''),
                    'priority': raw.get('priority', ''),
                    'category': raw.get('category'),
                    'decision': raw.get('decision', ''),
                    'points': round(pts, 2) if pts is not None else None,
                    'why': raw.get('why', ''),
                }

            def _to_reasoning_items(raw_list: list) -> list:
                return [_to_reasoning_item(item) for item in raw_list if isinstance(item, dict) and item.get('requirement')]

            if cand_entry:
                head_to_head = next((c for c in comparison.get('comparisons', []) if c.get('against_candidate_index') == index), None)
                all_comps = [
                    {
                        'against_candidate_index': comp['against_candidate_index'],
                        'against': comp['against'],
                        'rank': comp.get('rank'),
                        'score_gap': comp.get('score_gap'),
                        'top_candidate_advantages': _to_reasoning_items(comp.get('top_candidate_advantages', [])),
                        'other_candidate_advantages': _to_reasoning_items(comp.get('other_candidate_advantages', [])),
                        'is_tie': comp.get('is_tie', False),
                    }
                    for comp in comparison.get('comparisons', [])
                ]
                ranking_reasoning = {
                    'summary': cand_entry.get('summary', ''),
                    'placement_reason': cand_entry.get('placement_reason', ''),
                    'rank': cand_entry.get('rank'),
                    'score': cand_entry.get('weighted_score'),
                    'strengths': _to_reasoning_items(cand_entry.get('strengths', [])),
                    'gaps': _to_reasoning_items(cand_entry.get('gaps', [])),
                    'transferable': _to_reasoning_items(cand_entry.get('transferable', [])),
                    'head_to_head_summary': comparison.get('summary', ''),
                    'top_candidate_advantages': _to_reasoning_items(head_to_head.get('top_candidate_advantages', [])) if head_to_head else [],
                    'other_candidate_advantages': _to_reasoning_items(head_to_head.get('other_candidate_advantages', [])) if head_to_head else [],
                    'score_gap': head_to_head.get('score_gap') if head_to_head else None,
                    'all_comparisons': all_comps,
                }
        except Exception:
            ranking_reasoning = None

        return {'result_revision':snapshot['result_revision'],
                'candidate':report['candidates'][index],
                'final':candidate_projection(report,index,ledger),'original_segments':ledger,
                'requirements':report['requirements'],
                'ranking_reasoning':ranking_reasoning}

    @app.post('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/candidates/{doc_id}/focused-review',
              dependencies=[write],response_model=FocusedReviewDTO)
    def run_focused_review(workspace_id:str,job_id:str,doc_id:str,body:FocusedReviewRequest):
        return services.store.execute_focused_review(
            workspace_id,job_id,doc_id,body.requirement_id,body.provider,body.use_llm,
            expected_result_revision=body.expected_result_revision,
            idempotency_key=body.idempotency_key
        )

    @app.get('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/candidates/{doc_id}/review-history',
             dependencies=[read],response_model=ReviewHistoryDTO)
    def review_history(workspace_id:str,job_id:str,doc_id:str):
        return {'items':services.store.list_focused_reviews(workspace_id,job_id,doc_id)}

    @app.post('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/semantic-shadow',
              dependencies=[write],response_model=SemanticShadowDTO)
    def run_semantic_shadow_endpoint(workspace_id:str,job_id:str,body:SemanticShadowRequest):
        from backend.engine_service import run_semantic_shadow_diagnostic
        snapshot=services.store.assessment_snapshot(workspace_id,job_id)
        report=snapshot['report']
        if report is None:
            raise NotFound('Assessment report is not ready for semantic analysis')
        diag=run_semantic_shadow_diagnostic(
            report,top_k=body.top_k,embedding_model=body.embedding_model,
            cache_dir=services.store.root/'semantic',
            workspace_id=workspace_id,
            store=services.store,
        )
        return services.store.save_semantic_shadow(workspace_id,job_id,diag)

    @app.get('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/semantic-shadow',
             dependencies=[read],response_model=SemanticShadowDTO)
    def get_semantic_shadow_endpoint(workspace_id:str,job_id:str):
        return services.store.get_semantic_shadow(workspace_id,job_id)

    @app.get('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/usage',
             dependencies=[read],response_model=JobUsageDTO)
    def job_usage(workspace_id:str,job_id:str):
        return services.store.get_job_metrics(workspace_id,job_id)

    @app.get('/api/v1/workspaces/{workspace_id}/exports',dependencies=[read],response_model=ExportsDTO)
    def exports(workspace_id:str):return {'items':services.store.exports(workspace_id)}

    @app.post('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/exports',status_code=201,dependencies=[write],response_model=ExportDTO)
    def make_export(workspace_id:str,job_id:str,body:ExportRequest):
        from backend.engine_service import export_zip
        snapshot=services.store.assessment_snapshot(workspace_id,job_id)
        if (body.revision!=snapshot['result_revision'] or
                body.weight_revision!=snapshot['weight_revision']):
            raise Conflict('Result/weight revision changed. Reload before exporting.')
        report=snapshot['report']
        if report is None:raise ValueError('No committed report to export')
        by_id={row['document_id']:json.loads(row['source_ledger_json']).get('segments',[])
               for row in snapshot['ledgers']}
        ledgers={str(index):by_id.get(candidate['candidate_source'],[])
                 for index,candidate in enumerate(report['candidates'])}
        data=export_zip(report,snapshot['weights'],ledgers)
        # record_export checks both revisions AGAIN before publication. The
        # ZIP is generated outside a write lock and discarded on conflicts.
        return services.store.record_export(workspace_id,job_id,
            snapshot['weight_revision'],snapshot['result_revision'],data)

    @app.get('/api/v1/workspaces/{workspace_id}/exports/{export_id}/download',dependencies=[read])
    def download(workspace_id:str,export_id:str):
        row=services.store.export_row(workspace_id,export_id)
        return FileResponse(services.store.export_root/row['stored_name'],media_type='application/zip',
                   filename='TextileHR_Assessment_'+export_id[:8]+'.zip',headers={'Cache-Control':'no-store'})

    @app.delete('/api/v1/workspaces/{workspace_id}/jobs/{job_id}',dependencies=[write],response_model=DeleteResultDTO)
    def delete_assessment(workspace_id:str,job_id:str,body:ConfirmDeletion):
        return services.store.delete_assessment(workspace_id,job_id)

    @app.delete('/api/v1/workspaces/{workspace_id}',dependencies=[write],response_model=DeleteResultDTO)
    def delete_workspace(workspace_id:str,body:WorkspaceDelete):
        return services.store.delete_workspace(workspace_id)

    @app.delete('/api/v1/workspaces/{workspace_id}/documents/{document_id}',dependencies=[write],response_model=DeleteResultDTO)
    def delete_document(workspace_id:str,document_id:str,body:ConfirmDeletion):
        return services.store.delete_document(workspace_id,document_id)

    @app.delete('/api/v1/workspaces/{workspace_id}/exports/{export_id}',dependencies=[write],response_model=DeleteResultDTO)
    def delete_export(workspace_id:str,export_id:str,body:ConfirmDeletion):
        return services.store.delete_export(workspace_id,export_id)

    @app.post('/api/v1/workspaces/{workspace_id}/jobs/{job_id}/resolve-unknown',dependencies=[write])
    def resolve_unknown(workspace_id:str,job_id:str,body:UnknownRecoveryRequest):
        return services.store.recover_unknown(workspace_id,job_id,body.resolution,body.acknowledgement)

    @app.get('/api/v1/workspaces/{workspace_id}/retention',dependencies=[read],response_model=RetentionSummaryDTO)
    def retention_summary(workspace_id:str,days:int=30):
        return services.store.get_retention_summary(workspace_id,default_days=days)

    @app.post('/api/v1/workspaces/{workspace_id}/retention/purge',dependencies=[write],response_model=RetentionPurgeResultDTO)
    def retention_purge(workspace_id:str,body:RetentionPurgeRequest):
        return services.store.purge_retention(workspace_id,retention_days=body.retention_days)

    @app.get('/api/v1/workspaces/{workspace_id}/historical-reports',dependencies=[read],response_model=HistoricalListDTO)
    def historical_reports(workspace_id:str):
        return {'items':services.store.historical(workspace_id)}

    @app.post('/api/v1/workspaces/{workspace_id}/historical-reports',status_code=201,dependencies=[write])
    async def import_historical_report(workspace_id:str,file:UploadFile=File(...)):
        from cv_ranker.schemas import RankingReport
        name=(file.filename or 'historical.json').replace('\\','/').split('/')[-1]
        suffix=Path(name).suffix.lower()
        if suffix not in ('.json','.zip'):
            raise ValueError('Historical import accepts validated JSON reports or TextileHR export ZIPs')
        data=await file.read(20_000_001)
        await file.close()
        if len(data)>20_000_000:raise HTTPException(413,'Historical archive exceeds size limit')
        if suffix=='.zip':
            from io import BytesIO
            from zipfile import ZipFile,BadZipFile
            from pathlib import PurePosixPath
            try:
                with ZipFile(BytesIO(data)) as archive:
                    entries=archive.infolist()
                    if (len(entries)>500 or
                         sum(x.file_size for x in entries)>80_000_000 or
                         any(x.file_size>10_000_000 for x in entries)):
                        raise ValueError('Historical ZIP exceeds safe entry limits')
                    names=set()
                    for info in entries:
                        path=PurePosixPath(info.filename)
                        if (info.filename.startswith('/') or '\\' in info.filename or '..' in path.parts
                             or info.filename in names or ((info.external_attr>>16)&0o170000)==0o120000):
                            raise ValueError('Historical ZIP contains an unsafe path, duplicate or symbolic link')
                        names.add(info.filename)
                    if 'complete_assessment.json' not in names:
                        raise ValueError('Historical ZIP does not contain complete_assessment.json')
                    data=archive.read('complete_assessment.json')
            except (BadZipFile,EOFError) as exc:
                raise ValueError('Historical ZIP structure is invalid') from exc
        try:report=RankingReport.model_validate_json(data)
        except Exception as exc:raise ValueError('Historical report does not match the supported audit schema') from exc
        # An imported historical result is archived read-only, never regarded
        # as revalidated by this current assessment protocol.
        return services.store.import_historical(workspace_id,name,report.model_dump(mode='json'))

    @app.get('/api/v1/workspaces/{workspace_id}/historical-reports/{report_id}',dependencies=[read])
    def historical_report(workspace_id:str,report_id:str):
        return services.store.historical_report(workspace_id,report_id)

    @app.get('/api/v1/settings',dependencies=[read])
    def settings():
        # This endpoint never instantiates a provider or exposes cloud secrets.
        from cv_ranker.build_info import BUILD_ID,ASSESSMENT_PROTOCOL_VERSION
        return {'engine_build':BUILD_ID,'protocol':ASSESSMENT_PROTOCOL_VERSION,
            'available_providers':['ollama','openrouter'],
            'configured_provider':os.getenv('CVR_LLM_PROVIDER','ollama'),
            'organization_name':os.getenv('CVR_ORGANIZATION_NAME','Reliance Weaving Mills Ltd.'),
            'ollama_model':os.getenv('OLLAMA_MODEL','qwen2.5:3b'),
            'openrouter_model':os.getenv('OPENROUTER_MODEL','google/gemini-2.5-flash-lite'),
            'openrouter_key_configured':bool(os.getenv('OPENROUTER_API_KEY')),
            'yake_top_k_default':40,
            'openrouter_context_tokens':__import__('cv_ranker.config',fromlist=['Settings']).Settings(llm_provider='ollama').openrouter_context_tokens,
            'openrouter_output_tokens':__import__('cv_ranker.config',fromlist=['Settings']).Settings(llm_provider='ollama').openrouter_output_tokens,
            'openrouter_max_requests_per_assessment':__import__('cv_ranker.config',fromlist=['Settings']).Settings(llm_provider='ollama').openrouter_max_requests_per_assessment,
            'local_only':True,
            'data_retention':'Operator-managed local folder; exports remain until explicitly removed.'}

    if serve_frontend:
        from fastapi.staticfiles import StaticFiles
        root=Path(__file__).resolve().parents[1]/'frontend'/'dist'
        if (root/'index.html').exists():
            app.mount('/assets',StaticFiles(directory=root/'assets'),name='assets')
            @app.get('/{ui_path:path}',include_in_schema=False)
            def spa(ui_path:str):
                if ui_path.startswith(('api/','assets/')):
                    raise HTTPException(404,'Not found')
                if '.' in ui_path:raise HTTPException(404,'Unknown static file')
                return HTMLResponse((root/'index.html').read_text(encoding='utf-8'),headers={'Cache-Control':'no-store'})
        else:
            @app.get('/{ui_path:path}',include_in_schema=False)
            def frontend_not_built(ui_path:str):
                if ui_path.startswith(('api/','assets/')) or '.' in ui_path:
                    raise HTTPException(404,'Not found')
                return JSONResponse(status_code=503,content={'code':'frontend_build_missing',
                      'message':'Install the pinned frontend dependencies and run npm run build in frontend/.'})
    return app


app = create_app()
