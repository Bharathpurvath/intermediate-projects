from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import jwt
from fastapi import Depends,FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel,ConfigDict,EmailStr,Field
from sqlalchemy import Date,DateTime,ForeignKey,Integer,String,create_engine,select
from sqlalchemy.orm import DeclarativeBase,Mapped,Session,mapped_column,sessionmaker
ROOT=Path(__file__).resolve().parent
SECRET_KEY='local-pocket-ledger-secret-change-before-deployment'
engine=create_engine(f"sqlite:///{ROOT/'finance.db'}",connect_args={'check_same_thread':False})
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False);passwords=PasswordHash.recommended();bearer=HTTPBearer(auto_error=False)
CATEGORIES={'expense':['Food & dining','Housing','Transport','Shopping','Health','Utilities','Entertainment','Education','Travel','Other'],'income':['Salary','Freelance','Investment','Gift','Other']}
class Base(DeclarativeBase):pass
class User(Base):
 __tablename__='users'
 id:Mapped[int]=mapped_column(primary_key=True)
 name:Mapped[str]=mapped_column(String(80))
 email:Mapped[str]=mapped_column(String(254),unique=True,index=True)
 password_hash:Mapped[str]=mapped_column(String(255))
class Transaction(Base):
 __tablename__='transactions'
 id:Mapped[int]=mapped_column(primary_key=True)
 user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
 kind:Mapped[str]=mapped_column(String(10),index=True)
 amount_paise:Mapped[int]=mapped_column(Integer)
 category:Mapped[str]=mapped_column(String(50),index=True)
 description:Mapped[str]=mapped_column(String(160),default='')
 occurred_on:Mapped[date]=mapped_column(Date,index=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Budget(Base):
 __tablename__='budgets'
 id:Mapped[int]=mapped_column(primary_key=True)
 user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
 category:Mapped[str]=mapped_column(String(50))
 month:Mapped[str]=mapped_column(String(7),index=True)
 amount_paise:Mapped[int]=mapped_column(Integer)
Base.metadata.create_all(engine)
class RegisterIn(BaseModel):name:str=Field(min_length=2,max_length=80);email:EmailStr;password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel):email:EmailStr;password:str
class UserOut(BaseModel):model_config=ConfigDict(from_attributes=True);id:int;name:str;email:EmailStr
class AuthOut(BaseModel):access_token:str;token_type:str='bearer';user:UserOut
class TxIn(BaseModel):kind:str;amount_paise:int=Field(gt=0,le=100000000000);category:str=Field(min_length=1,max_length=50);description:str=Field(default='',max_length=160);occurred_on:date
class TxOut(BaseModel):id:int;kind:str;amount_paise:int;category:str;description:str;occurred_on:date
class BudgetIn(BaseModel):category:str;month:str=Field(pattern=r'^\d{4}-\d{2}$');amount_paise:int=Field(gt=0,le=100000000000)
class BudgetOut(BaseModel):id:int;category:str;month:str;amount_paise:int
app=FastAPI(title='Pocket Ledger API',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:5187','http://localhost:5187'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
def db_session():
 with SessionLocal() as db:yield db
def token_for(u):return jwt.encode({'sub':str(u.id),'exp':datetime.now(timezone.utc)+timedelta(days=14)},SECRET_KEY,algorithm='HS256')
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(db_session)):
 if credentials is None:raise HTTPException(401,'Please sign in to continue.')
 try:uid=int(jwt.decode(credentials.credentials,SECRET_KEY,algorithms=['HS256'])['sub'])
 except(jwt.InvalidTokenError,ValueError,KeyError):raise HTTPException(401,'Your session expired. Please sign in again.')
 u=db.get(User,uid)
 if u is None:raise HTTPException(401,'Account not found.')
 return u
def txout(x):return TxOut(id=x.id,kind=x.kind,amount_paise=x.amount_paise,category=x.category,description=x.description,occurred_on=x.occurred_on)
def valid_tx(data):
 if data.kind not in CATEGORIES:raise HTTPException(422,'Choose income or expense.')
 if data.category not in CATEGORIES[data.kind]:raise HTTPException(422,'Choose a valid category for this transaction type.')
def ym(value):
 try:return datetime.strptime(value,'%Y-%m').date()
 except ValueError:raise HTTPException(422,'Use a month in YYYY-MM format.')
def month_end(start):return (start.replace(day=28)+timedelta(days=4)).replace(day=1)
@app.get('/api/health')
def health():return {'status':'ok'}
@app.get('/api/categories')
def categories():return CATEGORIES
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
@app.get('/api/transactions',response_model=list[TxOut])
def list_transactions(month:str|None=None,kind:str='all',category:str='all',q:str='',user=Depends(current_user),db:Session=Depends(db_session)):
 stmt=select(Transaction).where(Transaction.user_id==user.id)
 if month:
  start=ym(month);stmt=stmt.where(Transaction.occurred_on>=start,Transaction.occurred_on<month_end(start))
 if kind in CATEGORIES:stmt=stmt.where(Transaction.kind==kind)
 rows=db.scalars(stmt.order_by(Transaction.occurred_on.desc(),Transaction.id.desc())).all()
 return [txout(x) for x in rows if (category=='all' or x.category==category) and q.casefold() in (x.description+' '+x.category).casefold()]
@app.post('/api/transactions',response_model=TxOut,status_code=201)
def create_tx(data:TxIn,user=Depends(current_user),db:Session=Depends(db_session)):
 valid_tx(data);x=Transaction(user_id=user.id,kind=data.kind,amount_paise=data.amount_paise,category=data.category,description=data.description.strip(),occurred_on=data.occurred_on);db.add(x);db.commit();db.refresh(x);return txout(x)
@app.delete('/api/transactions/{item_id}',status_code=204)
def delete_tx(item_id:int,user=Depends(current_user),db:Session=Depends(db_session)):
 x=db.scalar(select(Transaction).where(Transaction.id==item_id,Transaction.user_id==user.id))
 if x is None:raise HTTPException(404,'Transaction not found.')
 db.delete(x);db.commit();return None
@app.get('/api/budgets',response_model=list[BudgetOut])
def get_budgets(month:str,user=Depends(current_user),db:Session=Depends(db_session)):
 ym(month);return db.scalars(select(Budget).where(Budget.user_id==user.id,Budget.month==month)).all()
@app.put('/api/budgets',response_model=BudgetOut)
def put_budget(data:BudgetIn,user=Depends(current_user),db:Session=Depends(db_session)):
 ym(data.month)
 if data.category not in CATEGORIES['expense']:raise HTTPException(422,'Choose a valid expense category.')
 b=db.scalar(select(Budget).where(Budget.user_id==user.id,Budget.month==data.month,Budget.category==data.category))
 if b is None:b=Budget(user_id=user.id,month=data.month,category=data.category,amount_paise=data.amount_paise);db.add(b)
 else:b.amount_paise=data.amount_paise
 db.commit();db.refresh(b);return b
@app.get('/api/summary')
def summary(month:str,user=Depends(current_user),db:Session=Depends(db_session)):
 start=ym(month);end=month_end(start)
 rows=db.scalars(select(Transaction).where(Transaction.user_id==user.id,Transaction.occurred_on>=start,Transaction.occurred_on<end)).all()
 income=sum(x.amount_paise for x in rows if x.kind=='income');expenses=sum(x.amount_paise for x in rows if x.kind=='expense')
 category={c:sum(x.amount_paise for x in rows if x.kind=='expense' and x.category==c) for c in CATEGORIES['expense']}
 monthly=[]
 for offset in range(5,-1,-1):
  d=(start.replace(day=1)-timedelta(days=offset*28)).replace(day=1);mend=month_end(d)
  subset=db.scalars(select(Transaction).where(Transaction.user_id==user.id,Transaction.occurred_on>=d,Transaction.occurred_on<mend)).all()
  monthly.append({'month':d.strftime('%Y-%m'),'income':sum(x.amount_paise for x in subset if x.kind=='income'),'expenses':sum(x.amount_paise for x in subset if x.kind=='expense')})
 budgets=db.scalars(select(Budget).where(Budget.user_id==user.id,Budget.month==month)).all()
 return {'month':month,'income_paise':income,'expenses_paise':expenses,'balance_paise':income-expenses,'transaction_count':len(rows),'category_spend':category,'monthly':monthly,'budgets':[{'category':b.category,'amount_paise':b.amount_paise,'spent_paise':category.get(b.category,0)} for b in budgets]}
@app.post('/api/demo',response_model=list[TxOut])
def demo(month:str,user=Depends(current_user),db:Session=Depends(db_session)):
 start=ym(month);end=month_end(start)
 if db.scalar(select(Transaction.id).where(Transaction.user_id==user.id,Transaction.occurred_on>=start,Transaction.occurred_on<end).limit(1)):raise HTTPException(409,'Sample transactions can only be added to an empty month.')
 examples=[('income',9200000,'Salary','Monthly salary'),('income',1800000,'Freelance','Website project milestone'),('expense',1850000,'Housing','Monthly rent'),('expense',625000,'Food & dining','Groceries and dinner'),('expense',310000,'Transport','Commute and fuel'),('expense',240000,'Utilities','Electricity and internet'),('expense',195000,'Health','Pharmacy and checkup'),('expense',360000,'Shopping','Home essentials'),('expense',180000,'Entertainment','Concert tickets'),('expense',120000,'Education','Online course')]
 out=[]
 for i,(kind,amount,category,description) in enumerate(examples):
  day=min([2,3,5,8,10,12,14,17,20,24][i],(end-timedelta(days=1)).day)
  x=Transaction(user_id=user.id,kind=kind,amount_paise=amount,category=category,description=description,occurred_on=start.replace(day=day));db.add(x);out.append(x)
 for category,amount in [('Housing',2200000),('Food & dining',800000),('Transport',500000),('Utilities',350000),('Shopping',450000),('Health',300000),('Entertainment',300000),('Education',250000)]:db.add(Budget(user_id=user.id,category=category,month=month,amount_paise=amount))
 db.commit()
 for x in out:db.refresh(x)
 return [txout(x) for x in out]
