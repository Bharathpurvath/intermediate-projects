import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, create_engine, or_, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker, selectinload

ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env')
SECRET_KEY=os.getenv('SECRET_KEY','local-chat-secret-change-before-deployment')
engine=create_engine(f"sqlite:///{ROOT / 'chat.db'}",connect_args={'check_same_thread':False})
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)
passwords=PasswordHash.recommended();bearer=HTTPBearer(auto_error=False)
class Base(DeclarativeBase):pass
class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(80))
    email:Mapped[str]=mapped_column(String(254),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Conversation(Base):
    __tablename__='conversations'
    __table_args__=(UniqueConstraint('user_one_id','user_two_id',name='uq_direct_pair'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    user_one_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    user_two_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    messages:Mapped[list['Message']]=relationship(back_populates='conversation',cascade='all, delete-orphan',lazy='selectin',order_by='Message.created_at')
class Message(Base):
    __tablename__='messages'
    id:Mapped[int]=mapped_column(primary_key=True)
    conversation_id:Mapped[int]=mapped_column(ForeignKey('conversations.id',ondelete='CASCADE'),index=True)
    sender_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    content:Mapped[str]=mapped_column(String(4000))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),index=True)
    conversation:Mapped[Conversation]=relationship(back_populates='messages')
    sender:Mapped[User]=relationship()
Base.metadata.create_all(engine)
class RegisterIn(BaseModel):name:str=Field(min_length=2,max_length=80);email:EmailStr;password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel):email:EmailStr;password:str
class UserOut(BaseModel):model_config=ConfigDict(from_attributes=True);id:int;name:str;email:EmailStr
class AuthOut(BaseModel):access_token:str;token_type:str='bearer';user:UserOut
class ConversationOut(BaseModel):id:int;other_user:UserOut;last_message:str|None;updated_at:datetime;online:bool
class MessageOut(BaseModel):id:int;conversation_id:int;sender_id:int;sender_name:str;content:str;created_at:datetime
app=FastAPI(title='Goodtalk Chat API',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:5183','http://localhost:5183'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
def db_session():
    with SessionLocal() as db:yield db
def issue_token(user):return jwt.encode({'sub':str(user.id),'exp':datetime.now(timezone.utc)+timedelta(days=14)},SECRET_KEY,algorithm='HS256')
def user_from_token(raw,db):
    try:uid=int(jwt.decode(raw,SECRET_KEY,algorithms=['HS256'])['sub'])
    except(jwt.InvalidTokenError,ValueError,KeyError):return None
    return db.get(User,uid)
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(db_session)):
    if credentials is None:raise HTTPException(401,'Please sign in to continue.')
    user=user_from_token(credentials.credentials,db)
    if user is None:raise HTTPException(401,'Your session expired. Please sign in again.')
    return user
class SocketHub:
    def __init__(self):self.sockets:dict[int,set[WebSocket]]={}
    async def connect(self,user_id,socket):
        await socket.accept();self.sockets.setdefault(user_id,set()).add(socket)
    def disconnect(self,user_id,socket):
        group=self.sockets.get(user_id)
        if group:
            group.discard(socket)
            if not group:self.sockets.pop(user_id,None)
    def online(self,user_id):return bool(self.sockets.get(user_id))
    async def send_user(self,user_id,payload):
        for socket in list(self.sockets.get(user_id,set())):
            try:await socket.send_json(payload)
            except Exception:self.disconnect(user_id,socket)
hub=SocketHub()
def utc(v):return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
def get_conversation(conversation_id,user,db):
    row=db.scalar(select(Conversation).where(Conversation.id==conversation_id,or_(Conversation.user_one_id==user.id,Conversation.user_two_id==user.id)))
    if row is None:raise HTTPException(404,'Conversation not found.')
    return row
def conversation_json(c,user,db):
    other_id=c.user_two_id if c.user_one_id==user.id else c.user_one_id
    other=db.get(User,other_id)
    last=db.scalar(select(Message).where(Message.conversation_id==c.id).order_by(Message.created_at.desc(),Message.id.desc()).limit(1))
    return ConversationOut(id=c.id,other_user=other,last_message=last.content if last else None,updated_at=utc(last.created_at if last else c.created_at),online=hub.online(other_id))
def message_json(m,db):
    sender=db.get(User,m.sender_id)
    return {'id':m.id,'conversation_id':m.conversation_id,'sender_id':m.sender_id,'sender_name':sender.name,'content':m.content,'created_at':utc(m.created_at).isoformat()}
@app.get('/api/health')
def health():return {'status':'ok'}
@app.post('/api/auth/register',response_model=AuthOut,status_code=201)
def register(data:RegisterIn,db:Session=Depends(db_session)):
    email=str(data.email).lower()
    if db.scalar(select(User).where(User.email==email)):raise HTTPException(409,'An account with this email already exists.')
    user=User(name=data.name.strip(),email=email,password_hash=passwords.hash(data.password));db.add(user);db.commit();db.refresh(user)
    return AuthOut(access_token=issue_token(user),user=user)
@app.post('/api/auth/login',response_model=AuthOut)
def login(data:LoginIn,db:Session=Depends(db_session)):
    user=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if user is None or not passwords.verify(data.password,user.password_hash):raise HTTPException(401,'Email or password is incorrect.')
    return AuthOut(access_token=issue_token(user),user=user)
@app.get('/api/auth/me',response_model=UserOut)
def me(user=Depends(current_user)):return user
@app.get('/api/contacts',response_model=list[UserOut])
def contacts(user=Depends(current_user),db:Session=Depends(db_session)):
    return db.scalars(select(User).where(User.id!=user.id).order_by(User.name)).all()
@app.get('/api/conversations',response_model=list[ConversationOut])
def conversations(user=Depends(current_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(Conversation).where(or_(Conversation.user_one_id==user.id,Conversation.user_two_id==user.id))).all()
    return sorted([conversation_json(c,user,db) for c in rows],key=lambda x:x.updated_at,reverse=True)
@app.post('/api/conversations/{other_user_id}',response_model=ConversationOut)
def open_conversation(other_user_id:int,user=Depends(current_user),db:Session=Depends(db_session)):
    if other_user_id==user.id:raise HTTPException(400,'Choose another member to start a conversation.')
    if db.get(User,other_user_id) is None:raise HTTPException(404,'Member not found.')
    a,b=sorted((user.id,other_user_id))
    row=db.scalar(select(Conversation).where(Conversation.user_one_id==a,Conversation.user_two_id==b))
    if row is None:
        row=Conversation(user_one_id=a,user_two_id=b);db.add(row);db.commit();db.refresh(row)
    return conversation_json(row,user,db)
@app.get('/api/conversations/{conversation_id}/messages',response_model=list[MessageOut])
def history(conversation_id:int,limit:int=100,user=Depends(current_user),db:Session=Depends(db_session)):
    get_conversation(conversation_id,user,db)
    rows=db.scalars(select(Message).where(Message.conversation_id==conversation_id).options(selectinload(Message.sender)).order_by(Message.created_at.desc(),Message.id.desc()).limit(max(1,min(limit,200)))).all()
    return [MessageOut(id=m.id,conversation_id=m.conversation_id,sender_id=m.sender_id,sender_name=m.sender.name,content=m.content,created_at=utc(m.created_at)) for m in reversed(rows)]
@app.websocket('/api/ws')
async def websocket_chat(socket:WebSocket,token:str=''):
    with SessionLocal() as db:user=user_from_token(token,db)
    if user is None:
        await socket.close(code=4401);return
    user_id=user.id
    await hub.connect(user_id,socket)
    try:
        for connected_id in list(hub.sockets):await hub.send_user(connected_id,{'type':'presence','user_id':user_id,'online':True})
        while True:
            data=await socket.receive_json()
            kind=data.get('type')
            if kind=='typing':
                with SessionLocal() as db:
                    c=db.get(Conversation,int(data.get('conversation_id',0)))
                    if c and user_id in (c.user_one_id,c.user_two_id):
                        other=c.user_two_id if c.user_one_id==user_id else c.user_one_id
                if c and user_id in (c.user_one_id,c.user_two_id):await hub.send_user(other,{'type':'typing','conversation_id':c.id,'user_id':user_id,'name':user.name})
            elif kind=='message':
                content=str(data.get('content','')).strip();conversation_id=int(data.get('conversation_id',0))
                if not content:continue
                if len(content)>4000:await socket.send_json({'type':'error','message':'Messages must be 4,000 characters or less.'});continue
                with SessionLocal() as db:
                    c=db.scalar(select(Conversation).where(Conversation.id==conversation_id,or_(Conversation.user_one_id==user_id,Conversation.user_two_id==user_id)))
                    if c is None:await socket.send_json({'type':'error','message':'Conversation not found.'});continue
                    msg=Message(conversation_id=c.id,sender_id=user_id,content=content);db.add(msg);db.commit();db.refresh(msg)
                    payload=message_json(msg,db);other=c.user_two_id if c.user_one_id==user_id else c.user_one_id
                event={'type':'message','message':payload}
                await hub.send_user(user_id,event);await hub.send_user(other,event)
    except WebSocketDisconnect:pass
    except Exception:
        try:await socket.close(code=1011)
        except Exception:pass
    finally:
        hub.disconnect(user_id,socket)
        for connected_id in list(hub.sockets):await hub.send_user(connected_id,{'type':'presence','user_id':user_id,'online':hub.online(user_id)})
