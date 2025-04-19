from fastapi import FastAPI, HTTPException, WebSocket, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, select, update, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from pydantic import BaseModel
import jwt
import redis
import json
import asyncio
from config import settings, DATABASE_URL, REDIS_URL
from functools import lru_cache
import aioredis
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from passlib.context import CryptContext
from jose import JWTError, jwt

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis setup
redis_client = redis.Redis.from_url(REDIS_URL)

# Models (same as before)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    sku = Column(String, unique=True, index=True)
    category = Column(String)
    variants = relationship("ProductVariant", back_populates="product")
    bundles = relationship("ProductBundle", back_populates="product")

class ProductVariant(Base):
    __tablename__ = "product_variants"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    name = Column(String)
    sku = Column(String, unique=True, index=True)
    attributes = Column(String)  # JSON string
    product = relationship("Product", back_populates="variants")

class Warehouse(Base):
    __tablename__ = "warehouses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    location = Column(String)
    capacity = Column(Integer)
    inventory = relationship("Inventory", back_populates="warehouse")

class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"))
    quantity = Column(Integer)
    reserved_quantity = Column(Integer, default=0)
    low_stock_threshold = Column(Integer)
    warehouse = relationship("Warehouse", back_populates="inventory")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    order = relationship("Order", back_populates="items")

class Backorder(Base):
    __tablename__ = "backorders"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    customer_id = Column(Integer, ForeignKey("users.id"))
    quantity = Column(Integer)
    expected_date = Column(DateTime)
    status = Column(String)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Pydantic models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class ProductCreate(BaseModel):
    name: str
    description: str
    sku: str
    category: str

class InventoryUpdate(BaseModel):
    warehouse_id: int
    quantity: int
    low_stock_threshold: int

class OrderCreate(BaseModel):
    customer_id: int
    warehouse_id: int
    items: List[Dict[str, int]]

# Helper functions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

# WebSocket connections
connected_clients = set()

@app.on_event("startup")
async def startup():
    await FastAPILimiter.init(redis_client)

# Authentication endpoints
@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=UserCreate)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=get_password_hash(user.password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return user

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        connected_clients.remove(websocket)

async def notify_clients(message: str):
    for client in connected_clients:
        await client.send_text(message)

# Product endpoints
@app.post("/products/", dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_REQUESTS, seconds=settings.RATE_LIMIT_WINDOW))])
async def create_product(product: ProductCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_product = Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@app.get("/products/{product_id}")
async def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# Inventory endpoints
@app.get("/inventory/{product_id}")
async def get_inventory(product_id: int, db: Session = Depends(get_db)):
    inventory = db.query(Inventory).filter(Inventory.product_id == product_id).all()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    return inventory

@app.post("/inventory/{product_id}/update")
async def update_inventory(product_id: int, update: InventoryUpdate, db: Session = Depends(get_db)):
    inventory = db.query(Inventory).filter(
        and_(Inventory.product_id == product_id, Inventory.warehouse_id == update.warehouse_id)
    ).first()
    
    if not inventory:
        inventory = Inventory(
            product_id=product_id,
            warehouse_id=update.warehouse_id,
            quantity=update.quantity,
            low_stock_threshold=update.low_stock_threshold
        )
        db.add(inventory)
    else:
        inventory.quantity = update.quantity
        inventory.low_stock_threshold = update.low_stock_threshold
    
    db.commit()
    db.refresh(inventory)
    
    if inventory.quantity <= inventory.low_stock_threshold:
        await notify_clients(json.dumps({
            "type": "low_stock_alert",
            "product_id": product_id,
            "warehouse_id": update.warehouse_id,
            "current_stock": update.quantity
        }))
    
    return inventory

# Order endpoints
@app.post("/orders/")
async def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    # Start transaction
    try:
        # Create order
        db_order = Order(
            customer_id=order.customer_id,
            warehouse_id=order.warehouse_id,
            status="PENDING"
        )
        db.add(db_order)
        db.flush()  # Get the order ID
        
        # Process each item
        for item in order.items:
            product_id = item["product_id"]
            quantity = item["quantity"]
            
            # Check inventory
            inventory = db.query(Inventory).filter(
                and_(
                    Inventory.product_id == product_id,
                    Inventory.warehouse_id == order.warehouse_id
                )
            ).first()
            
            if not inventory or inventory.quantity < quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for product {product_id}"
                )
            
            # Create order item
            order_item = OrderItem(
                order_id=db_order.id,
                product_id=product_id,
                quantity=quantity
            )
            db.add(order_item)
            
            # Update inventory
            inventory.quantity -= quantity
            inventory.reserved_quantity += quantity
        
        # Update order status
        db_order.status = "COMPLETED"
        db.commit()
        
        # Notify clients
        await notify_clients(json.dumps({
            "type": "order_created",
            "order_id": db_order.id,
            "status": "COMPLETED"
        }))
        
        return db_order
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/orders/{order_id}")
async def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

# Warehouse endpoints
@app.get("/warehouses/")
async def get_warehouses(db: Session = Depends(get_db)):
    return db.query(Warehouse).all()

@app.post("/warehouses/{id}/transfer")
async def transfer_inventory(warehouse_id: int, transfer_data: Dict, db: Session = Depends(get_db)):
    from_warehouse_id = transfer_data["from_warehouse_id"]
    to_warehouse_id = transfer_data["to_warehouse_id"]
    product_id = transfer_data["product_id"]
    quantity = transfer_data["quantity"]
    
    # Start transaction
    try:
        # Check source inventory
        source_inventory = db.query(Inventory).filter(
            and_(
                Inventory.product_id == product_id,
                Inventory.warehouse_id == from_warehouse_id
            )
        ).first()
        
        if not source_inventory or source_inventory.quantity < quantity:
            raise HTTPException(
                status_code=400,
                detail="Insufficient inventory in source warehouse"
            )
        
        # Update source inventory
        source_inventory.quantity -= quantity
        
        # Update or create destination inventory
        dest_inventory = db.query(Inventory).filter(
            and_(
                Inventory.product_id == product_id,
                Inventory.warehouse_id == to_warehouse_id
            )
        ).first()
        
        if dest_inventory:
            dest_inventory.quantity += quantity
        else:
            dest_inventory = Inventory(
                product_id=product_id,
                warehouse_id=to_warehouse_id,
                quantity=quantity,
                low_stock_threshold=source_inventory.low_stock_threshold
            )
            db.add(dest_inventory)
        
        db.commit()
        
        # Notify clients
        await notify_clients(json.dumps({
            "type": "inventory_transfer",
            "product_id": product_id,
            "from_warehouse": from_warehouse_id,
            "to_warehouse": to_warehouse_id,
            "quantity": quantity
        }))
        
        return {"message": "Transfer completed successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Analytics endpoints
@app.get("/analytics/inventory")
async def get_inventory_analytics(db: Session = Depends(get_db)):
    # Get total products
    total_products = db.query(Product).count()
    
    # Get low stock items
    low_stock_items = db.query(Inventory).filter(
        Inventory.quantity <= Inventory.low_stock_threshold
    ).all()
    
    # Get warehouse capacity utilization
    warehouses = db.query(Warehouse).all()
    warehouse_utilization = []
    
    for warehouse in warehouses:
        total_capacity = warehouse.capacity
        used_capacity = db.query(Inventory).filter(
            Inventory.warehouse_id == warehouse.id
        ).with_entities(
            db.func.sum(Inventory.quantity).label('total_quantity')
        ).scalar() or 0
        
        utilization = (used_capacity / total_capacity) * 100 if total_capacity > 0 else 0
        
        warehouse_utilization.append({
            "warehouse_id": warehouse.id,
            "name": warehouse.name,
            "utilization": utilization
        })
    
    return {
        "total_products": total_products,
        "low_stock_items": len(low_stock_items),
        "warehouse_utilization": warehouse_utilization
    }

# Background tasks
@app.on_event("startup")
async def start_analytics_task():
    asyncio.create_task(process_analytics())

async def process_analytics():
    while True:
        try:
            # Process analytics in batches
            db = SessionLocal()
            try:
                # Get inventory trends
                inventory_trends = db.query(Inventory).order_by(
                    Inventory.updated_at.desc()
                ).limit(settings.ANALYTICS_BATCH_SIZE).all()
                
                # Process trends and update Redis cache
                for trend in inventory_trends:
                    key = f"inventory_trend:{trend.product_id}:{trend.warehouse_id}"
                    redis_client.setex(
                        key,
                        settings.CACHE_TTL,
                        json.dumps({
                            "quantity": trend.quantity,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    )
            finally:
                db.close()
            
            await asyncio.sleep(settings.ANALYTICS_INTERVAL)
        except Exception as e:
            print(f"Error in analytics processing: {str(e)}")
            await asyncio.sleep(60)  # Wait before retrying 