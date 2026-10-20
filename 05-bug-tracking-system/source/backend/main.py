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
DB_URL=os.getenv('DATABASE_URL',f'sqlite:///{ROOT / "bugs.db"}')
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
    issues:Mapped[list['Issue']]=relationship(back_populates='reporter',cascade='all, delete-orphan')
class Issue(Base):
    __tablename__='issues'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    title:Mapped[str]=mapped_column(String(160),index=True)
    description:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(20),default='open',index=True)
    priority:Mapped[str]=mapped_column(String(20),default='medium',index=True)
    module:Mapped[str]=mapped_column(String(80),default='General')
    assignee:Mapped[str]=mapped_column(String(80),default='Unassigned')
    reported_on:Mapped[date]=mapped_column(Date,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc))
    reporter_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    reporter:Mapped[User]=relationship(back_populates='issues')
@asynccontextmanager
async def lifespan(app:FastAPI):
    Base.metadata.create_all(engine)
    yield
app=FastAPI(title='Bugboard API',version='1.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5177','http://127.0.0.1:5177'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
def db_session():
    with SessionLocal() as db: yield db
class RegisterIn(BaseModel):
    name:str=Field(min_length=2,max_length=80)
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel): email:EmailStr; password:str
class UserOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; name:str; email:EmailStr
class AuthOut(BaseModel): access_token:str; token_type:str='bearer'; user:UserOut
class IssueIn(BaseModel):
    title:str=Field(min_length=4,max_length=160)
    description:str=Field(min_length=10,max_length=12000)
    status:str='open'
    priority:str='medium'
    module:str=Field(default='General',min_length=2,max_length=80)
    assignee:str=Field(default='Unassigned',min_length=2,max_length=80)
    reported_on:date
class IssueOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; title:str; description:str; status:str; priority:str; module:str; assignee:str; reported_on:date; created_at:datetime; updated_at:datetime
class IssueList(BaseModel): items:list[IssueOut]; total:int
def make_token(user): return jwt.encode({'sub':str(user.id),'exp':datetime.now(timezone.utc)+timedelta(days=14)},SECRET_KEY,algorithm='HS256')
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(db_session))->User:
    if credentials is None: raise HTTPException(401,'Please sign in to continue.')
    try: uid=int(jwt.decode(credentials.credentials,SECRET_KEY,algorithms=['HS256'])['sub'])
    except (jwt.InvalidTokenError,ValueError,KeyError): raise HTTPException(401,'Your session expired. Please sign in again.')
    user=db.get(User,uid)
    if user is None: raise HTTPException(401,'Account not found.')
    return user
def validate_issue(data:IssueIn):
    if data.status not in ('open','in_progress','resolved','closed'): raise HTTPException(422,'Choose a valid issue status.')
    if data.priority not in ('low','medium','high','critical'): raise HTTPException(422,'Choose a valid priority.')
@app.get('/api/health')
def health(): return {'status':'ok'}
@app.post('/api/auth/register',response_model=AuthOut,status_code=201)
def register(data:RegisterIn,db:Session=Depends(db_session)):
    email=str(data.email).lower()
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,'An account with that email already exists.')
    user=User(name=data.name.strip(),email=email,password_hash=passwords.hash(data.password)); db.add(user); db.commit(); db.refresh(user)
    return AuthOut(access_token=make_token(user),user=user)
@app.post('/api/auth/login',response_model=AuthOut)
def login(data:LoginIn,db:Session=Depends(db_session)):
    user=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if not user or not passwords.verify(data.password,user.password_hash): raise HTTPException(401,'Email or password is incorrect.')
    return AuthOut(access_token=make_token(user),user=user)
@app.get('/api/auth/me',response_model=UserOut)
def me(user:User=Depends(current_user)): return user
@app.get('/api/issues',response_model=IssueList)
def list_issues(search:str='',status_filter:str='',priority_filter:str='',user:User=Depends(current_user),db:Session=Depends(db_session)):
    query=select(Issue).where(Issue.reporter_id==user.id)
    if status_filter:
        if status_filter not in ('open','in_progress','resolved','closed'): raise HTTPException(422,'Invalid status filter.')
        query=query.where(Issue.status==status_filter)
    if priority_filter:
        if priority_filter not in ('low','medium','high','critical'): raise HTTPException(422,'Invalid priority filter.')
        query=query.where(Issue.priority==priority_filter)
    term=search.strip()
    if term: query=query.where(Issue.title.ilike(f'%{term}%')|Issue.description.ilike(f'%{term}%')|Issue.module.ilike(f'%{term}%')|Issue.assignee.ilike(f'%{term}%'))
    items=db.scalars(query.order_by(Issue.updated_at.desc(),Issue.id.desc())).all()
    return IssueList(items=items,total=len(items))
@app.post('/api/issues',response_model=IssueOut,status_code=201)
def create_issue(data:IssueIn,user:User=Depends(current_user),db:Session=Depends(db_session)):
    validate_issue(data)
    issue=Issue(**data.model_dump(),reporter_id=user.id)
    db.add(issue); db.commit(); db.refresh(issue)
    return issue
@app.put('/api/issues/{issue_id}',response_model=IssueOut)
def update_issue(issue_id:int,data:IssueIn,user:User=Depends(current_user),db:Session=Depends(db_session)):
    validate_issue(data)
    issue=db.scalar(select(Issue).where(Issue.id==issue_id,Issue.reporter_id==user.id))
    if issue is None: raise HTTPException(404,'Issue not found.')
    for key,value in data.model_dump().items(): setattr(issue,key,value)
    db.commit(); db.refresh(issue)
    return issue
@app.delete('/api/issues/{issue_id}',status_code=204)
def delete_issue(issue_id:int,user:User=Depends(current_user),db:Session=Depends(db_session)):
    issue=db.scalar(select(Issue).where(Issue.id==issue_id,Issue.reporter_id==user.id))
    if issue is None: raise HTTPException(404,'Issue not found.')
    db.delete(issue); db.commit()
    return Response(status_code=204)
