from datetime import datetime,timedelta,timezone
from pathlib import Path
import jwt
from dotenv import load_dotenv
from fastapi import Depends,FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel,ConfigDict,EmailStr,Field
from sqlalchemy import DateTime,ForeignKey,Integer,String,UniqueConstraint,create_engine,select,func
from sqlalchemy.orm import DeclarativeBase,Mapped,Session,mapped_column,sessionmaker
ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env')
SECRET_KEY='local-inventory-secret-change-before-deployment'
engine=create_engine(f"sqlite:///{ROOT/'inventory.db'}",connect_args={'check_same_thread':False})
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)
passwords=PasswordHash.recommended();bearer=HTTPBearer(auto_error=False)
class Base(DeclarativeBase):pass
class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(80))
    email:Mapped[str]=mapped_column(String(254),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
class Product(Base):
    __tablename__='products'
    __table_args__=(UniqueConstraint('user_id','sku',name='uq_product_user_sku'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    name:Mapped[str]=mapped_column(String(140))
    sku:Mapped[str]=mapped_column(String(50))
    category:Mapped[str]=mapped_column(String(60),default='General',index=True)
    unit_price_cents:Mapped[int]=mapped_column(Integer,default=0)
    quantity:Mapped[int]=mapped_column(Integer,default=0)
    reorder_level:Mapped[int]=mapped_column(Integer,default=5)
    description:Mapped[str]=mapped_column(String(500),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc))
class Movement(Base):
    __tablename__='movements'
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    product_id:Mapped[int]=mapped_column(ForeignKey('products.id',ondelete='CASCADE'),index=True)
    amount:Mapped[int]=mapped_column(Integer)
    before_quantity:Mapped[int]=mapped_column(Integer)
    after_quantity:Mapped[int]=mapped_column(Integer)
    reason:Mapped[str]=mapped_column(String(20))
    note:Mapped[str]=mapped_column(String(300),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),index=True)
Base.metadata.create_all(engine)
class RegisterIn(BaseModel):name:str=Field(min_length=2,max_length=80);email:EmailStr;password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel):email:EmailStr;password:str
class UserOut(BaseModel):model_config=ConfigDict(from_attributes=True);id:int;name:str;email:EmailStr
class AuthOut(BaseModel):access_token:str;token_type:str='bearer';user:UserOut
class ProductIn(BaseModel):name:str=Field(min_length=2,max_length=140);sku:str=Field(min_length=1,max_length=50);category:str=Field(default='General',min_length=2,max_length=60);unit_price_cents:int=Field(default=0,ge=0,le=100000000);quantity:int=Field(default=0,ge=0,le=10000000);reorder_level:int=Field(default=5,ge=0,le=10000000);description:str=Field(default='',max_length=500)
class ProductEdit(BaseModel):name:str=Field(min_length=2,max_length=140);sku:str=Field(min_length=1,max_length=50);category:str=Field(min_length=2,max_length=60);unit_price_cents:int=Field(ge=0,le=100000000);reorder_level:int=Field(ge=0,le=10000000);description:str=Field(default='',max_length=500)
class ProductOut(BaseModel):id:int;name:str;sku:str;category:str;unit_price_cents:int;quantity:int;reorder_level:int;description:str;updated_at:datetime;low_stock:bool
class AdjustIn(BaseModel):amount:int=Field(ne=0,ge=-10000000,le=10000000);reason:str=Field(pattern='^(received|issued|correction)$');note:str=Field(default='',max_length=300)
class MovementOut(BaseModel):id:int;product_id:int;product_name:str;amount:int;before_quantity:int;after_quantity:int;reason:str;note:str;created_at:datetime
app=FastAPI(title='Stockroom Inventory API',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:5185','http://localhost:5185'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
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
def product_out(p):return ProductOut(id=p.id,name=p.name,sku=p.sku,category=p.category,unit_price_cents=p.unit_price_cents,quantity=p.quantity,reorder_level=p.reorder_level,description=p.description,updated_at=p.updated_at,low_stock=p.quantity<=p.reorder_level)
def owned(pid,user,db):
    p=db.scalar(select(Product).where(Product.id==pid,Product.user_id==user.id))
    if p is None:raise HTTPException(404,'Product not found.')
    return p
@app.get('/api/health')
def health():return {'status':'ok'}
@app.post('/api/auth/register',response_model=AuthOut,status_code=201)
def register(data:RegisterIn,db:Session=Depends(db_session)):
    email=str(data.email).lower()
    if db.scalar(select(User.id).where(User.email==email)):raise HTTPException(409,'An account with that email already exists.')
    u=User(name=data.name.strip(),email=email,password_hash=passwords.hash(data.password));db.add(u);db.commit();db.refresh(u);return AuthOut(access_token=token_for(u),user=u)
@app.post('/api/auth/login',response_model=AuthOut)
def login(data:LoginIn,db:Session=Depends(db_session)):
    u=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if u is None or not passwords.verify(data.password,u.password_hash):raise HTTPException(401,'Email or password is incorrect.')
    return AuthOut(access_token=token_for(u),user=u)
@app.get('/api/auth/me',response_model=UserOut)
def me(user=Depends(current_user)):return user
@app.get('/api/products',response_model=list[ProductOut])
def products(q:str='',category:str='all',user=Depends(current_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(Product).where(Product.user_id==user.id).order_by(Product.name)).all()
    return [product_out(p) for p in rows if q.casefold() in (p.name+' '+p.sku+' '+p.category).casefold() and (category=='all' or p.category==category)]
@app.post('/api/products',response_model=ProductOut,status_code=201)
def create_product(data:ProductIn,user=Depends(current_user),db:Session=Depends(db_session)):
    sku=data.sku.strip().upper()
    if db.scalar(select(Product.id).where(Product.user_id==user.id,Product.sku==sku)):raise HTTPException(409,'You already use this SKU. Choose a unique product code.')
    p=Product(user_id=user.id,name=data.name.strip(),sku=sku,category=data.category.strip(),unit_price_cents=data.unit_price_cents,quantity=data.quantity,reorder_level=data.reorder_level,description=data.description.strip())
    db.add(p);db.flush()
    if p.quantity:db.add(Movement(user_id=user.id,product_id=p.id,amount=p.quantity,before_quantity=0,after_quantity=p.quantity,reason='received',note='Opening stock'))
    db.commit();db.refresh(p);return product_out(p)
@app.patch('/api/products/{product_id}',response_model=ProductOut)
def edit_product(product_id:int,data:ProductEdit,user=Depends(current_user),db:Session=Depends(db_session)):
    p=owned(product_id,user,db);sku=data.sku.strip().upper()
    if db.scalar(select(Product.id).where(Product.user_id==user.id,Product.sku==sku,Product.id!=p.id)):raise HTTPException(409,'You already use this SKU. Choose a unique product code.')
    p.name=data.name.strip();p.sku=sku;p.category=data.category.strip();p.unit_price_cents=data.unit_price_cents;p.reorder_level=data.reorder_level;p.description=data.description.strip();p.updated_at=datetime.now(timezone.utc)
    db.commit();db.refresh(p);return product_out(p)
@app.delete('/api/products/{product_id}',status_code=204)
def delete_product(product_id:int,user=Depends(current_user),db:Session=Depends(db_session)):
    p=owned(product_id,user,db);db.execute(Movement.__table__.delete().where(Movement.product_id==p.id));db.delete(p);db.commit();return None
@app.post('/api/products/{product_id}/adjust',response_model=ProductOut)
def adjust_stock(product_id:int,data:AdjustIn,user=Depends(current_user),db:Session=Depends(db_session)):
    p=owned(product_id,user,db);before=p.quantity;after=before+data.amount
    if after<0:raise HTTPException(409,'There is not enough stock for this issue. Check the quantity on hand.')
    if after>10000000:raise HTTPException(422,'Stock cannot exceed 10,000,000 units.')
    p.quantity=after;p.updated_at=datetime.now(timezone.utc);db.add(Movement(user_id=user.id,product_id=p.id,amount=data.amount,before_quantity=before,after_quantity=after,reason=data.reason,note=data.note.strip()));db.commit();db.refresh(p);return product_out(p)
@app.get('/api/movements',response_model=list[MovementOut])
def movements(limit:int=50,user=Depends(current_user),db:Session=Depends(db_session)):
    rows=db.execute(select(Movement,Product.name).join(Product,Product.id==Movement.product_id).where(Movement.user_id==user.id).order_by(Movement.created_at.desc()).limit(max(1,min(limit,200)))).all()
    return [MovementOut(id=m.id,product_id=m.product_id,product_name=name,amount=m.amount,before_quantity=m.before_quantity,after_quantity=m.after_quantity,reason=m.reason,note=m.note,created_at=m.created_at) for m,name in rows]
@app.get('/api/summary')
def summary(user=Depends(current_user),db:Session=Depends(db_session)):
    rows=db.scalars(select(Product).where(Product.user_id==user.id)).all()
    return {'products':len(rows),'units':sum(x.quantity for x in rows),'low_stock':sum(x.quantity<=x.reorder_level for x in rows),'stock_value_cents':sum(x.quantity*x.unit_price_cents for x in rows),'categories':sorted({x.category for x in rows})}
@app.post('/api/demo',response_model=list[ProductOut])
def demo(user=Depends(current_user),db:Session=Depends(db_session)):
    if db.scalar(select(Product.id).where(Product.user_id==user.id).limit(1)):raise HTTPException(409,'Demo stock can only be loaded into an empty inventory.')
    examples=[('Cotton canvas tote','BAG-014','Accessories',1800,24,8,'Natural cotton shopper bag.'),('Hardcover journal','PAP-028','Stationery',950,7,10,'A5 linen-bound ruled journal.'),('Ceramic travel cup','HOME-103','Home',2200,12,5,'Double-wall ceramic cup with lid.'),('Desk lamp, olive','HOME-211','Home',4900,4,6,'Adjustable LED task light.'),('Brass bookmark','GIFT-032','Accessories',700,31,8,'Hand-finished brass page marker.'),('Gift box, small','PACK-005','Packaging',350,6,12,'Recycled kraft gift box.'),('Printed postcard set','PAP-063','Stationery',1200,18,8,'Six illustrated A6 cards.')]
    made=[]
    for name,sku,cat,price,qty,reorder,desc in examples:
        p=Product(user_id=user.id,name=name,sku=sku,category=cat,unit_price_cents=price,quantity=qty,reorder_level=reorder,description=desc);db.add(p);db.flush();db.add(Movement(user_id=user.id,product_id=p.id,amount=qty,before_quantity=0,after_quantity=qty,reason='received',note='Demo opening stock'));made.append(p)
    db.commit()
    for p in made:db.refresh(p)
    return [product_out(p) for p in made]
