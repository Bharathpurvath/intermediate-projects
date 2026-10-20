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
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
SECRET_KEY = os.getenv('SECRET_KEY', 'change-before-deployment')
DB_URL = os.getenv('DATABASE_URL', f'sqlite:///{ROOT / "expenses.db"}')
engine = create_engine(DB_URL, connect_args={'check_same_thread': False} if DB_URL.startswith('sqlite') else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    transactions: Mapped[list['Transaction']] = relationship(back_populates='user', cascade='all, delete-orphan')
class Transaction(Base):
    __tablename__ = 'transactions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    kind: Mapped[str] = mapped_column(String(10), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    note: Mapped[str] = mapped_column(Text, default='')
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    user: Mapped[User] = relationship(back_populates='transactions')
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield
app = FastAPI(title='Pocket Ledger API', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5175', 'http://127.0.0.1:5175'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
def db_session():
    with SessionLocal() as db: yield db
class AccountIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
class LoginIn(BaseModel): email: EmailStr; password: str
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; name: str; email: EmailStr
class AuthOut(BaseModel): access_token: str; token_type: str = 'bearer'; user: UserOut
class TransactionIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    amount: float = Field(gt=0, le=999999999)
    kind: str
    category: str = Field(min_length=2, max_length=40)
    note: str = Field(default='', max_length=1000)
    occurred_on: date
    @classmethod
    def validate_kind(cls, value): return value
class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; title: str; amount: float; kind: str; category: str; note: str; occurred_on: date; created_at: datetime

def token_for(user):
    return jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(days=14)}, SECRET_KEY, algorithm='HS256')
def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(db_session)) -> User:
    if credentials is None: raise HTTPException(401, 'Please sign in to continue.')
    try: user_id = int(jwt.decode(credentials.credentials, SECRET_KEY, algorithms=['HS256'])['sub'])
    except (jwt.InvalidTokenError, ValueError, KeyError): raise HTTPException(401, 'Your session expired. Please sign in again.')
    user = db.get(User, user_id)
    if user is None: raise HTTPException(401, 'Account not found.')
    return user
def validate_transaction(data: TransactionIn):
    if data.kind not in ('income', 'expense'): raise HTTPException(422, 'Type must be income or expense.')
    return data
@app.get('/api/health')
def health(): return {'status': 'ok'}
@app.post('/api/auth/register', response_model=AuthOut, status_code=201)
def register(data: AccountIn, db: Session = Depends(db_session)):
    email = str(data.email).lower()
    if db.scalar(select(User).where(User.email == email)): raise HTTPException(409, 'An account with that email already exists.')
    user = User(name=data.name.strip(), email=email, password_hash=passwords.hash(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return AuthOut(access_token=token_for(user), user=user)
@app.post('/api/auth/login', response_model=AuthOut)
def login(data: LoginIn, db: Session = Depends(db_session)):
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if not user or not passwords.verify(data.password, user.password_hash): raise HTTPException(401, 'Email or password is incorrect.')
    return AuthOut(access_token=token_for(user), user=user)
@app.get('/api/auth/me', response_model=UserOut)
def me(user: User = Depends(current_user)): return user
@app.get('/api/transactions', response_model=list[TransactionOut])
def list_transactions(month: str = '', user: User = Depends(current_user), db: Session = Depends(db_session)):
    query = select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.occurred_on.desc(), Transaction.id.desc())
    if month:
        try: year, number = map(int, month.split('-')); start = date(year, number, 1); end = date(year + (number == 12), number % 12 + 1, 1)
        except (ValueError, TypeError): raise HTTPException(422, 'Month must use YYYY-MM format.')
        query = query.where(Transaction.occurred_on >= start, Transaction.occurred_on < end)
    return db.scalars(query).all()
@app.post('/api/transactions', response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionIn, user: User = Depends(current_user), db: Session = Depends(db_session)):
    validate_transaction(data)
    item = Transaction(**data.model_dump(), user_id=user.id)
    db.add(item); db.commit(); db.refresh(item)
    return item
@app.put('/api/transactions/{transaction_id}', response_model=TransactionOut)
def update_transaction(transaction_id: int, data: TransactionIn, user: User = Depends(current_user), db: Session = Depends(db_session)):
    validate_transaction(data)
    item = db.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id))
    if item is None: raise HTTPException(404, 'Transaction not found.')
    for key, value in data.model_dump().items(): setattr(item, key, value)
    db.commit(); db.refresh(item)
    return item
@app.delete('/api/transactions/{transaction_id}', status_code=204)
def delete_transaction(transaction_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    item = db.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id))
    if item is None: raise HTTPException(404, 'Transaction not found.')
    db.delete(item); db.commit()
    return Response(status_code=204)
