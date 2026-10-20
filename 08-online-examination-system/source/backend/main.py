import os
from contextlib import asynccontextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path
import jwt
from dotenv import load_dotenv
from fastapi import Depends,FastAPI,HTTPException,Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel,ConfigDict,EmailStr,Field
from sqlalchemy import Boolean,DateTime,ForeignKey,Integer,String,Text,UniqueConstraint,create_engine,select
from sqlalchemy.orm import DeclarativeBase,Mapped,Session,mapped_column,relationship,sessionmaker,selectinload
ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env')
SECRET_KEY=os.getenv('SECRET_KEY','change-before-deployment')
DB_URL=os.getenv('DATABASE_URL',f'sqlite:///{ROOT / "exams.db"}')
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
    role:Mapped[str]=mapped_column(String(20),default='student')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Exam(Base):
    __tablename__='exams'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    title:Mapped[str]=mapped_column(String(160))
    description:Mapped[str]=mapped_column(Text)
    duration_minutes:Mapped[int]=mapped_column(Integer)
    is_published:Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    questions:Mapped[list['Question']]=relationship(back_populates='exam',cascade='all, delete-orphan',order_by='Question.position',lazy='selectin')
class Question(Base):
    __tablename__='questions'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    exam_id:Mapped[int]=mapped_column(ForeignKey('exams.id',ondelete='CASCADE'),index=True)
    prompt:Mapped[str]=mapped_column(Text)
    option_a:Mapped[str]=mapped_column(String(500))
    option_b:Mapped[str]=mapped_column(String(500))
    option_c:Mapped[str]=mapped_column(String(500))
    option_d:Mapped[str]=mapped_column(String(500))
    correct_option:Mapped[str]=mapped_column(String(1))
    explanation:Mapped[str]=mapped_column(Text,default='')
    points:Mapped[int]=mapped_column(Integer,default=1)
    position:Mapped[int]=mapped_column(Integer,default=0)
    exam:Mapped[Exam]=relationship(back_populates='questions')
class Attempt(Base):
    __tablename__='attempts'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    exam_id:Mapped[int]=mapped_column(ForeignKey('exams.id',ondelete='CASCADE'),index=True)
    status:Mapped[str]=mapped_column(String(20),default='in_progress',index=True)
    score:Mapped[int]=mapped_column(Integer,default=0)
    max_score:Mapped[int]=mapped_column(Integer)
    duration_minutes:Mapped[int]=mapped_column(Integer)
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    submitted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    exam:Mapped[Exam]=relationship()
    answers:Mapped[list['AttemptAnswer']]=relationship(back_populates='attempt',cascade='all, delete-orphan',lazy='selectin')
class AttemptAnswer(Base):
    __tablename__='attempt_answers'
    __table_args__=(UniqueConstraint('attempt_id','question_id',name='uq_attempt_question'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    attempt_id:Mapped[int]=mapped_column(ForeignKey('attempts.id',ondelete='CASCADE'),index=True)
    question_id:Mapped[int]=mapped_column(ForeignKey('questions.id',ondelete='CASCADE'),index=True)
    selected_option:Mapped[str]=mapped_column(String(1))
    attempt:Mapped[Attempt]=relationship(back_populates='answers')
SEED_QUESTIONS=[
('Which HTML element is used for the largest heading?',['<h6>','<heading>','<h1>','<head>'],'C','The h1 element represents the highest-level heading.',1),
('Which CSS property changes text color?',['font-style','color','text-color','foreground'],'B','The color property sets an element text color.',1),
('Which keyword declares a block-scoped variable in JavaScript?',['var','let','define','static'],'B','let is block-scoped. const is also block-scoped.',1),
('What does DOM stand for?',['Document Object Model','Data Order Map','Digital Ordinance Model','Document Orientation Mode'],'A','The DOM represents a page as a tree of objects.',1),
('Which HTTP method is commonly used to retrieve data?',['POST','PATCH','GET','DELETE'],'C','GET requests retrieve a resource without changing it.',1),
('Which CSS layout system is designed for one-dimensional layouts?',['Grid','Flexbox','Float','Position'],'B','Flexbox is suited to arranging items along a row or column.',1),
('What does JSON.stringify() do?',['Parses JSON into an object','Converts a value to a JSON string','Fetches an API','Creates a new array'],'B','JSON.stringify serializes a JavaScript value as JSON text.',1),
('Which attribute provides alternative text for an image?',['title','src','alt','label'],'C','The alt attribute describes an image for assistive technology and fallback display.',1),
]
@asynccontextmanager
async def lifespan(app:FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(Exam.id).limit(1)) is None:
            exam=Exam(title='Web Fundamentals',description='A short checkpoint on the core ideas behind building for the web. Take your time, read each question, and trust what you have learned.',duration_minutes=10,is_published=True)
            exam.questions=[Question(prompt=q[0],option_a=q[1][0],option_b=q[1][1],option_c=q[1][2],option_d=q[1][3],correct_option=q[2],explanation=q[3],points=q[4],position=i) for i,q in enumerate(SEED_QUESTIONS)]
            db.add(exam); db.commit()
    yield
app=FastAPI(title='Checkmate Exam API',version='1.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5180','http://127.0.0.1:5180'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
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
class QuestionIn(BaseModel):
    prompt:str=Field(min_length=5,max_length=2000)
    options:list[str]=Field(min_length=4,max_length=4)
    correct_option:str
    explanation:str=Field(default='',max_length=2000)
    points:int=Field(default=1,ge=1,le=100)
class ExamIn(BaseModel):
    title:str=Field(min_length=4,max_length=160)
    description:str=Field(min_length=10,max_length=4000)
    duration_minutes:int=Field(ge=1,le=240)
    is_published:bool=False
    questions:list[QuestionIn]=Field(min_length=1,max_length=50)
class OptionOut(BaseModel): key:str; text:str
class QuestionPublic(BaseModel): id:int; prompt:str; options:list[OptionOut]; points:int; position:int
class ExamSummary(BaseModel): id:int; title:str; description:str; duration_minutes:int; is_published:bool; question_count:int; created_at:datetime
class ExamDetail(BaseModel): id:int; title:str; description:str; duration_minutes:int; questions:list[QuestionPublic]
class SavedAnswer(BaseModel): question_id:int; selected_option:str
class AnswerIn(BaseModel): question_id:int; selected_option:str
class SaveAnswersIn(BaseModel): answers:list[AnswerIn]
class AttemptStartOut(BaseModel): id:int; exam_id:int; exam_title:str; duration_minutes:int; started_at:datetime; deadline:datetime; questions:list[QuestionPublic]; answers:list[SavedAnswer]
class AttemptSummary(BaseModel): id:int; exam_id:int; exam_title:str; status:str; score:int; max_score:int; started_at:datetime; submitted_at:datetime|None
class AnswerResult(BaseModel): question_id:int; prompt:str; options:list[OptionOut]; selected_option:str|None; correct_option:str; is_correct:bool; points:int; points_earned:int; explanation:str
class AttemptResult(BaseModel): id:int; exam_title:str; score:int; max_score:int; percentage:int; submitted_at:datetime; answers:list[AnswerResult]
def make_token(user): return jwt.encode({'sub':str(user.id),'exp':datetime.now(timezone.utc)+timedelta(days=14)},SECRET_KEY,algorithm='HS256')
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(db_session))->User:
    if credentials is None: raise HTTPException(401,'Please sign in to continue.')
    try: uid=int(jwt.decode(credentials.credentials,SECRET_KEY,algorithms=['HS256'])['sub'])
    except (jwt.InvalidTokenError,ValueError,KeyError): raise HTTPException(401,'Your session expired. Please sign in again.')
    user=db.get(User,uid)
    if user is None: raise HTTPException(401,'Account not found.')
    return user
def require_admin(user:User=Depends(current_user)):
    if user.role!='admin': raise HTTPException(403,'Only an admin can create or manage exams.')
    return user
def options_for(q): return [OptionOut(key=k,text=v) for k,v in zip('ABCD',[q.option_a,q.option_b,q.option_c,q.option_d])]
def public_question(q): return QuestionPublic(id=q.id,prompt=q.prompt,options=options_for(q),points=q.points,position=q.position)
def as_utc(value): return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
def attempt_deadline(a): return as_utc(a.started_at)+timedelta(minutes=a.duration_minutes)
def load_attempt(attempt_id,user,db):
    a=db.scalar(select(Attempt).where(Attempt.id==attempt_id,Attempt.user_id==user.id).options(selectinload(Attempt.exam).selectinload(Exam.questions),selectinload(Attempt.answers)))
    if a is None: raise HTTPException(404,'Exam attempt not found.')
    return a
def start_output(a): return AttemptStartOut(id=a.id,exam_id=a.exam_id,exam_title=a.exam.title,duration_minutes=a.duration_minutes,started_at=as_utc(a.started_at),deadline=attempt_deadline(a),questions=[public_question(q) for q in a.exam.questions],answers=[SavedAnswer(question_id=x.question_id,selected_option=x.selected_option) for x in a.answers])
@app.get('/api/health')
def health(): return {'status':'ok'}
@app.post('/api/auth/register',response_model=AuthOut,status_code=201)
def register(data:RegisterIn,db:Session=Depends(db_session)):
    email=str(data.email).lower()
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,'An account with that email already exists.')
    role='admin' if db.scalar(select(User.id).limit(1)) is None else 'student'
    user=User(name=data.name.strip(),email=email,password_hash=passwords.hash(data.password),role=role)
    db.add(user); db.commit(); db.refresh(user)
    return AuthOut(access_token=make_token(user),user=user)
@app.post('/api/auth/login',response_model=AuthOut)
def login(data:LoginIn,db:Session=Depends(db_session)):
    user=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if not user or not passwords.verify(data.password,user.password_hash): raise HTTPException(401,'Email or password is incorrect.')
    return AuthOut(access_token=make_token(user),user=user)
@app.get('/api/auth/me',response_model=UserOut)
def me(user:User=Depends(current_user)): return user
@app.get('/api/exams',response_model=list[ExamSummary])
def exams(user:User=Depends(current_user),db:Session=Depends(db_session)):
    q=select(Exam).options(selectinload(Exam.questions)).order_by(Exam.created_at.desc())
    rows=db.scalars(q).all()
    if user.role!='admin': rows=[x for x in rows if x.is_published]
    return [ExamSummary(id=x.id,title=x.title,description=x.description,duration_minutes=x.duration_minutes,is_published=x.is_published,question_count=len(x.questions),created_at=x.created_at) for x in rows]
@app.get('/api/exams/{exam_id}',response_model=ExamDetail)
def exam_detail(exam_id:int,user:User=Depends(current_user),db:Session=Depends(db_session)):
    exam=db.scalar(select(Exam).where(Exam.id==exam_id).options(selectinload(Exam.questions)))
    if exam is None or (not exam.is_published and user.role!='admin'): raise HTTPException(404,'Exam not found.')
    return ExamDetail(id=exam.id,title=exam.title,description=exam.description,duration_minutes=exam.duration_minutes,questions=[public_question(q) for q in exam.questions])
@app.post('/api/exams',response_model=ExamSummary,status_code=201)
def create_exam(data:ExamIn,user:User=Depends(require_admin),db:Session=Depends(db_session)):
    for q in data.questions:
        if q.correct_option not in ('A','B','C','D'): raise HTTPException(422,'Correct answer must be A, B, C, or D.')
        if any(not option.strip() for option in q.options): raise HTTPException(422,'All four answer options are required.')
    exam=Exam(title=data.title.strip(),description=data.description.strip(),duration_minutes=data.duration_minutes,is_published=data.is_published)
    exam.questions=[Question(prompt=q.prompt.strip(),option_a=q.options[0].strip(),option_b=q.options[1].strip(),option_c=q.options[2].strip(),option_d=q.options[3].strip(),correct_option=q.correct_option,explanation=q.explanation.strip(),points=q.points,position=i) for i,q in enumerate(data.questions)]
    db.add(exam); db.commit(); db.refresh(exam)
    return ExamSummary(id=exam.id,title=exam.title,description=exam.description,duration_minutes=exam.duration_minutes,is_published=exam.is_published,question_count=len(exam.questions),created_at=exam.created_at)
class PublishIn(BaseModel): is_published:bool
@app.patch('/api/exams/{exam_id}/publish',response_model=ExamSummary)
def publish_exam(exam_id:int,data:PublishIn,user:User=Depends(require_admin),db:Session=Depends(db_session)):
    exam=db.scalar(select(Exam).where(Exam.id==exam_id).options(selectinload(Exam.questions)))
    if exam is None: raise HTTPException(404,'Exam not found.')
    exam.is_published=data.is_published; db.commit(); db.refresh(exam)
    return ExamSummary(id=exam.id,title=exam.title,description=exam.description,duration_minutes=exam.duration_minutes,is_published=exam.is_published,question_count=len(exam.questions),created_at=exam.created_at)
@app.delete('/api/exams/{exam_id}',status_code=204)
def delete_exam(exam_id:int,user:User=Depends(require_admin),db:Session=Depends(db_session)):
    exam=db.get(Exam,exam_id)
    if exam is None: raise HTTPException(404,'Exam not found.')
    if db.scalar(select(Attempt.id).where(Attempt.exam_id==exam_id).limit(1)): raise HTTPException(409,'This exam has attempts and cannot be deleted. Unpublish it instead.')
    db.delete(exam); db.commit(); return Response(status_code=204)
def result_output(a):
    saved={x.question_id:x.selected_option for x in a.answers}
    details=[]; score=0
    for q in a.exam.questions:
        selected=saved.get(q.id); correct=selected==q.correct_option; earned=q.points if correct else 0; score+=earned
        details.append(AnswerResult(question_id=q.id,prompt=q.prompt,options=options_for(q),selected_option=selected,correct_option=q.correct_option,is_correct=correct,points=q.points,points_earned=earned,explanation=q.explanation))
    return AttemptResult(id=a.id,exam_title=a.exam.title,score=score,max_score=a.max_score,percentage=round(score*100/a.max_score) if a.max_score else 0,submitted_at=as_utc(a.submitted_at),answers=details)
def finish_attempt(a,db):
    saved={x.question_id:x.selected_option for x in a.answers}
    score=sum(q.points for q in a.exam.questions if saved.get(q.id)==q.correct_option)
    a.score=score; a.status='submitted'; a.submitted_at=datetime.now(timezone.utc)
    db.commit()
    return result_output(a)
@app.post('/api/exams/{exam_id}/attempts',response_model=AttemptStartOut,status_code=201)
def start_attempt(exam_id:int,user:User=Depends(current_user),db:Session=Depends(db_session)):
    exam=db.scalar(select(Exam).where(Exam.id==exam_id).options(selectinload(Exam.questions)))
    if exam is None or (not exam.is_published and user.role!='admin'): raise HTTPException(404,'Exam not found.')
    if not exam.questions: raise HTTPException(409,'This exam does not have any questions yet.')
    attempt=Attempt(user_id=user.id,exam_id=exam.id,max_score=sum(q.points for q in exam.questions),duration_minutes=exam.duration_minutes)
    db.add(attempt); db.commit()
    return start_output(load_attempt(attempt.id,user,db))
@app.get('/api/attempts',response_model=list[AttemptSummary])
def attempts(user:User=Depends(current_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(Attempt).where(Attempt.user_id==user.id).options(selectinload(Attempt.exam)).order_by(Attempt.started_at.desc())).all()
    return [AttemptSummary(id=a.id,exam_id=a.exam_id,exam_title=a.exam.title,status=a.status,score=a.score,max_score=a.max_score,started_at=as_utc(a.started_at),submitted_at=as_utc(a.submitted_at) if a.submitted_at else None) for a in rows]
@app.get('/api/attempts/{attempt_id}',response_model=AttemptStartOut)
def get_attempt(attempt_id:int,user:User=Depends(current_user),db:Session=Depends(db_session)):
    a=load_attempt(attempt_id,user,db)
    if a.status!='in_progress': raise HTTPException(409,'This attempt has already been submitted.')
    return start_output(a)
@app.put('/api/attempts/{attempt_id}/answers')
def save_answers(attempt_id:int,data:SaveAnswersIn,user:User=Depends(current_user),db:Session=Depends(db_session)):
    a=load_attempt(attempt_id,user,db)
    if a.status!='in_progress': raise HTTPException(409,'This attempt has already been submitted.')
    if datetime.now(timezone.utc)>=attempt_deadline(a): raise HTTPException(409,'Time is up. Submit your exam to see the result.')
    questions={q.id for q in a.exam.questions}
    current={x.question_id:x for x in a.answers}
    for answer in data.answers:
        if answer.question_id not in questions: raise HTTPException(422,'Answer contains a question from another exam.')
        if answer.selected_option not in ('A','B','C','D'): raise HTTPException(422,'Choose one of the four answer options.')
        if answer.question_id in current: current[answer.question_id].selected_option=answer.selected_option
        else: a.answers.append(AttemptAnswer(question_id=answer.question_id,selected_option=answer.selected_option))
    db.commit()
    return {'saved':True,'answered':len(a.answers)}
@app.post('/api/attempts/{attempt_id}/submit',response_model=AttemptResult)
def submit_attempt(attempt_id:int,user:User=Depends(current_user),db:Session=Depends(db_session)):
    a=load_attempt(attempt_id,user,db)
    if a.status=='submitted': return result_output(a)
    return finish_attempt(a,db)
@app.get('/api/attempts/{attempt_id}/result',response_model=AttemptResult)
def attempt_result(attempt_id:int,user:User=Depends(current_user),db:Session=Depends(db_session)):
    a=load_attempt(attempt_id,user,db)
    if a.status!='submitted': raise HTTPException(409,'Submit the exam before viewing its result.')
    return result_output(a)
