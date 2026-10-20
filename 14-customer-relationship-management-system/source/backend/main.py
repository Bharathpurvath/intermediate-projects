from datetime import datetime,timedelta,timezone
from pathlib import Path
import jwt
from dotenv import load_dotenv
from fastapi import Depends,FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel,ConfigDict,EmailStr,Field
from sqlalchemy import DateTime,ForeignKey,Integer,String,Text,create_engine,select
from sqlalchemy.orm import DeclarativeBase,Mapped,Session,mapped_column,sessionmaker
ROOT=Path(__file__).resolve().parent;load_dotenv(ROOT/'.env')
SECRET_KEY='local-crm-secret-change-before-deployment'
engine=create_engine(f"sqlite:///{ROOT/'crm.db'}",connect_args={'check_same_thread':False})
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False);passwords=PasswordHash.recommended();bearer=HTTPBearer(auto_error=False)
STAGES=['New lead','Contacted','Qualified','Proposal','Won','Lost']
class Base(DeclarativeBase):pass
class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(80))
    email:Mapped[str]=mapped_column(String(254),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
class Lead(Base):
    __tablename__='leads'
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    name:Mapped[str]=mapped_column(String(120))
    company:Mapped[str]=mapped_column(String(140),default='')
    email:Mapped[str]=mapped_column(String(254),default='')
    phone:Mapped[str]=mapped_column(String(50),default='')
    source:Mapped[str]=mapped_column(String(40),default='Other')
    value_cents:Mapped[int]=mapped_column(Integer,default=0)
    stage:Mapped[str]=mapped_column(String(20),default='New lead',index=True)
    follow_up:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True,index=True)
    notes:Mapped[str]=mapped_column(Text,default='')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc))
Base.metadata.create_all(engine)
class RegisterIn(BaseModel):name:str=Field(min_length=2,max_length=80);email:EmailStr;password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel):email:EmailStr;password:str
class UserOut(BaseModel):model_config=ConfigDict(from_attributes=True);id:int;name:str;email:EmailStr
class AuthOut(BaseModel):access_token:str;token_type:str='bearer';user:UserOut
class LeadIn(BaseModel):name:str=Field(min_length=2,max_length=120);company:str=Field(default='',max_length=140);email:EmailStr|None=None;phone:str=Field(default='',max_length=50);source:str=Field(default='Other',max_length=40);value_cents:int=Field(default=0,ge=0,le=100000000000);stage:str=Field(default='New lead');follow_up:datetime|None=None;notes:str=Field(default='',max_length=10000)
class StageIn(BaseModel):stage:str
class LeadOut(BaseModel):id:int;name:str;company:str;email:str;phone:str;source:str;value_cents:int;stage:str;follow_up:datetime|None;notes:str;created_at:datetime;updated_at:datetime
app=FastAPI(title='Fieldnotes CRM API',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:5186','http://localhost:5186'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
def db_session():
    with SessionLocal() as db:yield db
def utc(v):
    if v is None:return None
    return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
def token_for(u):return jwt.encode({'sub':str(u.id),'exp':datetime.now(timezone.utc)+timedelta(days=14)},SECRET_KEY,algorithm='HS256')
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(db_session)):
    if credentials is None:raise HTTPException(401,'Please sign in to continue.')
    try:uid=int(jwt.decode(credentials.credentials,SECRET_KEY,algorithms=['HS256'])['sub'])
    except(jwt.InvalidTokenError,ValueError,KeyError):raise HTTPException(401,'Your session expired. Please sign in again.')
    u=db.get(User,uid)
    if u is None:raise HTTPException(401,'Account not found.')
    return u
def owned(lead_id,user,db):
    lead=db.scalar(select(Lead).where(Lead.id==lead_id,Lead.user_id==user.id))
    if lead is None:raise HTTPException(404,'Lead not found.')
    return lead
def output(l):return LeadOut(id=l.id,name=l.name,company=l.company,email=l.email,phone=l.phone,source=l.source,value_cents=l.value_cents,stage=l.stage,follow_up=utc(l.follow_up),notes=l.notes,created_at=utc(l.created_at),updated_at=utc(l.updated_at))
def validate_stage(stage):
    if stage not in STAGES:raise HTTPException(422,'Choose a valid pipeline stage.')
@app.get('/api/health')
def health():return {'status':'ok'}
@app.get('/api/stages')
def stages():return STAGES
@app.post('/api/auth/register',response_model=AuthOut,status_code=201)
def register(data:RegisterIn,db:Session=Depends(db_session)):
    email=str(data.email).lower()
    if db.scalar(select(User.id).where(User.email==email)):raise HTTPException(409,'An account with this email already exists.')
    u=User(name=data.name.strip(),email=email,password_hash=passwords.hash(data.password));db.add(u);db.commit();db.refresh(u);return AuthOut(access_token=token_for(u),user=u)
@app.post('/api/auth/login',response_model=AuthOut)
def login(data:LoginIn,db:Session=Depends(db_session)):
    u=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if u is None or not passwords.verify(data.password,u.password_hash):raise HTTPException(401,'Email or password is incorrect.')
    return AuthOut(access_token=token_for(u),user=u)
@app.get('/api/auth/me',response_model=UserOut)
def me(user=Depends(current_user)):return user
@app.get('/api/leads',response_model=list[LeadOut])
def list_leads(q:str='',stage:str='all',user=Depends(current_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(Lead).where(Lead.user_id==user.id).order_by(Lead.updated_at.desc())).all()
    return [output(l) for l in rows if stage=='all' or l.stage==stage if q.casefold() in (l.name+' '+l.company+' '+l.email+' '+l.phone+' '+l.source).casefold()]
@app.post('/api/leads',response_model=LeadOut,status_code=201)
def create_lead(data:LeadIn,user=Depends(current_user),db:Session=Depends(db_session)):
    validate_stage(data.stage);email=str(data.email).lower() if data.email else ''
    if email and db.scalar(select(Lead.id).where(Lead.user_id==user.id,Lead.email==email)):raise HTTPException(409,'A lead with this email is already in your CRM.')
    l=Lead(user_id=user.id,name=data.name.strip(),company=data.company.strip(),email=email,phone=data.phone.strip(),source=data.source.strip() or 'Other',value_cents=data.value_cents,stage=data.stage,follow_up=utc(data.follow_up),notes=data.notes.strip());db.add(l);db.commit();db.refresh(l);return output(l)
@app.patch('/api/leads/{lead_id}',response_model=LeadOut)
def edit_lead(lead_id:int,data:LeadIn,user=Depends(current_user),db:Session=Depends(db_session)):
    validate_stage(data.stage);l=owned(lead_id,user,db);email=str(data.email).lower() if data.email else ''
    if email and db.scalar(select(Lead.id).where(Lead.user_id==user.id,Lead.email==email,Lead.id!=lead_id)):raise HTTPException(409,'A lead with this email is already in your CRM.')
    l.name=data.name.strip();l.company=data.company.strip();l.email=email;l.phone=data.phone.strip();l.source=data.source.strip() or 'Other';l.value_cents=data.value_cents;l.stage=data.stage;l.follow_up=utc(data.follow_up);l.notes=data.notes.strip();l.updated_at=datetime.now(timezone.utc);db.commit();db.refresh(l);return output(l)
@app.patch('/api/leads/{lead_id}/stage',response_model=LeadOut)
def change_stage(lead_id:int,data:StageIn,user=Depends(current_user),db:Session=Depends(db_session)):
    validate_stage(data.stage);l=owned(lead_id,user,db);l.stage=data.stage;l.updated_at=datetime.now(timezone.utc);db.commit();db.refresh(l);return output(l)
@app.delete('/api/leads/{lead_id}',status_code=204)
def delete_lead(lead_id:int,user=Depends(current_user),db:Session=Depends(db_session)):
    l=owned(lead_id,user,db);db.delete(l);db.commit();return None
@app.get('/api/summary')
def summary(user=Depends(current_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(Lead).where(Lead.user_id==user.id)).all();now=datetime.now(timezone.utc)
    counts={stage:sum(l.stage==stage for l in rows) for stage in STAGES}
    return {'leads':len(rows),'open_pipeline_cents':sum(l.value_cents for l in rows if l.stage not in ('Won','Lost')),'won_cents':sum(l.value_cents for l in rows if l.stage=='Won'),'overdue':sum(bool(l.follow_up and utc(l.follow_up)<now and l.stage not in ('Won','Lost')) for l in rows),'stage_counts':counts,'conversion':round(100*counts['Won']/len(rows)) if rows else 0}
@app.post('/api/demo',response_model=list[LeadOut])
def demo(user=Depends(current_user),db:Session=Depends(db_session)):
    if db.scalar(select(Lead.id).where(Lead.user_id==user.id).limit(1)):raise HTTPException(409,'Sample leads can only be added to an empty CRM.')
    now=datetime.now(timezone.utc);items=[('Maya Chen','Northstar Studio','maya@example.com','+91 90000 10001','Referral',480000,'Proposal',3,'Interested in a small brand and website refresh.'),('Arjun Rao','Fieldwork Coffee','arjun@example.com','+91 90000 10002','Website',225000,'Qualified',1,'Asked for an online menu and local search improvements.'),('Leena Das','Sunday Market','leena@example.com','+91 90000 10003','Event',125000,'Contacted',-2,'Met at the makers market. Send the product catalog.'),('Kabir Nair','Moss & Thread','kabir@example.com','+91 90000 10004','Social',76000,'New lead',4,'Looking for a simple store landing page.'),('Tara Iyer','Paper Habit','tara@example.com','+91 90000 10005','Referral',86000,'Won',-5,'Starter project approved. Kickoff scheduled.'),('Dev Mehta','Open Bench','dev@example.com','+91 90000 10006','Cold outreach',310000,'Lost',-7,'Budget paused until next quarter.')]
    out=[]
    for name,company,email,phone,source,value,stage,delta,notes in items:
        l=Lead(user_id=user.id,name=name,company=company,email=email,phone=phone,source=source,value_cents=value,stage=stage,follow_up=now+timedelta(days=delta),notes=notes);db.add(l);out.append(l)
    db.commit()
    for l in out:db.refresh(l)
    return [output(x) for x in out]
