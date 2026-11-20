import os,json,uuid,secrets
import redis
from fastapi import HTTPException
from sqlalchemy import select
from .models import Swatch,Audit
from .sharing_models import PartnerFactory,FactoryGrant,AtlasPublication
queue=redis.Redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'),decode_responses=True)
JOB_TTL=86400

def log(db,user,action):db.add(Audit(actor=user.email,action=action))
def get_factory(db,key):
    factory=db.get(PartnerFactory,key)
    if not factory:raise HTTPException(404,'外协厂不存在')
    return factory
def measured_grants(db,factory_id):
    return db.scalars(select(Swatch).join(FactoryGrant,FactoryGrant.swatch_id==Swatch.id).where(FactoryGrant.factory_id==factory_id,Swatch.measured==True).order_by(Swatch.id)).all()

def create_factory(db,data,user):
    if db.scalar(select(PartnerFactory).where(PartnerFactory.code==data.code)):raise HTTPException(409,'外协厂编号已存在')
    factory=PartnerFactory(code=data.code,name=data.name,token=secrets.token_hex(16),active=True,epoch=1)
    db.add(factory);db.flush();log(db,user,f'建立外协厂档案 {factory.code}');db.commit();db.refresh(factory);return factory

def grant(db,key,data,user):
    factory=get_factory(db,key)
    if not factory.active:raise HTTPException(409,'该厂授权已撤回，请先重新授权再分配染样')
    ids=list(dict.fromkeys(data.swatch_ids))
    swatches={s.id:s for s in db.scalars(select(Swatch).where(Swatch.id.in_(ids))).all()}
    missing=[i for i in ids if i not in swatches]
    if missing:raise HTTPException(404,'染样不存在: '+','.join(map(str,missing)))
    unmeasured=[s.lot for s in swatches.values() if not s.measured]
    if unmeasured:raise HTTPException(409,'仅实测染样可授权外协厂: '+','.join(unmeasured))
    existing=set(db.scalars(select(FactoryGrant.swatch_id).where(FactoryGrant.factory_id==factory.id)).all())
    added=0
    for sid in ids:
        if sid in existing:continue
        db.add(FactoryGrant(factory_id=factory.id,swatch_id=sid,granted_by=user.email));added+=1
    log(db,user,f'为外协厂 {factory.code} 授权 {added} 张实测染样');db.commit()
    return {'factory_id':factory.id,'added':added,'total':len(existing)+added}

def revoke(db,key,user):
    factory=get_factory(db,key)
    if not factory.active:raise HTTPException(409,'该厂授权已处于撤回状态')
    factory.active=False;factory.epoch+=1
    log(db,user,f'撤回外协厂 {factory.code} 图谱授权，epoch 升至 {factory.epoch}');db.commit()
    return {'factory_id':factory.id,'active':factory.active,'epoch':factory.epoch}

def authorize(db,key,user):
    factory=get_factory(db,key)
    if factory.active:raise HTTPException(409,'该厂授权仍然有效，无需重复授权')
    factory.active=True;factory.epoch+=1
    log(db,user,f'重新授权外协厂 {factory.code}，epoch 升至 {factory.epoch}');db.commit()
    return {'factory_id':factory.id,'active':factory.active,'epoch':factory.epoch}

def enqueue(db,key,user):
    factory=get_factory(db,key)
    if not factory.active:raise HTTPException(409,'该厂授权已撤回，不能生成图谱')
    swatches=measured_grants(db,factory.id)
    if not swatches:raise HTTPException(422,'该厂尚未获得任何实测染样授权，无法出图')
    if len(swatches)<3:raise HTTPException(422,f'该厂获准实测染样仅 {len(swatches)} 张，PCA 至少需要 3 张，请先授权更多染样')
    job_id=uuid.uuid4().hex
    queue.set('factory:atlas:job:'+job_id,json.dumps({'factory_id':factory.id,'epoch':factory.epoch}),ex=JOB_TTL)
    queue.set('factory:atlas:result:'+job_id,json.dumps({'state':'queued'}),ex=JOB_TTL)
    queue.rpush('factory:atlas:queue',json.dumps({'job_id':job_id,'factory_id':factory.id,'epoch':factory.epoch}))
    log(db,user,f'为外协厂 {factory.code} 提交图谱任务(epoch {factory.epoch}，{len(swatches)} 张染样)');db.commit()
    return {'job_id':job_id,'epoch':factory.epoch,'count':len(swatches)}

def current_atlas(db,key):
    factory=get_factory(db,key)
    if not factory.active:raise HTTPException(410,'授权已撤回，该厂已生成的图谱全部失效')
    pub=db.scalar(select(AtlasPublication).where(AtlasPublication.factory_id==factory.id,AtlasPublication.epoch==factory.epoch).order_by(AtlasPublication.id.desc()))
    if not pub:raise HTTPException(404,'该厂当前授权期内尚未生成图谱')
    return {'factory_id':factory.id,'code':factory.code,'name':factory.name,'epoch':factory.epoch,'job_id':pub.job_id,'published_at':pub.created_at,'result':pub.result}

def publications(db,key):
    factory=get_factory(db,key)
    pubs=db.scalars(select(AtlasPublication).where(AtlasPublication.factory_id==factory.id).order_by(AtlasPublication.id.desc())).all()
    lots={s.id:s.lot for s in db.scalars(select(Swatch)).all()}
    return [{'id':p.id,'job_id':p.job_id,'epoch':p.epoch,'valid':bool(factory.active and p.epoch==factory.epoch),
             'created_at':p.created_at,'count':len(p.swatch_ids or []),
             'swatches':[{'id':sid,'lot':lots.get(sid,f'#{sid}')} for sid in (p.swatch_ids or [])]} for p in pubs]

def job_status(db,key,job_id):
    factory=get_factory(db,key)
    raw=queue.get('factory:atlas:job:'+job_id)
    if not raw:raise HTTPException(404,'图谱任务不存在或已过期')
    meta=json.loads(raw)
    if meta['factory_id']!=factory.id:raise HTTPException(404,'图谱任务不存在或已过期')
    if not factory.active or meta['epoch']!=factory.epoch:return {'state':'revoked','detail':'授权已撤回或更新，该任务已失效'}
    value=queue.get('factory:atlas:result:'+job_id)
    if not value:raise HTTPException(404,'图谱任务结果已过期')
    return json.loads(value)

def shared_current(db,factory):
    if not factory.active:raise HTTPException(403,'授权已撤回，图谱已失效，请联系厂内主管')
    pub=db.scalar(select(AtlasPublication).where(AtlasPublication.factory_id==factory.id,AtlasPublication.epoch==factory.epoch).order_by(AtlasPublication.id.desc()))
    if not pub:raise HTTPException(404,'当前授权期内尚未发布图谱，请联系厂内主管出图')
    r=pub.result
    return {'factory':factory.name,'code':factory.code,'epoch':pub.epoch,'published_at':pub.created_at,
            'explained_variance':r['explained_variance'],'reconstruction_mse':r['reconstruction_mse'],
            'count':r['count'],'method':r['method'],
            'points':[{'lot':p['lot'],'x':p['x'],'y':p['y']} for p in r['points']]}

def shared_job(db,factory,job_id):
    raw=queue.get('factory:atlas:job:'+job_id)
    if not raw:raise HTTPException(404,'任务不存在或已过期')
    meta=json.loads(raw)
    if meta['factory_id']!=factory.id:raise HTTPException(404,'任务不存在或已过期')
    if not factory.active or meta['epoch']!=factory.epoch:return {'state':'revoked','detail':'授权已撤回或更新，该任务已失效'}
    value=queue.get('factory:atlas:result:'+job_id)
    if not value:raise HTTPException(404,'任务结果已过期')
    payload=json.loads(value)
    if payload.get('state')=='done' and payload.get('result'):
        r=payload['result']
        payload['result']={'explained_variance':r['explained_variance'],'reconstruction_mse':r['reconstruction_mse'],
                           'count':r['count'],'method':r['method'],'points':[{'lot':p['lot'],'x':p['x'],'y':p['y']} for p in r['points']]}
    return payload
