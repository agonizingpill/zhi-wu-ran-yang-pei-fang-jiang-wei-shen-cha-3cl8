from sqlalchemy import String,Integer,Boolean,ForeignKey,JSON,DateTime,func,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class PartnerFactory(Base):
    __tablename__='partner_factories'
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(40),unique=True)
    name:Mapped[str]=mapped_column(String(100))
    token:Mapped[str]=mapped_column(String(80),unique=True)
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    epoch:Mapped[int]=mapped_column(Integer,default=1)
    created_at:Mapped[object]=mapped_column(DateTime,server_default=func.now())
class FactoryGrant(Base):
    __tablename__='factory_grants'
    __table_args__=(UniqueConstraint('factory_id','swatch_id'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    factory_id:Mapped[int]=mapped_column(ForeignKey('partner_factories.id'))
    swatch_id:Mapped[int]=mapped_column(ForeignKey('swatches.id'))
    granted_by:Mapped[str]=mapped_column(String(120))
    created_at:Mapped[object]=mapped_column(DateTime,server_default=func.now())
class AtlasPublication(Base):
    __tablename__='atlas_publications'
    id:Mapped[int]=mapped_column(primary_key=True)
    factory_id:Mapped[int]=mapped_column(ForeignKey('partner_factories.id'))
    job_id:Mapped[str]=mapped_column(String(40),unique=True)
    epoch:Mapped[int]=mapped_column(Integer)
    swatch_ids:Mapped[list]=mapped_column(JSON)
    result:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[object]=mapped_column(DateTime,server_default=func.now())
