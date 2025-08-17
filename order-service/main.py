from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import requests
import enum
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.auth import verify_token

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://user:password@order-db:3306/orderdb")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8001")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8002")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="Order Service", version="1.0.0")

security = HTTPBearer()

class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    shipping_address = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(String(50), nullable=False)
    product_name = Column(String(200))
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)
    
    order = relationship("Order", back_populates="items")

Base.metadata.create_all(bind=engine)

class OrderItemCreate(BaseModel):
    product_id: str
    quantity: int

class OrderCreate(BaseModel):
    items: List[OrderItemCreate]
    shipping_address: str

class OrderItemResponse(BaseModel):
    id: int
    product_id: str
    product_name: str
    quantity: int
    price: float
    subtotal: float

class OrderResponse(BaseModel):
    id: int
    user_id: int
    total_amount: float
    status: OrderStatus
    shipping_address: str
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]

class OrderStatusUpdate(BaseModel):
    status: OrderStatus

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def verify_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    
    try:
        response = requests.get(
            f"{USER_SERVICE_URL}/verify-token",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        return response.json()
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="User service unavailable")

@app.post("/orders", response_model=OrderResponse)
async def create_order(order_data: OrderCreate, user=Depends(verify_user), db: Session = Depends(get_db)):
    total_amount = 0
    order_items = []
    
    for item in order_data.items:
        try:
            response = requests.get(f"{PRODUCT_SERVICE_URL}/products/{item.product_id}")
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
            
            product = response.json()
            
            if product["quantity"] < item.quantity:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Insufficient inventory for product {product['name']}"
                )
            
            subtotal = product["price"] * item.quantity
            total_amount += subtotal
            
            order_items.append({
                "product_id": item.product_id,
                "product_name": product["name"],
                "quantity": item.quantity,
                "price": product["price"],
                "subtotal": subtotal
            })
            
        except requests.RequestException:
            raise HTTPException(status_code=503, detail="Product service unavailable")
    
    db_order = Order(
        user_id=user["user_id"],
        total_amount=total_amount,
        shipping_address=order_data.shipping_address
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    for item_data in order_items:
        db_item = OrderItem(
            order_id=db_order.id,
            **item_data
        )
        db.add(db_item)
        
        try:
            response = requests.patch(
                f"{PRODUCT_SERVICE_URL}/products/{item_data['product_id']}/inventory",
                params={"quantity_change": -item_data["quantity"]}
            )
            if response.status_code != 200:
                db.rollback()
                raise HTTPException(status_code=500, detail="Failed to update inventory")
        except requests.RequestException:
            db.rollback()
            raise HTTPException(status_code=503, detail="Product service unavailable")
    
    db.commit()
    db.refresh(db_order)
    
    return OrderResponse(
        id=db_order.id,
        user_id=db_order.user_id,
        total_amount=db_order.total_amount,
        status=db_order.status,
        shipping_address=db_order.shipping_address,
        created_at=db_order.created_at,
        updated_at=db_order.updated_at,
        items=[
            OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                price=item.price,
                subtotal=item.subtotal
            )
            for item in db_order.items
        ]
    )

@app.get("/orders", response_model=List[OrderResponse])
async def get_user_orders(user=Depends(verify_user), db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.user_id == user["user_id"]).all()
    
    return [
        OrderResponse(
            id=order.id,
            user_id=order.user_id,
            total_amount=order.total_amount,
            status=order.status,
            shipping_address=order.shipping_address,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=[
                OrderItemResponse(
                    id=item.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    quantity=item.quantity,
                    price=item.price,
                    subtotal=item.subtotal
                )
                for item in order.items
            ]
        )
        for order in orders
    ]

@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int, user=Depends(verify_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == user["user_id"]
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        total_amount=order.total_amount,
        status=order.status,
        shipping_address=order.shipping_address,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=[
            OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                price=item.price,
                subtotal=item.subtotal
            )
            for item in order.items
        ]
    )

@app.patch("/orders/{order_id}/status")
async def update_order_status(
    order_id: int, 
    status_update: OrderStatusUpdate, 
    user=Depends(verify_user), 
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status == OrderStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot update cancelled order")
    
    if status_update.status == OrderStatus.CANCELLED and order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=400, detail="Can only cancel pending orders")
    
    if status_update.status == OrderStatus.CANCELLED:
        for item in order.items:
            try:
                response = requests.patch(
                    f"{PRODUCT_SERVICE_URL}/products/{item.product_id}/inventory",
                    params={"quantity_change": item.quantity}
                )
                if response.status_code != 200:
                    raise HTTPException(status_code=500, detail="Failed to restore inventory")
            except requests.RequestException:
                raise HTTPException(status_code=503, detail="Product service unavailable")
    
    order.status = status_update.status
    order.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Order status updated", "new_status": order.status}

@app.get("/orders/stats/summary")
async def get_order_stats(user=Depends(verify_user), db: Session = Depends(get_db)):
    user_orders = db.query(Order).filter(Order.user_id == user["user_id"]).all()
    
    total_orders = len(user_orders)
    total_spent = sum(order.total_amount for order in user_orders)
    
    status_counts = {}
    for status in OrderStatus:
        count = len([order for order in user_orders if order.status == status])
        status_counts[status.value] = count
    
    return {
        "total_orders": total_orders,
        "total_spent": total_spent,
        "order_status_breakdown": status_counts
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)