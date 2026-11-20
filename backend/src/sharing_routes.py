from fastapi import APIRouter,Depends,Request,HTTPException
from sqlalchemy import select,func
from .database import session
from .auth import current,editor,admin
from .models import Swatch
from .sharing_models import PartnerFactory,FactoryGrant,AtlasPublication
from .sharing_schemas import FactoryInput,GrantInput
from . import sharing_service as svc
router=APIRouter()

def factory_token(request:Request,db=Depends(session)):
    token=request.headers.get('X-Factory-Token') or request.query_params.get('token')
    if not token:raise HTTPException(401,'缺少外协厂访问令牌')
    factory=db.scalar(select(PartnerFactory).where(PartnerFactory.token==token))
    if not factory:raise HTTPException(401,'外协厂令牌无效')
    return factory

@router.get('/factories')
def factories(user=Depends(current),db=Depends(session)):
    rows=db.scalars(select(PartnerFactory).order_by(PartnerFactory.id)).all()
    grants=dict(db.execute(select(FactoryGrant.factory_id,func.count()).group_by(FactoryGrant.factory_id)).all())
    pubs=dict(db.execute(select(AtlasPublication.factory_id,func.count()).group_by(AtlasPublication.factory_id)).all())
    return [{'id':f.id,'code':f.code,'name':f.name,'token':f.token,'active':f.active,'epoch':f.epoch,
             'grants':grants.get(f.id,0),'publications':pubs.get(f.id,0)} for f in rows]
@router.post('/factories')
def create_factory(p:FactoryInput,user=Depends(admin),db=Depends(session)):return svc.create_factory(db,p,user)
@router.get('/factories/{key}/grants')
def grants(key:int,user=Depends(current),db=Depends(session)):
    factory=svc.get_factory(db,key)
    rows=db.execute(select(FactoryGrant,Swatch).join(Swatch,Swatch.id==FactoryGrant.swatch_id).where(FactoryGrant.factory_id==factory.id).order_by(Swatch.id)).all()
    return [{'swatch_id':s.id,'lot':s.lot,'measured':s.measured,'granted_by':g.granted_by,'created_at':g.created_at} for g,s in rows]
@router.post('/factories/{key}/grants')
def grant(key:int,p:GrantInput,user=Depends(admin),db=Depends(session)):return svc.grant(db,key,p,user)
@router.post('/factories/{key}/revoke')
def revoke(key:int,user=Depends(admin),db=Depends(session)):return svc.revoke(db,key,user)
@router.post('/factories/{key}/authorize')
def authorize(key:int,user=Depends(admin),db=Depends(session)):return svc.authorize(db,key,user)
@router.post('/factories/{key}/atlas')
def enqueue(key:int,user=Depends(editor),db=Depends(session)):return svc.enqueue(db,key,user)
@router.get('/factories/{key}/atlas')
def current_atlas(key:int,user=Depends(current),db=Depends(session)):return svc.current_atlas(db,key)
@router.get('/factories/{key}/jobs/{job_id}')
def job(key:int,job_id:str,user=Depends(current),db=Depends(session)):return svc.job_status(db,key,job_id)
@router.get('/factories/{key}/publications')
def publications(key:int,user=Depends(current),db=Depends(session)):return svc.publications(db,key)
@router.get('/shared/atlas')
def shared(factory=Depends(factory_token),db=Depends(session)):return svc.shared_current(db,factory)
@router.get('/shared/atlas/jobs/{job_id}')
def shared_job(job_id:str,factory=Depends(factory_token),db=Depends(session)):return svc.shared_job(db,factory,job_id)
