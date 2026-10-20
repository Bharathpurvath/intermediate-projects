import os
from contextlib import asynccontextmanager
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import jwt
from dotenv import load_dotenv
from fastapi import Depends,FastAPI,HTTPException,Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel,ConfigDict,EmailStr,Field
from sqlalchemy import Date,DateTime,ForeignKey,Integer,String,Text,create_engine,or_,select
from sqlalchemy.orm import DeclarativeBase,Mapped,Session,mapped_column,relationship,sessionmaker
ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env')
SECRET_KEY=os.getenv('SECRET_KEY','change-before-deployment')
DB_URL=os.getenv('DATABASE_URL',f'sqlite:///{ROOT / "employees.db"}')
engine=create_engine(DB_URL,connect_args={'check_same_thread':False} if DB_URL.startswith('sqlite') else {})
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)
passwords=PasswordHash.recommended(); bearer=HTTPBearer(auto_error=False)
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    name:Mapped[str]=mapped_column(String(80))
    email:Mapped[str]=mapped_column(String(254),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
    role:Mapped[str]=mapped_column(String(20),default='viewer')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Employee(Base):
    __tablename__='employees'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    full_name:Mapped[str]=mapped_column(String(120),index=True)
    email:Mapped[str]=mapped_column(String(254),index=True)
    phone:Mapped[str]=mapped_column(String(40),default='')
    job_title:Mapped[str]=mapped_column(String(100),index=True)
    department:Mapped[str]=mapped_column(String(80),index=True)
    employment_type:Mapped[str]=mapped_column(String(20),default='full_time')
    status:Mapped[str]=mapped_column(String(20),default='active',index=True)
    location:Mapped[str]=mapped_column(String(100),default='')
    manager:Mapped[str]=mapped_column(String(120),default='')
    start_date:Mapped[date]=mapped_column(Date,index=True)
    notes:Mapped[str]=mapped_column(Text,default='')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc))
@asynccontextmanager
async def lifespan(app:FastAPI):
    Base.metadata.create_all(engine)
    yield
app=FastAPI(title='People Ops API',version='1.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5179','http://127.0.0.1:5179'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
def db_session():
    with SessionLocal() as db: yield db
class RegisterIn(BaseModel):
    name:str=Field(min_length=2,max_length=80)
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel): email:EmailStr; password:str
class UserOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; name:str; email:EmailStr; role:str
class AuthOut(BaseModel): access_token:str; token_type:str='bearer'; user:UserOut
class TeamRoleIn(BaseModel): role:str
class EmployeeIn(BaseModel):
    full_name:str=Field(min_length=2,max_length=120)
    email:EmailStr
    phone:str=Field(default='',max_length=40)
    job_title:str=Field(min_length=2,max_length=100)
    department:str=Field(min_length=2,max_length=80)
    employment_type:str='full_time'
    status:str='active'
    location:str=Field(default='',max_length=100)
    manager:str=Field(default='',max_length=120)
    start_date:date
    notes:str=Field(default='',max_length=5000)
class EmployeeOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; full_name:str; email:EmailStr; phone:str; job_title:str; department:str; employment_type:str; status:str; location:str; manager:str; start_date:date; notes:str; created_at:datetime; updated_at:datetime
class EmployeeList(BaseModel): items:list[EmployeeOut]; total:int
def make_token(user): return jwt.encode({'sub':str(user.id),'exp':datetime.now(timezone.utc)+timedelta(days=14)},SECRET_KEY,algorithm='HS256')
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(db_session))->User:
    if credentials is None: raise HTTPException(401,'Please sign in to continue.')
    try: uid=int(jwt.decode(credentials.credentials,SECRET_KEY,algorithms=['HS256'])['sub'])
    except (jwt.InvalidTokenError,ValueError,KeyError): raise HTTPException(401,'Your session expired. Please sign in again.')
    user=db.get(User,uid)
    if user is None: raise HTTPException(401,'Account not found.')
    return user
def require_editor(user:User=Depends(current_user)):
    if user.role not in ('admin','editor'): raise HTTPException(403,'Your account has view-only access. Ask an admin for editor access.')
    return user
def require_admin(user:User=Depends(current_user)):
    if user.role!='admin': raise HTTPException(403,'Only an admin can manage team access.')
    return user
def validate_employee(data:EmployeeIn):
    if data.status not in ('active','on_leave','inactive'): raise HTTPException(422,'Choose an employee status.')
    if data.employment_type not in ('full_time','part_time','contractor','intern'): raise HTTPException(422,'Choose an employment type.')
@app.get('/api/health')
def health(): return {'status':'ok'}
@app.post('/api/auth/register',response_model=AuthOut,status_code=201)
def register(data:RegisterIn,db:Session=Depends(db_session)):
    email=str(data.email).lower()
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,'An account with that email already exists.')
    is_first=db.scalar(select(User.id).limit(1)) is None
    user=User(name=data.name.strip(),email=email,password_hash=passwords.hash(data.password),role='admin' if is_first else 'viewer')
    db.add(user); db.commit(); db.refresh(user)
    return AuthOut(access_token=make_token(user),user=user)
@app.post('/api/auth/login',response_model=AuthOut)
def login(data:LoginIn,db:Session=Depends(db_session)):
    user=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if not user or not passwords.verify(data.password,user.password_hash): raise HTTPException(401,'Email or password is incorrect.')
    return AuthOut(access_token=make_token(user),user=user)
@app.get('/api/auth/me',response_model=UserOut)
def me(user:User=Depends(current_user)): return user
@app.get('/api/employees',response_model=EmployeeList)
def employees(search:str='',department:str='',status_filter:str='',user:User=Depends(current_user),db:Session=Depends(db_session)):
    q=select(Employee)
    if department and department!='all': q=q.where(Employee.department==department)
    if status_filter:
        if status_filter not in ('active','on_leave','inactive'): raise HTTPException(422,'Invalid status filter.')
        q=q.where(Employee.status==status_filter)
    term=search.strip()
    if term: q=q.where(Employee.full_name.ilike(f'%{term}%')|Employee.job_title.ilike(f'%{term}%')|Employee.department.ilike(f'%{term}%')|Employee.email.ilike(f'%{term}%'))
    rows=db.scalars(q.order_by(Employee.full_name)).all()
    return EmployeeList(items=rows,total=len(rows))
@app.post('/api/employees',response_model=EmployeeOut,status_code=201)
def create_employee(data:EmployeeIn,user:User=Depends(require_editor),db:Session=Depends(db_session)):
    validate_employee(data); email=str(data.email).lower()
    if db.scalar(select(Employee.id).where(Employee.email==email)): raise HTTPException(409,'An employee with that email already exists.')
    row=Employee(**{**data.model_dump(),'email':email}); db.add(row); db.commit(); db.refresh(row); return row
@app.put('/api/employees/{employee_id}',response_model=EmployeeOut)
def update_employee(employee_id:int,data:EmployeeIn,user:User=Depends(require_editor),db:Session=Depends(db_session)):
    validate_employee(data)
    row=db.get(Employee,employee_id)
    if row is None: raise HTTPException(404,'Employee not found.')
    email=str(data.email).lower()
    duplicate=db.scalar(select(Employee.id).where(Employee.email==email,Employee.id!=employee_id))
    if duplicate: raise HTTPException(409,'Another employee already uses that email.')
    for key,value in data.model_dump().items(): setattr(row,key,value)
    row.email=email; db.commit(); db.refresh(row); return row
@app.delete('/api/employees/{employee_id}',status_code=204)
def delete_employee(employee_id:int,user:User=Depends(require_editor),db:Session=Depends(db_session)):
    row=db.get(Employee,employee_id)
    if row is None: raise HTTPException(404,'Employee not found.')
    db.delete(row); db.commit(); return Response(status_code=204)
@app.get('/api/team',response_model=list[UserOut])
def team(user:User=Depends(require_admin),db:Session=Depends(db_session)):
    return db.scalars(select(User).order_by(User.created_at)).all()
@app.patch('/api/team/{user_id}/role',response_model=UserOut)
def update_role(user_id:int,data:TeamRoleIn,user:User=Depends(require_admin),db:Session=Depends(db_session)):
    if data.role not in ('admin','editor','viewer'): raise HTTPException(422,'Role must be admin, editor, or viewer.')
    member=db.get(User,user_id)
    if member is None: raise HTTPException(404,'Team member not found.')
    if member.role=='admin' and data.role!='admin':
        admin_count=len(db.scalars(select(User).where(User.role=='admin')).all())
        if admin_count<=1: raise HTTPException(409,'The workspace must keep at least one admin.')
    member.role=data.role; db.commit(); db.refresh(member); return member
