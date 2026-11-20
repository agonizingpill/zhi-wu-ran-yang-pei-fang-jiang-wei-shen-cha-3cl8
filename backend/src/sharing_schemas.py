from pydantic import BaseModel,Field
class FactoryInput(BaseModel):
    code:str=Field(min_length=1,max_length=40)
    name:str=Field(min_length=1,max_length=100)
class GrantInput(BaseModel):
    swatch_ids:list[int]=Field(min_length=1,max_length=500)
