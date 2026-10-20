import os
from datetime import datetime,timedelta,timezone
from pathlib import Path
import jwt
from dotenv import load_dotenv
from fastapi import Depends,FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel,ConfigDict,EmailStr,Field
from sqlalchemy import DateTime,ForeignKey,Integer,String,create_engine,or_,select,update
from sqlalchemy.orm import DeclarativeBase,Mapped,Session,mapped_column,relationship,sessionmaker
ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env')
SECRET_KEY=os.getenv('SECRET_KEY','local-booking-secret-change-before-deployment')
engine=create_engine(f"sqlite:///{ROOT / 'appointments.db'}",connect_args={'check_same_thread':False})
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)
passwords=PasswordHash.recommended();bearer=HTTPBearer(auto_error=False)
class Base(DeclarativeBase):pass
class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(80))
    email:Mapped[str]=mapped_column(String(254),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
class Slot(Base):
    __tablename__='slots'
    id:Mapped[int]=mapped_column(primary_key=True)
    host_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    booked_by_id:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True,index=True)
    title:Mapped[str]=mapped_column(String(120))
    starts_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    ends_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    status:Mapped[str]=mapped_column(String(20),default='open',index=True)
    host:Mapped[User]=relationship(foreign_keys=[host_id])
    guest:Mapped[User|None]=relationship(foreign_keys=[booked_by_id])
Base.metadata.create_all(engine)
class RegisterIn(BaseModel):name:str=Field(min_length=2,max_length=80);email:EmailStr;password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel):email:EmailStr;password:str
class UserOut(BaseModel):model_config=ConfigDict(from_attributes=True);id:int;name:str;email:EmailStr
class AuthOut(BaseModel):access_token:str;token_type:str='bearer';user:UserOut
class SlotIn(BaseModel):title:str=Field(min_length=3,max_length=120);starts_at:datetime;duration_minutes:int=Field(ge=15,le=240)
class SlotOut(BaseModel):id:int;host_id:int;host_name:str;booked_by_id:int|None;guest_name:str|None;title:str;starts_at:datetime;ends_at:datetime;status:str
app=FastAPI(title='Meetwell Appointment API',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:5184','http://localhost:5184'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
def db_session():
    with SessionLocal() as db:yield db
def utc(v):return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
def auth_token(user):return jwt.encode({'sub':str(user.id),'exp':datetime.now(timezone.utc)+timedelta(days=14)},SECRET_KEY,algorithm='HS256')
def token_user(raw,db):
    try:uid=int(jwt.decode(raw,SECRET_KEY,algorithms=['HS256'])['sub'])
    except(jwt.InvalidTokenError,ValueError,KeyError):return None
    return db.get(User,uid)
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(db_session)):
    if credentials is None:raise HTTPException(401,'Please sign in to continue.')
    user=token_user(credentials.credentials,db)
    if user is None:raise HTTPException(401,'Your session expired. Please sign in again.')
    return user
def slot_out(s):return SlotOut(id=s.id,host_id=s.host_id,host_name=s.host.name,booked_by_id=s.booked_by_id,guest_name=s.guest.name if s.guest else None,title=s.title,starts_at=utc(s.starts_at),ends_at=utc(s.ends_at),status=s.status)
@app.get('/api/health')
def health():return {'status':'ok'}
@app.post('/api/auth/register',response_model=AuthOut,status_code=201)
def register(data:RegisterIn,db:Session=Depends(db_session)):
    email=str(data.email).lower()
    if db.scalar(select(User).where(User.email==email)):raise HTTPException(409,'An account with this email already exists.')
    u=User(name=data.name.strip(),email=email,password_hash=passwords.hash(data.password));db.add(u);db.commit();db.refresh(u)
    return AuthOut(access_token=auth_token(u),user=u)
@app.post('/api/auth/login',response_model=AuthOut)
def login(data:LoginIn,db:Session=Depends(db_session)):
    u=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if u is None or not passwords.verify(data.password,u.password_hash):raise HTTPException(401,'Email or password is incorrect.')
    return AuthOut(access_token=auth_token(u),user=u)
@app.get('/api/auth/me',response_model=UserOut)
def me(user=Depends(current_user)):return user
@app.post('/api/slots',response_model=SlotOut,status_code=201)
def create_slot(data:SlotIn,user=Depends(current_user),db:Session=Depends(db_session)):
    start=utc(data.starts_at);end=start+timedelta(minutes=data.duration_minutes);now=datetime.now(timezone.utc)
    if start<=now:raise HTTPException(422,'Choose a start time in the future.')
    if start>now+timedelta(days=365):raise HTTPException(422,'Appointments can be scheduled up to one year ahead.')
    existing=db.scalar(select(Slot.id).where(Slot.host_id==user.id,Slot.status.in_(['open','booked']),Slot.starts_at<end,Slot.ends_at>start).limit(1))
    if existing:raise HTTPException(409,'That time overlaps another slot in your calendar.')
    slot=Slot(host_id=user.id,title=data.title.strip(),starts_at=start,ends_at=end,status='open');db.add(slot);db.commit();db.refresh(slot)
    return slot_out(slot)
@app.get('/api/slots',response_model=list[SlotOut])
def available_slots(user=Depends(current_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(Slot).where(Slot.status=='open',Slot.host_id!=user.id,Slot.starts_at>datetime.now(timezone.utc)).order_by(Slot.starts_at).limit(200)).all()
    return [slot_out(x) for x in rows]
@app.get('/api/appointments',response_model=list[SlotOut])
def my_appointments(user=Depends(current_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(Slot).where(or_(Slot.host_id==user.id,Slot.booked_by_id==user.id)).order_by(Slot.starts_at)).all()
    return [slot_out(x) for x in rows]
@app.post('/api/slots/{slot_id}/book',response_model=SlotOut)
def book_slot(slot_id:int,user=Depends(current_user),db:Session=Depends(db_session)):
    slot=db.get(Slot,slot_id)
    if slot is None:raise HTTPException(404,'That time is no longer available.')
    if slot.host_id==user.id:raise HTTPException(400,'You cannot book your own availability.')
    if slot.status!='open' or utc(slot.starts_at)<=datetime.now(timezone.utc):raise HTTPException(409,'That time has just been booked or has passed. Refresh and choose another.')
    clash=db.scalar(select(Slot.id).where(Slot.booked_by_id==user.id,Slot.status=='booked',Slot.starts_at<slot.ends_at,Slot.ends_at>slot.starts_at).limit(1))
    if clash:raise HTTPException(409,'This overlaps one of your existing appointments.')
    result=db.execute(update(Slot).where(Slot.id==slot_id,Slot.status=='open').values(status='booked',booked_by_id=user.id))
    if result.rowcount!=1:db.rollback();raise HTTPException(409,'Someone else just booked that time. Refresh to see current availability.')
    db.commit();db.expire_all();return slot_out(db.get(Slot,slot_id))
@app.post('/api/appointments/{slot_id}/cancel',response_model=SlotOut)
def cancel_appointment(slot_id:int,user=Depends(current_user),db:Session=Depends(db_session)):
    slot=db.get(Slot,slot_id)
    if slot is None:raise HTTPException(404,'Appointment not found.')
    if slot.status not in ('open','booked'):raise HTTPException(409,'This appointment has already been cancelled.')
    if utc(slot.starts_at)<=datetime.now(timezone.utc):raise HTTPException(409,'Past appointments cannot be changed.')
    if slot.host_id==user.id:slot.status='cancelled';slot.booked_by_id=None
    elif slot.booked_by_id==user.id:slot.status='open';slot.booked_by_id=None
    else:raise HTTPException(403,'You are not part of this appointment.')
    db.commit();db.refresh(slot);return slot_out(slot)
