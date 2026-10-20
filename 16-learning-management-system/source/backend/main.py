from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import jwt
from fastapi import Depends,FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel,ConfigDict,EmailStr,Field
from sqlalchemy import Boolean,Date,DateTime,ForeignKey,Integer,String,Text,create_engine,select
from sqlalchemy.orm import DeclarativeBase,Mapped,Session,mapped_column,sessionmaker
ROOT=Path(__file__).resolve().parent;SECRET_KEY='local-learning-garden-secret-change-before-deployment'
engine=create_engine(f"sqlite:///{ROOT/'learning.db'}",connect_args={'check_same_thread':False});SessionLocal=sessionmaker(bind=engine,expire_on_commit=False);passwords=PasswordHash.recommended();bearer=HTTPBearer(auto_error=False)
STATUSES=['In progress','Planning','Completed'];CATEGORIES=['Development','Design','Business','Data','Languages','Creative','Other'];COLORS=['sage','lavender','peach','blue','rose','butter']
class Base(DeclarativeBase):pass
class User(Base):
 __tablename__='users'
 id:Mapped[int]=mapped_column(primary_key=True);name:Mapped[str]=mapped_column(String(80));email:Mapped[str]=mapped_column(String(254),unique=True,index=True);password_hash:Mapped[str]=mapped_column(String(255))
class Course(Base):
 __tablename__='courses'
 id:Mapped[int]=mapped_column(primary_key=True);user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True);title:Mapped[str]=mapped_column(String(140));instructor:Mapped[str]=mapped_column(String(100),default='');category:Mapped[str]=mapped_column(String(30),default='Other');description:Mapped[str]=mapped_column(Text,default='');status:Mapped[str]=mapped_column(String(20),default='Planning',index=True);color:Mapped[str]=mapped_column(String(20),default='sage');target_date:Mapped[date|None]=mapped_column(Date,nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Lesson(Base):
 __tablename__='lessons'
 id:Mapped[int]=mapped_column(primary_key=True);course_id:Mapped[int]=mapped_column(ForeignKey('courses.id',ondelete='CASCADE'),index=True);title:Mapped[str]=mapped_column(String(160));position:Mapped[int]=mapped_column(Integer,default=0);completed:Mapped[bool]=mapped_column(Boolean,default=False)
Base.metadata.create_all(engine)
class RegisterIn(BaseModel):name:str=Field(min_length=2,max_length=80);email:EmailStr;password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel):email:EmailStr;password:str
class UserOut(BaseModel):model_config=ConfigDict(from_attributes=True);id:int;name:str;email:EmailStr
class AuthOut(BaseModel):access_token:str;token_type:str='bearer';user:UserOut
class CourseIn(BaseModel):title:str=Field(min_length=2,max_length=140);instructor:str=Field(default='',max_length=100);category:str='Other';description:str=Field(default='',max_length=5000);status:str='Planning';color:str='sage';target_date:date|None=None
class LessonIn(BaseModel):title:str=Field(min_length=2,max_length=160)
class LessonOut(BaseModel):id:int;title:str;position:int;completed:bool
class CourseOut(BaseModel):id:int;title:str;instructor:str;category:str;description:str;status:str;color:str;target_date:date|None;created_at:datetime;lessons:list[LessonOut];completed_count:int;lesson_count:int;progress:int
app=FastAPI(title='Learning Garden API',version='1.0.0');app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:5188','http://localhost:5188'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
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
def valid_course(d):
 if d.category not in CATEGORIES:raise HTTPException(422,'Choose a valid course category.')
 if d.status not in STATUSES:raise HTTPException(422,'Choose a valid course status.')
 if d.color not in COLORS:raise HTTPException(422,'Choose a valid course color.')
def course_output(c,db):
 lessons=db.scalars(select(Lesson).where(Lesson.course_id==c.id).order_by(Lesson.position,Lesson.id)).all();done=sum(x.completed for x in lessons)
 return CourseOut(id=c.id,title=c.title,instructor=c.instructor,category=c.category,description=c.description,status=c.status,color=c.color,target_date=c.target_date,created_at=c.created_at,lessons=[LessonOut(id=x.id,title=x.title,position=x.position,completed=x.completed) for x in lessons],completed_count=done,lesson_count=len(lessons),progress=round(done/len(lessons)*100) if lessons else 0)
def owned_course(cid,user,db):
 c=db.scalar(select(Course).where(Course.id==cid,Course.user_id==user.id))
 if c is None:raise HTTPException(404,'Course not found.')
 return c
@app.get('/api/health')
def health():return {'status':'ok'}
@app.get('/api/meta')
def meta():return {'categories':CATEGORIES,'statuses':STATUSES,'colors':COLORS}
@app.post('/api/auth/register',response_model=AuthOut,status_code=201)
def register(d:RegisterIn,db:Session=Depends(db_session)):
 email=str(d.email).lower()
 if db.scalar(select(User.id).where(User.email==email)):raise HTTPException(409,'An account with this email already exists.')
 u=User(name=d.name.strip(),email=email,password_hash=passwords.hash(d.password));db.add(u);db.commit();db.refresh(u);return AuthOut(access_token=token_for(u),user=u)
@app.post('/api/auth/login',response_model=AuthOut)
def login(d:LoginIn,db:Session=Depends(db_session)):
 u=db.scalar(select(User).where(User.email==str(d.email).lower()))
 if u is None or not passwords.verify(d.password,u.password_hash):raise HTTPException(401,'Email or password is incorrect.')
 return AuthOut(access_token=token_for(u),user=u)
@app.get('/api/auth/me',response_model=UserOut)
def me(user=Depends(current_user)):return user
@app.get('/api/courses',response_model=list[CourseOut])
def list_courses(user=Depends(current_user),db:Session=Depends(db_session)):
 return [course_output(c,db) for c in db.scalars(select(Course).where(Course.user_id==user.id).order_by(Course.created_at.desc())).all()]
@app.post('/api/courses',response_model=CourseOut,status_code=201)
def create_course(d:CourseIn,user=Depends(current_user),db:Session=Depends(db_session)):
 valid_course(d);c=Course(user_id=user.id,**d.model_dump());db.add(c);db.commit();db.refresh(c);return course_output(c,db)
@app.patch('/api/courses/{cid}',response_model=CourseOut)
def update_course(cid:int,d:CourseIn,user=Depends(current_user),db:Session=Depends(db_session)):
 valid_course(d);c=owned_course(cid,user,db)
 for k,v in d.model_dump().items():setattr(c,k,v)
 db.commit();db.refresh(c);return course_output(c,db)
@app.delete('/api/courses/{cid}',status_code=204)
def delete_course(cid:int,user=Depends(current_user),db:Session=Depends(db_session)):
 c=owned_course(cid,user,db);db.query(Lesson).filter(Lesson.course_id==cid).delete();db.delete(c);db.commit();return None
@app.post('/api/courses/{cid}/lessons',response_model=CourseOut,status_code=201)
def add_lesson(cid:int,d:LessonIn,user=Depends(current_user),db:Session=Depends(db_session)):
 c=owned_course(cid,user,db);n=len(db.scalars(select(Lesson.id).where(Lesson.course_id==cid)).all());db.add(Lesson(course_id=cid,title=d.title.strip(),position=n))
 if c.status=='Completed':c.status='In progress'
 db.commit();db.refresh(c);return course_output(c,db)
@app.patch('/api/lessons/{lid}',response_model=CourseOut)
def toggle_lesson(lid:int,user=Depends(current_user),db:Session=Depends(db_session)):
 l=db.get(Lesson,lid)
 if l is None:raise HTTPException(404,'Lesson not found.')
 c=owned_course(l.course_id,user,db);l.completed=not l.completed
 lessons=db.scalars(select(Lesson).where(Lesson.course_id==c.id)).all()
 if lessons and all(x.completed or x.id==l.id for x in lessons):c.status='Completed'
 elif c.status=='Completed':c.status='In progress'
 db.commit();db.refresh(c);return course_output(c,db)
@app.delete('/api/lessons/{lid}',status_code=204)
def delete_lesson(lid:int,user=Depends(current_user),db:Session=Depends(db_session)):
 l=db.get(Lesson,lid)
 if l is None:raise HTTPException(404,'Lesson not found.')
 owned_course(l.course_id,user,db);db.delete(l);db.commit();return None
@app.get('/api/summary')
def summary(user=Depends(current_user),db:Session=Depends(db_session)):
 courses=db.scalars(select(Course).where(Course.user_id==user.id)).all();ids=[c.id for c in courses];lessons=db.scalars(select(Lesson).where(Lesson.course_id.in_(ids))).all() if ids else []
 done=sum(l.completed for l in lessons);return {'courses':len(courses),'active':sum(c.status=='In progress' for c in courses),'completed':sum(c.status=='Completed' for c in courses),'lessons':len(lessons),'lessons_done':done,'progress':round(done/len(lessons)*100) if lessons else 0,'minutes_this_week':0}
@app.post('/api/demo',response_model=list[CourseOut])
def demo(user=Depends(current_user),db:Session=Depends(db_session)):
 if db.scalar(select(Course.id).where(Course.user_id==user.id).limit(1)):raise HTTPException(409,'Sample courses can only be added to an empty library.')
 examples=[('JavaScript: The Practical Guide','Mira Patel','Development','Build confidence with the language behind interactive websites.','In progress','sage',['Values, types & variables','Functions and scope','DOM events','Async JavaScript','Build a small project'],2),('Designing with Type','Noah Kim','Design','A thoughtful introduction to type, spacing, and visual rhythm.','In progress','lavender',['Type anatomy','Hierarchy & scale','Pairing typefaces','Responsive layouts'],1),('SQL for Curious People','Asha Rao','Data','Learn to ask better questions of structured data.','Planning','butter',['Tables and rows','SELECT and WHERE','JOIN across tables','Grouping results'],0)]
 out=[]
 for title,instructor,category,description,status,color,names,done in examples:
  c=Course(user_id=user.id,title=title,instructor=instructor,category=category,description=description,status=status,color=color,target_date=date.today()+timedelta(days=21));db.add(c);db.flush()
  for i,name in enumerate(names):db.add(Lesson(course_id=c.id,title=name,position=i,completed=i<done))
  out.append(c)
 db.commit()
 for c in out:db.refresh(c)
 return [course_output(c,db) for c in out]
