from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from backend.core.security import same_origin
from backend.database.session import SessionLocal
from backend.models.entities import Record
from backend.schemas.benchmark import BenchmarkInput

router = APIRouter(prefix='/api/benchmarks', dependencies=[Depends(same_origin)])

@router.get('')
async def history(before_id: int | None = Query(None, gt=0)):
    with SessionLocal() as session:
        query = select(Record).where(Record.kind == 'benchmark')
        if before_id:
            query = query.where(Record.id < before_id)
        records = session.scalars(query.order_by(Record.id.desc()).limit(51)).all()
        return dict(items=[dict(id=r.id, name=r.name, created_at=r.created_at.isoformat(), status=r.payload.get('status'),
                                 progress=r.payload.get('progress'), total=r.payload.get('total'), model=r.payload.get('definition',{}).get('model')) for r in records[:50]], has_more=len(records)>50)

@router.post('', status_code=202)
async def start(body: BenchmarkInput, request: Request):
    return {'id':request.app.state.benchmarks.start(body)}

@router.get('/{identifier}')
async def detail(identifier: int):
    with SessionLocal() as session:
        record = session.get(Record, identifier)
        if not record or record.kind != 'benchmark':
            raise HTTPException(404, 'Benchmark not found.')
        return dict(id=record.id, name=record.name, **record.payload)

@router.post('/{identifier}/cancel')
async def cancel(identifier: int, request: Request):
    await request.app.state.benchmarks.cancel(identifier)
    return {'cancelled':True}
