import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env')
SECRET_KEY=os.getenv('SECRET_KEY','change-before-deployment')
DB_URL=os.getenv('DATABASE_URL',f'sqlite:///{ROOT / "applications.db"}')
engine=create_engine(DB_URL,connect_args={'check_same_thread':False} if DB_URL.startswith('sqlite') else {})
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)
passwords=PasswordHash.recommended()
bearer=HTTPBearer(auto_error=False)
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    name:Mapped[str]=mapped_column(String(80))
    email:Mapped[str]=mapped_column(String(254),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    applications:Mapped[list['Application']]=relationship(back_populates='user',cascade='all, delete-orphan')
class Application(Base):
    __tablename__='applications'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    company:Mapped[str]=mapped_column(String(120),index=True)
    role:Mapped[str]=mapped_column(String(120),index=True)
    status:Mapped[str]=mapped_column(String(20),default='saved',index=True)
    location:Mapped[str]=mapped_column(String(120),default='')
    work_mode:Mapped[str]=mapped_column(String(20),default='On-site')
    salary:Mapped[str]=mapped_column(String(80),default='')
    job_url:Mapped[str]=mapped_column(String(500),default='')
    notes:Mapped[str]=mapped_column(Text,default='')
    applied_on:Mapped[date]=mapped_column(Date,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc))
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    user:Mapped[User]=relationship(back_populates='applications')
@asynccontextmanager
async def lifespan(app:FastAPI):
    Base.metadata.create_all(engine)
    yield
app=FastAPI(title='Next Chapter API',version='1.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5176','http://127.0.0.1:5176'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
def db_session():
    with SessionLocal() as db: yield db
class RegisterIn(BaseModel):
    name:str=Field(min_length=2,max_length=80)
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel):
    email:EmailStr
    password:str
class UserOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int
    name:str
    email:EmailStr
class AuthOut(BaseModel):
    access_token:str
    token_type:str='bearer'
    user:UserOut
class ApplicationIn(BaseModel):
    company:str=Field(min_length=2,max_length=120)
    role:str=Field(min_length=2,max_length=120)
    status:str='saved'
    location:str=Field(default='',max_length=120)
    work_mode:str=Field(default='On-site',max_length=20)
    salary:str=Field(default='',max_length=80)
    job_url:str=Field(default='',max_length=500)
    notes:str=Field(default='',max_length=10000)
    applied_on:date
class ApplicationOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int
    company:str
    role:str
    status:str
    location:str
    work_mode:str
    salary:str
    job_url:str
    notes:str
    applied_on:date
    created_at:datetime
    updated_at:datetime
class ApplicationsOut(BaseModel):
    items:list[ApplicationOut]
    total:int
def issue_token(user):
    return jwt.encode({'sub':str(user.id),'exp':datetime.now(timezone.utc)+timedelta(days=14)},SECRET_KEY,algorithm='HS256')
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(db_session))->User:
    if credentials is None: raise HTTPException(401,'Please sign in to continue.')
    try:
        uid=int(jwt.decode(credentials.credentials,SECRET_KEY,algorithms=['HS256'])['sub'])
    except (jwt.InvalidTokenError,ValueError,KeyError):
        raise HTTPException(401,'Your session expired. Please sign in again.')
    user=db.get(User,uid)
    if user is None: raise HTTPException(401,'Account not found.')
    return user
def valid(data:ApplicationIn):
    if data.status not in ('saved','applied','interviewing','offer','rejected'):
        raise HTTPException(422,'Choose a valid application status.')
    if data.work_mode not in ('On-site','Hybrid','Remote'):
        raise HTTPException(422,'Choose a valid work arrangement.')
    if data.job_url and not data.job_url.startswith(('https://','http://')):
        raise HTTPException(422,'Job link must start with http:// or https://.')
@app.get('/api/health')
def health(): return {'status':'ok'}
@app.post('/api/auth/register',response_model=AuthOut,status_code=201)
def register(data:RegisterIn,db:Session=Depends(db_session)):
    email=str(data.email).lower()
    if db.scalar(select(User).where(User.email==email)):
        raise HTTPException(409,'An account with that email already exists.')
    user=User(name=data.name.strip(),email=email,password_hash=passwords.hash(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return AuthOut(access_token=issue_token(user),user=user)
@app.post('/api/auth/login',response_model=AuthOut)
def login(data:LoginIn,db:Session=Depends(db_session)):
    user=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if not user or not passwords.verify(data.password,user.password_hash):
        raise HTTPException(401,'Email or password is incorrect.')
    return AuthOut(access_token=issue_token(user),user=user)
@app.get('/api/auth/me',response_model=UserOut)
def me(user:User=Depends(current_user)): return user
@app.get('/api/applications',response_model=ApplicationsOut)
def list_applications(search:str='',status_filter:str='',user:User=Depends(current_user),db:Session=Depends(db_session)):
    query=select(Application).where(Application.user_id==user.id)
    if status_filter:
        if status_filter not in ('saved','applied','interviewing','offer','rejected'):
            raise HTTPException(422,'Invalid status filter.')
        query=query.where(Application.status==status_filter)
    term=search.strip()
    if term:
        query=query.where(Application.company.ilike(f'%{term}%')|Application.role.ilike(f'%{term}%')|Application.location.ilike(f'%{term}%'))
    items=db.scalars(query.order_by(Application.updated_at.desc(),Application.id.desc())).all()
    return ApplicationsOut(items=items,total=len(items))
@app.post('/api/applications',response_model=ApplicationOut,status_code=201)
def create_application(data:ApplicationIn,user:User=Depends(current_user),db:Session=Depends(db_session)):
    valid(data)
    item=Application(**data.model_dump(),user_id=user.id)
    db.add(item); db.commit(); db.refresh(item)
    return item
@app.put('/api/applications/{application_id}',response_model=ApplicationOut)
def update_application(application_id:int,data:ApplicationIn,user:User=Depends(current_user),db:Session=Depends(db_session)):
    valid(data)
    item=db.scalar(select(Application).where(Application.id==application_id,Application.user_id==user.id))
    if item is None: raise HTTPException(404,'Application not found.')
    for key,value in data.model_dump().items(): setattr(item,key,value)
    db.commit(); db.refresh(item)
    return item
@app.delete('/api/applications/{application_id}',status_code=204)
def delete_application(application_id:int,user:User=Depends(current_user),db:Session=Depends(db_session)):
    item=db.scalar(select(Application).where(Application.id==application_id,Application.user_id==user.id))
    if item is None: raise HTTPException(404,'Application not found.')
    db.delete(item); db.commit()
    return Response(status_code=204)
