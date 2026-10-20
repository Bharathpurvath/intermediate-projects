import os
import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl
from sqlalchemy import DateTime, ForeignKey, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker, selectinload

ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env')
SECRET_KEY=os.getenv('SECRET_KEY','local-development-secret-change-before-deployment')
engine=create_engine(f"sqlite:///{ROOT / 'links.db'}",connect_args={'check_same_thread':False})
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)
passwords=PasswordHash.recommended(); bearer=HTTPBearer(auto_error=False)
ALPHABET=string.ascii_letters+string.digits
CODE_RE=re.compile(r'^[A-Za-z0-9-]{3,30}$')
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(80))
    email:Mapped[str]=mapped_column(String(254),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
class ShortLink(Base):
    __tablename__='short_links'
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    code:Mapped[str]=mapped_column(String(30),unique=True,index=True)
    destination:Mapped[str]=mapped_column(String(2048))
    title:Mapped[str]=mapped_column(String(120),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    clicks:Mapped[list['LinkClick']]=relationship(back_populates='link',cascade='all, delete-orphan',lazy='selectin')
class LinkClick(Base):
    __tablename__='link_clicks'
    id:Mapped[int]=mapped_column(primary_key=True)
    link_id:Mapped[int]=mapped_column(ForeignKey('short_links.id',ondelete='CASCADE'),index=True)
    clicked_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),index=True)
    link:Mapped[ShortLink]=relationship(back_populates='clicks')
Base.metadata.create_all(engine)
class RegisterIn(BaseModel):
    name:str=Field(min_length=2,max_length=80)
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel): email:EmailStr; password:str
class UserOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; name:str; email:EmailStr
class AuthOut(BaseModel): access_token:str; token_type:str='bearer'; user:UserOut
class LinkIn(BaseModel):
    url:HttpUrl
    title:str=Field(default='',max_length=120)
    custom_code:str|None=Field(default=None,max_length=30)
    expires_at:datetime|None=None
class LinkOut(BaseModel):
    id:int; code:str; short_url:str; destination:str; title:str; clicks:int; created_at:datetime; expires_at:datetime|None; is_expired:bool
app=FastAPI(title='Little Link API',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:5182','http://localhost:5182'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
def db_session():
    with SessionLocal() as db: yield db
def make_token(user):return jwt.encode({'sub':str(user.id),'exp':datetime.now(timezone.utc)+timedelta(days=14)},SECRET_KEY,algorithm='HS256')
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(db_session)):
    if credentials is None:raise HTTPException(401,'Please sign in to continue.')
    try:uid=int(jwt.decode(credentials.credentials,SECRET_KEY,algorithms=['HS256'])['sub'])
    except(jwt.InvalidTokenError,ValueError,KeyError):raise HTTPException(401,'Your session expired. Please sign in again.')
    user=db.get(User,uid)
    if user is None:raise HTTPException(401,'Account not found.')
    return user
def utc(dt):return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt.astimezone(timezone.utc) if dt else None
def expired(link):return bool(link.expires_at and utc(link.expires_at)<=datetime.now(timezone.utc))
def short_url(code):return f'http://127.0.0.1:8009/r/{code}'
def link_out(link):return LinkOut(id=link.id,code=link.code,short_url=short_url(link.code),destination=link.destination,title=link.title,clicks=len(link.clicks),created_at=utc(link.created_at),expires_at=utc(link.expires_at),is_expired=expired(link))
@app.get('/api/health')
def health():return {'status':'ok'}
@app.post('/api/auth/register',response_model=AuthOut,status_code=201)
def register(data:RegisterIn,db:Session=Depends(db_session)):
    email=str(data.email).lower()
    if db.scalar(select(User).where(User.email==email)):raise HTTPException(409,'An account with this email already exists.')
    user=User(name=data.name.strip(),email=email,password_hash=passwords.hash(data.password));db.add(user);db.commit();db.refresh(user)
    return AuthOut(access_token=make_token(user),user=user)
@app.post('/api/auth/login',response_model=AuthOut)
def login(data:LoginIn,db:Session=Depends(db_session)):
    user=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if user is None or not passwords.verify(data.password,user.password_hash):raise HTTPException(401,'Email or password is incorrect.')
    return AuthOut(access_token=make_token(user),user=user)
@app.get('/api/auth/me',response_model=UserOut)
def me(user=Depends(current_user)):return user
@app.get('/api/links',response_model=list[LinkOut])
def list_links(user=Depends(current_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(ShortLink).where(ShortLink.user_id==user.id).options(selectinload(ShortLink.clicks)).order_by(ShortLink.created_at.desc())).all()
    return [link_out(x) for x in rows]
@app.post('/api/links',response_model=LinkOut,status_code=201)
def create_link(data:LinkIn,user=Depends(current_user),db:Session=Depends(db_session)):
    dest=str(data.url)
    if len(dest)>2048:raise HTTPException(422,'The destination URL is too long.')
    parsed=urlparse(dest)
    if parsed.scheme not in ('http','https') or not parsed.hostname:raise HTTPException(422,'Only valid http:// and https:// destinations are supported.')
    code=data.custom_code.strip() if data.custom_code else ''
    if code and not CODE_RE.fullmatch(code):raise HTTPException(422,'Custom codes need 3–30 letters, numbers, or hyphens.')
    if data.expires_at and utc(data.expires_at)<=datetime.now(timezone.utc):raise HTTPException(422,'Choose an expiration time in the future.')
    if code and db.scalar(select(ShortLink.id).where(ShortLink.code==code)):raise HTTPException(409,'That custom code is already in use. Try another.')
    if not code:
        for _ in range(10):
            candidate=''.join(secrets.choice(ALPHABET) for _ in range(7))
            if not db.scalar(select(ShortLink.id).where(ShortLink.code==candidate)):
                code=candidate;break
        if not code:raise HTTPException(503,'Could not reserve a short code. Please try again.')
    link=ShortLink(user_id=user.id,code=code,destination=dest,title=data.title.strip(),expires_at=utc(data.expires_at))
    db.add(link)
    try:db.commit();db.refresh(link)
    except Exception:db.rollback();raise HTTPException(409,'That short code was just taken. Please try another.')
    return link_out(link)
@app.delete('/api/links/{link_id}',status_code=204)
def delete_link(link_id:int,user=Depends(current_user),db:Session=Depends(db_session)):
    link=db.scalar(select(ShortLink).where(ShortLink.id==link_id,ShortLink.user_id==user.id))
    if link is None:raise HTTPException(404,'Link not found.')
    db.delete(link);db.commit();return None
@app.get('/api/stats')
def stats(user=Depends(current_user),db:Session=Depends(db_session)):
    links=db.scalars(select(ShortLink).where(ShortLink.user_id==user.id).options(selectinload(ShortLink.clicks))).all()
    cutoff=datetime.now(timezone.utc)-timedelta(days=6)
    clicks=[c for link in links for c in link.clicks if utc(c.clicked_at)>=cutoff]
    days=[]
    for offset in reversed(range(7)):
        day=(datetime.now(timezone.utc)-timedelta(days=offset)).date()
        days.append({'date':day.isoformat(),'count':sum(1 for c in clicks if utc(c.clicked_at).date()==day)})
    return {'links':len(links),'clicks':sum(len(l.clicks) for l in links),'active':sum(not expired(l) for l in links),'last_seven_days':days}
@app.get('/r/{code}')
def redirect_short(code:str,db:Session=Depends(db_session)):
    link=db.scalar(select(ShortLink).where(ShortLink.code==code).options(selectinload(ShortLink.clicks)))
    if link is None:raise HTTPException(404,'This short link could not be found.')
    if expired(link):raise HTTPException(410,'This short link has expired.')
    link.clicks.append(LinkClick());db.commit()
    return RedirectResponse(link.destination,status_code=307)
