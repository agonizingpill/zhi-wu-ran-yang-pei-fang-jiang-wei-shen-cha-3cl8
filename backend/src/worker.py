import os,time,json,traceback
from pathlib import Path
import redis
from sqlalchemy import select
from .database import Session
from .models import Swatch
from .atlas import calculate_atlas
from .sharing_models import PartnerFactory,FactoryGrant,AtlasPublication
queue=redis.Redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'),decode_responses=True)
ARTIFACTS=os.getenv('ARTIFACTS_DIR','/artifacts')
RESULT_TTL=86400

def set_result(key,payload):queue.set(key,json.dumps(payload),ex=RESULT_TTL)

def handle_internal(jobid):
    with Session() as db:
        swatches=db.scalars(select(Swatch).where(Swatch.measured==True)).all()
        result=calculate_atlas([{'id':s.id,'lot':s.lot,'recipe_id':s.recipe_id,'spectrum':s.spectrum} for s in swatches])
    Path(ARTIFACTS).mkdir(parents=True,exist_ok=True)
    Path(ARTIFACTS,f'{jobid}.json').write_text(json.dumps(result))
    set_result('atlas:result:'+jobid,{'state':'done','result':result})

def granted_swatches(db,factory_id):
    return db.scalars(select(Swatch).join(FactoryGrant,FactoryGrant.swatch_id==Swatch.id).where(FactoryGrant.factory_id==factory_id,Swatch.measured==True).order_by(Swatch.id)).all()

def handle_factory(jobid,factory_id,epoch):
    key='factory:atlas:result:'+jobid
    with Session() as db:
        factory=db.get(PartnerFactory,factory_id)
        if not factory or not factory.active or factory.epoch!=epoch:
            set_result(key,{'state':'revoked','error':'授权已撤回或更新，排队任务失效'});return
        samples=[{'id':s.id,'lot':s.lot,'recipe_id':s.recipe_id,'spectrum':s.spectrum} for s in granted_swatches(db,factory_id)]
    if len(samples)<3:
        set_result(key,{'state':'failed','error':f'该厂获准实测染样仅 {len(samples)} 张，PCA 至少需要 3 张'});return
    try:result=calculate_atlas(samples)
    except Exception as e:
        set_result(key,{'state':'failed','error':str(e)});return
    with Session() as db:
        fresh=db.scalar(select(PartnerFactory).where(PartnerFactory.id==factory_id).with_for_update())
        if not fresh or not fresh.active or fresh.epoch!=epoch:
            db.rollback();set_result(key,{'state':'revoked','error':'授权已撤回，计算结果不予发布'});return
        db.add(AtlasPublication(factory_id=factory_id,job_id=jobid,epoch=epoch,swatch_ids=[s['id'] for s in samples],result=result))
        db.commit()
    Path(ARTIFACTS).mkdir(parents=True,exist_ok=True)
    Path(ARTIFACTS,f'factory-{jobid}.json').write_text(json.dumps(result))
    set_result(key,{'state':'done','epoch':epoch,'result':result})

def process_one(job):
    key,raw=job
    if key=='factory:atlas:queue':
        payload=json.loads(raw)
        try:handle_factory(payload['job_id'],payload['factory_id'],payload['epoch'])
        except Exception as e:
            traceback.print_exc();set_result('factory:atlas:result:'+payload['job_id'],{'state':'failed','error':str(e)})
    else:
        try:handle_internal(raw)
        except Exception as e:
            traceback.print_exc();set_result('atlas:result:'+raw,{'state':'failed','error':str(e)})

def main():
    while True:
        Path('/tmp/worker-heartbeat').touch()
        job=queue.blpop(['atlas:queue','factory:atlas:queue'],timeout=3)
        if not job:continue
        process_one(job)

if __name__=='__main__':main()
