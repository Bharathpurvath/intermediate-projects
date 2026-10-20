import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine, or_, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / '.env')
SECRET_KEY = os.getenv('SECRET_KEY', 'development-only-change-me')
ALGORITHM = 'HS256'
DB_URL = os.getenv('DATABASE_URL', f'sqlite:///{BASE / "blog.db"}')
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
    posts: Mapped[list['Post']] = relationship(back_populates='author', cascade='all, delete-orphan')

class Post(Base):
    __tablename__ = 'posts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str] = mapped_column(String(50), default='Thoughts')
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    author_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    author: Mapped[User] = relationship(back_populates='posts')

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield

app = FastAPI(title='Margin Blog API', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5174', 'http://127.0.0.1:5174'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

def db_session():
    with SessionLocal() as db: yield db

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr

class PostIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    category: str = Field(default='Thoughts', min_length=2, max_length=50)
    content: str = Field(min_length=20, max_length=20000)

class PostOut(BaseModel):
    id: int
    title: str
    category: str
    content: str
    created_at: datetime
    updated_at: datetime
    author: UserOut

class AuthOut(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: UserOut

def make_token(user: User) -> str:
    return jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(days=7)}, SECRET_KEY, algorithm=ALGORITHM)

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(db_session)) -> User:
    if not credentials: raise HTTPException(status_code=401, detail='Please sign in to continue.')
    try: uid = int(jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])['sub'])
    except (jwt.InvalidTokenError, ValueError, KeyError): raise HTTPException(status_code=401, detail='Your session expired. Please sign in again.')
    user = db.get(User, uid)
    if not user: raise HTTPException(status_code=401, detail='Account not found.')
    return user

def post_out(p: Post) -> PostOut:
    return PostOut(id=p.id, title=p.title, category=p.category, content=p.content, created_at=p.created_at, updated_at=p.updated_at, author=UserOut.model_validate(p.author))

def owned_post(post_id: int, user: User, db: Session) -> Post:
    post = db.get(Post, post_id)
    if not post: raise HTTPException(status_code=404, detail='Post not found.')
    if post.author_id != user.id: raise HTTPException(status_code=403, detail='You can only change your own posts.')
    return post

@app.get('/api/health')
def health(): return {'status': 'ok'}

@app.post('/api/auth/register', response_model=AuthOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(db_session)):
    email = str(data.email).lower()
    if db.scalar(select(User).where(User.email == email)): raise HTTPException(status_code=409, detail='That email is already registered.')
    user = User(name=data.name.strip(), email=email, password_hash=passwords.hash(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return AuthOut(access_token=make_token(user), user=user)

@app.post('/api/auth/login', response_model=AuthOut)
def login(data: LoginIn, db: Session = Depends(db_session)):
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if not user or not passwords.verify(data.password, user.password_hash): raise HTTPException(status_code=401, detail='Email or password is incorrect.')
    return AuthOut(access_token=make_token(user), user=user)

@app.get('/api/auth/me', response_model=UserOut)
def me(user: User = Depends(current_user)): return user

@app.get('/api/posts', response_model=list[PostOut])
def list_posts(search: str = '', db: Session = Depends(db_session)):
    query = select(Post).order_by(Post.created_at.desc())
    term = search.strip()
    if term: query = query.where(or_(Post.title.ilike(f'%{term}%'), Post.content.ilike(f'%{term}%'), Post.category.ilike(f'%{term}%'), Post.author.has(User.name.ilike(f'%{term}%'))))
    return [post_out(p) for p in db.scalars(query).all()]

@app.post('/api/posts', response_model=PostOut, status_code=201)
def create_post(data: PostIn, user: User = Depends(current_user), db: Session = Depends(db_session)):
    post = Post(title=data.title.strip(), category=data.category.strip(), content=data.content.strip(), author=user)
    db.add(post); db.commit(); db.refresh(post)
    return post_out(post)

@app.put('/api/posts/{post_id}', response_model=PostOut)
def update_post(post_id: int, data: PostIn, user: User = Depends(current_user), db: Session = Depends(db_session)):
    post = owned_post(post_id, user, db)
    post.title, post.category, post.content = data.title.strip(), data.category.strip(), data.content.strip()
    db.commit(); db.refresh(post)
    return post_out(post)

@app.delete('/api/posts/{post_id}', status_code=204)
def delete_post(post_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    db.delete(owned_post(post_id, user, db)); db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
