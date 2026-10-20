import os
from contextlib import asynccontextmanager
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
import jwt
from dotenv import load_dotenv
from fastapi import Depends,FastAPI,HTTPException,Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel,ConfigDict,EmailStr,Field
from sqlalchemy import DateTime,ForeignKey,Integer,Numeric,String,Text,create_engine,select
from sqlalchemy.orm import DeclarativeBase,Mapped,Session,mapped_column,relationship,sessionmaker,selectinload
ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env')
SECRET_KEY=os.getenv('SECRET_KEY','change-before-deployment')
DB_URL=os.getenv('DATABASE_URL',f'sqlite:///{ROOT / "store.db"}')
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
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    orders:Mapped[list['Order']]=relationship(back_populates='user')
class Product(Base):
    __tablename__='products'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    sku:Mapped[str]=mapped_column(String(32),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(120),index=True)
    tagline:Mapped[str]=mapped_column(String(140),default='')
    description:Mapped[str]=mapped_column(Text)
    category:Mapped[str]=mapped_column(String(40),index=True)
    price:Mapped[Decimal]=mapped_column(Numeric(10,2))
    stock:Mapped[int]=mapped_column(Integer,default=10)
    visual:Mapped[str]=mapped_column(String(24),default='form-1')
    badge:Mapped[str]=mapped_column(String(32),default='')
    featured:Mapped[bool]=mapped_column(default=False)
    active:Mapped[bool]=mapped_column(default=True)
class Order(Base):
    __tablename__='orders'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    total:Mapped[Decimal]=mapped_column(Numeric(10,2))
    status:Mapped[str]=mapped_column(String(20),default='confirmed')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    user:Mapped[User]=relationship(back_populates='orders')
    items:Mapped[list['OrderItem']]=relationship(back_populates='order',cascade='all, delete-orphan',lazy='selectin')
class OrderItem(Base):
    __tablename__='order_items'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    order_id:Mapped[int]=mapped_column(ForeignKey('orders.id',ondelete='CASCADE'),index=True)
    product_id:Mapped[int|None]=mapped_column(ForeignKey('products.id',ondelete='SET NULL'),nullable=True)
    product_name:Mapped[str]=mapped_column(String(120))
    unit_price:Mapped[Decimal]=mapped_column(Numeric(10,2))
    quantity:Mapped[int]=mapped_column(Integer)
    order:Mapped[Order]=relationship(back_populates='items')
PRODUCT_SEED=[
('ST-01','Arc Table Light','A softer kind of focus.','A small, sculptural lamp made for late pages and early mornings. A warm diffused glow, touch dimming, and a weighted base that stays put.','Lighting','4890.00',18,'lamp','BESTSELLER',True),
('ST-02','Field Notes Set','Keep the good ideas close.','Three cloth-bound notebooks with smooth, uncoated pages and lay-flat binding. Made to travel from the desk to everywhere else.','Desk','1290.00',42,'notebook','',True),
('ST-03','Daily Carry Tray','A place for the everyday.','A hand-finished catchall for keys, pens, and all the small things that deserve a home. Solid beech with a soft oil finish.','Accessories','1850.00',27,'tray','NEW',False),
('ST-04','Contour Bookend','Give your shelf some shape.','A pair of weighted powder-coated bookends with a quiet architectural profile. Strong enough for the heavy reads.','Storage','2450.00',21,'bookend','',True),
('ST-05','Studio Desk Mat','A little room to think.','A generous felt surface that brings calm to busy desks. Recycled wool blend with a non-slip natural rubber base.','Desk','3200.00',16,'mat','STAFF PICK',False),
('ST-06','Pebble Pen','Good lines, every time.','A balanced aluminum rollerball with a soft-touch finish and a refillable ink cartridge. Designed for long notes.','Accessories','980.00',53,'pen','',False),
('ST-07','Quiet Hour Clock','Let the day find its pace.','A minimal analog clock with a silent sweep movement and a warm oak face. A useful reminder to look up.','Accessories','3650.00',12,'clock','',False),
('ST-08','Fold Magazine Rack','A little order, without the fuss.','An easy, open steel frame for the books, zines, and papers you like to keep within reach. Folds flat when you need the space.','Storage','2790.00',9,'rack','LOW STOCK',False),
('ST-09','Halo Candle','Close the laptop gently.','A low-smoke soy candle with cedar, bergamot, and a little quiet. Poured in a reusable amber glass vessel.','Accessories','1150.00',36,'candle','',False),
('ST-10','Everyday Mug','A good pause, held well.','Hand-thrown stoneware with a comfortable curved handle and a satin glaze. Each one has its own small variations.','Desk','1450.00',24,'mug','',False),
]
@asynccontextmanager
async def lifespan(app:FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(Product.id).limit(1)) is None:
            db.add_all([Product(sku=s[0],name=s[1],tagline=s[2],description=s[3],category=s[4],price=Decimal(s[5]),stock=s[6],visual=s[7],badge=s[8],featured=s[9]) for s in PRODUCT_SEED])
            db.commit()
    yield
app=FastAPI(title='Forma Supply API',version='1.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5178','http://127.0.0.1:5178'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
def db_session():
    with SessionLocal() as db: yield db
class RegisterIn(BaseModel):
    name:str=Field(min_length=2,max_length=80)
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)
class LoginIn(BaseModel): email:EmailStr; password:str
class UserOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; name:str; email:EmailStr
class AuthOut(BaseModel): access_token:str; token_type:str='bearer'; user:UserOut
class ProductOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; sku:str; name:str; tagline:str; description:str; category:str; price:Decimal; stock:int; visual:str; badge:str; featured:bool
class OrderLineIn(BaseModel): product_id:int; quantity:int=Field(ge=1,le=20)
class OrderIn(BaseModel): items:list[OrderLineIn]=Field(min_length=1,max_length=30)
class OrderLineOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; product_id:int|None; product_name:str; unit_price:Decimal; quantity:int
class OrderOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; total:Decimal; status:str; created_at:datetime; items:list[OrderLineOut]
def make_token(user): return jwt.encode({'sub':str(user.id),'exp':datetime.now(timezone.utc)+timedelta(days=14)},SECRET_KEY,algorithm='HS256')
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(db_session))->User:
    if credentials is None: raise HTTPException(401,'Please sign in to continue.')
    try: uid=int(jwt.decode(credentials.credentials,SECRET_KEY,algorithms=['HS256'])['sub'])
    except (jwt.InvalidTokenError,ValueError,KeyError): raise HTTPException(401,'Your session expired. Please sign in again.')
    user=db.get(User,uid)
    if user is None: raise HTTPException(401,'Account not found.')
    return user
@app.get('/api/health')
def health(): return {'status':'ok'}
@app.get('/api/products',response_model=list[ProductOut])
def products(search:str='',category:str='',db:Session=Depends(db_session)):
    q=select(Product).where(Product.active.is_(True))
    if category and category!='All': q=q.where(Product.category==category)
    term=search.strip()
    if term: q=q.where(Product.name.ilike(f'%{term}%')|Product.tagline.ilike(f'%{term}%')|Product.description.ilike(f'%{term}%')|Product.category.ilike(f'%{term}%'))
    return db.scalars(q.order_by(Product.featured.desc(),Product.name)).all()
@app.post('/api/auth/register',response_model=AuthOut,status_code=201)
def register(data:RegisterIn,db:Session=Depends(db_session)):
    email=str(data.email).lower()
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,'An account with that email already exists.')
    user=User(name=data.name.strip(),email=email,password_hash=passwords.hash(data.password)); db.add(user); db.commit(); db.refresh(user)
    return AuthOut(access_token=make_token(user),user=user)
@app.post('/api/auth/login',response_model=AuthOut)
def login(data:LoginIn,db:Session=Depends(db_session)):
    user=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if not user or not passwords.verify(data.password,user.password_hash): raise HTTPException(401,'Email or password is incorrect.')
    return AuthOut(access_token=make_token(user),user=user)
@app.get('/api/auth/me',response_model=UserOut)
def me(user:User=Depends(current_user)): return user
@app.get('/api/orders',response_model=list[OrderOut])
def orders(user:User=Depends(current_user),db:Session=Depends(db_session)):
    return db.scalars(select(Order).where(Order.user_id==user.id).options(selectinload(Order.items)).order_by(Order.created_at.desc())).all()
@app.post('/api/orders',response_model=OrderOut,status_code=201)
def checkout(data:OrderIn,user:User=Depends(current_user),db:Session=Depends(db_session)):
    quantities={}
    for line in data.items: quantities[line.product_id]=quantities.get(line.product_id,0)+line.quantity
    if any(q>20 for q in quantities.values()): raise HTTPException(422,'Maximum quantity per product is 20.')
    product_ids=list(quantities)
    found=db.scalars(select(Product).where(Product.id.in_(product_ids),Product.active.is_(True))).all()
    by_id={p.id:p for p in found}
    if len(by_id)!=len(product_ids): raise HTTPException(404,'One or more products are no longer available.')
    for pid,qty in quantities.items():
        if by_id[pid].stock<qty: raise HTTPException(409,'Not enough stock for '+by_id[pid].name+'.')
    order=Order(user_id=user.id,total=Decimal('0.00'),status='confirmed')
    total=Decimal('0.00')
    for pid,qty in quantities.items():
        product=by_id[pid]; product.stock-=qty; total+=product.price*qty
        order.items.append(OrderItem(product_id=product.id,product_name=product.name,unit_price=product.price,quantity=qty))
    order.total=total; db.add(order); db.commit(); db.refresh(order)
    return order
