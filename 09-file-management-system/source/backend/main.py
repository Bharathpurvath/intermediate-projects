import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parent
STORAGE = ROOT / 'storage'
STORAGE.mkdir(exist_ok=True)
load_dotenv(ROOT / '.env')
SECRET_KEY = os.getenv('SECRET_KEY', 'local-development-key-change-before-deployment')
DATABASE_URL = f"sqlite:///{ROOT / 'files.db'}"
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
MAX_BYTES = 15 * 1024 * 1024
BLOCKED_EXTENSIONS = {'.exe','.dll','.bat','.cmd','.com','.msi','.ps1','.sh','.js','.vbs','.scr','.jar'}

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class StoredFile(Base):
    __tablename__ = 'files'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    disk_name: Mapped[str] = mapped_column(String(100), unique=True)
    content_type: Mapped[str] = mapped_column(String(150), default='application/octet-stream')
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
Base.metadata.create_all(engine)

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
class AuthOut(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: UserOut
class FileOut(BaseModel):
    id: int
    name: str
    content_type: str
    size_bytes: int
    category: str
    created_at: datetime

app = FastAPI(title='Keepsake File Manager API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5181','http://localhost:5181'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
def db_session():
    with SessionLocal() as db: yield db
def token_for(user):
    return jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(days=14)}, SECRET_KEY, algorithm='HS256')
def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(db_session)):
    if credentials is None: raise HTTPException(401, 'Please sign in to continue.')
    try: user_id = int(jwt.decode(credentials.credentials, SECRET_KEY, algorithms=['HS256'])['sub'])
    except (jwt.InvalidTokenError, ValueError, KeyError): raise HTTPException(401, 'Your session expired. Please sign in again.')
    user = db.get(User, user_id)
    if user is None: raise HTTPException(401, 'Account not found.')
    return user
def category_for(name, mime):
    ext = Path(name).suffix.lower()
    if mime.startswith('image/'): return 'images'
    if mime.startswith('video/'): return 'videos'
    if mime.startswith('audio/'): return 'audio'
    if ext in {'.pdf','.doc','.docx','.txt','.rtf','.odt','.ppt','.pptx','.xls','.xlsx','.csv'}: return 'documents'
    if ext in {'.zip','.rar','.7z','.tar','.gz'}: return 'archives'
    return 'other'
def output(f):
    return FileOut(id=f.id, name=f.original_name, content_type=f.content_type, size_bytes=f.size_bytes, category=category_for(f.original_name, f.content_type), created_at=f.created_at)
def owned_file(file_id, user, db):
    item = db.scalar(select(StoredFile).where(StoredFile.id == file_id, StoredFile.user_id == user.id))
    if item is None: raise HTTPException(404, 'File not found.')
    return item

@app.get('/api/health')
def health(): return {'status':'ok'}
@app.post('/api/auth/register', response_model=AuthOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(db_session)):
    email = str(data.email).lower()
    if db.scalar(select(User).where(User.email == email)): raise HTTPException(409, 'An account with this email already exists.')
    user = User(name=data.name.strip(), email=email, password_hash=passwords.hash(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return AuthOut(access_token=token_for(user), user=user)
@app.post('/api/auth/login', response_model=AuthOut)
def login(data: LoginIn, db: Session = Depends(db_session)):
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if user is None or not passwords.verify(data.password, user.password_hash): raise HTTPException(401, 'Email or password is incorrect.')
    return AuthOut(access_token=token_for(user), user=user)
@app.get('/api/auth/me', response_model=UserOut)
def me(user=Depends(current_user)): return user
@app.get('/api/files', response_model=list[FileOut])
def list_files(q: str = Query('', max_length=200), category: str = Query('all'), user=Depends(current_user), db: Session = Depends(db_session)):
    rows = db.scalars(select(StoredFile).where(StoredFile.user_id == user.id).order_by(StoredFile.created_at.desc())).all()
    results = [f for f in rows if q.casefold() in f.original_name.casefold() and (category == 'all' or category_for(f.original_name, f.content_type) == category)]
    return [output(f) for f in results]
@app.post('/api/files', response_model=FileOut, status_code=201)
async def upload_file(file: UploadFile = File(...), user=Depends(current_user), db: Session = Depends(db_session)):
    name = Path((file.filename or '').replace('\\','/')).name.strip()
    if not name or name in {'.','..'}: raise HTTPException(400, 'Choose a file with a valid name.')
    if len(name) > 255: raise HTTPException(400, 'File names must be 255 characters or shorter.')
    if Path(name).suffix.lower() in BLOCKED_EXTENSIONS: raise HTTPException(415, 'This file type cannot be uploaded.')
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES: raise HTTPException(413, 'Files must be 15 MB or smaller.')
    if not content: raise HTTPException(400, 'This file is empty.')
    disk_name = uuid4().hex + Path(name).suffix.lower()
    folder = STORAGE / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / disk_name).write_bytes(content)
    item = StoredFile(user_id=user.id, original_name=name, disk_name=disk_name, content_type=(file.content_type or 'application/octet-stream')[:150], size_bytes=len(content))
    db.add(item)
    try: db.commit(); db.refresh(item)
    except Exception:
        db.rollback(); (folder / disk_name).unlink(missing_ok=True); raise
    return output(item)
@app.get('/api/files/{file_id}/download')
def download_file(file_id: int, user=Depends(current_user), db: Session = Depends(db_session)):
    item = owned_file(file_id, user, db)
    path = STORAGE / str(user.id) / item.disk_name
    if not path.is_file(): raise HTTPException(404, 'The stored file is missing.')
    return FileResponse(path, media_type=item.content_type, filename=item.original_name)
@app.delete('/api/files/{file_id}', status_code=204)
def delete_file(file_id: int, user=Depends(current_user), db: Session = Depends(db_session)):
    item = owned_file(file_id, user, db)
    path = STORAGE / str(user.id) / item.disk_name
    db.delete(item); db.commit(); path.unlink(missing_ok=True)
    return None
