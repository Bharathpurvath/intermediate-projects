import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'students.db'}")

engine_options = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    course: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)


class StudentFields(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    course: str = Field(min_length=2, max_length=100)
    year: int = Field(ge=1, le=8)


class StudentCreate(StudentFields):
    pass


class StudentUpdate(StudentFields):
    pass


class StudentRead(StudentFields):
    model_config = ConfigDict(from_attributes=True)
    id: int


def get_session():
    with SessionLocal() as session:
        yield session


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Student Management API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/students", response_model=list[StudentRead])
def list_students(session: Session = Depends(get_session)):
    return session.scalars(select(Student).order_by(Student.name)).all()


@app.post("/api/students", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(student_data: StudentCreate, session: Session = Depends(get_session)):
    email = str(student_data.email).lower()
    existing_student = session.scalar(select(Student).where(Student.email == email))
    if existing_student:
        raise HTTPException(status_code=409, detail="A student with this email already exists.")

    student = Student(**student_data.model_dump(exclude={"email"}), email=email)
    session.add(student)
    session.commit()
    session.refresh(student)
    return student


@app.put("/api/students/{student_id}", response_model=StudentRead)
def update_student(student_id: int, student_data: StudentUpdate, session: Session = Depends(get_session)):
    student = session.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found.")

    email = str(student_data.email).lower()
    duplicate = session.scalar(
        select(Student).where(Student.email == email, Student.id != student_id)
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="A student with this email already exists.")

    for field, value in student_data.model_dump().items():
        setattr(student, field, email if field == "email" else value)
    session.commit()
    session.refresh(student)
    return student


@app.delete("/api/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: int, session: Session = Depends(get_session)):
    student = session.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found.")

    session.delete(student)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)