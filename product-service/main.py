from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pymongo import MongoClient
from bson import ObjectId
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import requests
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.auth import verify_token

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://product-db:27017/")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8001")

client = MongoClient(MONGODB_URL)
db = client.product_database
products_collection = db.products

app = FastAPI(title="Product Service", version="1.0.0")

security = HTTPBearer()

class Product(BaseModel):
    name: str
    description: str
    price: float
    quantity: int
    category: str
    sku: str
    image_url: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[int] = None
    category: Optional[str] = None
    image_url: Optional[str] = None

class ProductResponse(BaseModel):
    id: str = Field(alias="_id")
    name: str
    description: str
    price: float
    quantity: int
    category: str
    sku: str
    image_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True

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

@app.post("/products", response_model=ProductResponse)
async def create_product(product: Product, user=Depends(verify_user)):
    existing_product = products_collection.find_one({"sku": product.sku})
    if existing_product:
        raise HTTPException(status_code=400, detail="Product with this SKU already exists")
    
    product_dict = product.dict()
    product_dict["created_at"] = datetime.utcnow()
    product_dict["updated_at"] = datetime.utcnow()
    product_dict["created_by"] = user["user_id"]
    
    result = products_collection.insert_one(product_dict)
    created_product = products_collection.find_one({"_id": result.inserted_id})
    
    return ProductResponse(
        _id=str(created_product["_id"]),
        name=created_product["name"],
        description=created_product["description"],
        price=created_product["price"],
        quantity=created_product["quantity"],
        category=created_product["category"],
        sku=created_product["sku"],
        image_url=created_product.get("image_url"),
        created_at=created_product["created_at"],
        updated_at=created_product["updated_at"]
    )

@app.get("/products", response_model=List[ProductResponse])
async def list_products(
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    skip: int = 0,
    limit: int = 20
):
    query = {}
    
    if category:
        query["category"] = category
    
    if min_price is not None or max_price is not None:
        price_query = {}
        if min_price is not None:
            price_query["$gte"] = min_price
        if max_price is not None:
            price_query["$lte"] = max_price
        query["price"] = price_query
    
    products = products_collection.find(query).skip(skip).limit(limit)
    
    return [
        ProductResponse(
            _id=str(product["_id"]),
            name=product["name"],
            description=product["description"],
            price=product["price"],
            quantity=product["quantity"],
            category=product["category"],
            sku=product["sku"],
            image_url=product.get("image_url"),
            created_at=product["created_at"],
            updated_at=product["updated_at"]
        )
        for product in products
    ]

@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    try:
        product = products_collection.find_one({"_id": ObjectId(product_id)})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return ProductResponse(
            _id=str(product["_id"]),
            name=product["name"],
            description=product["description"],
            price=product["price"],
            quantity=product["quantity"],
            category=product["category"],
            sku=product["sku"],
            image_url=product.get("image_url"),
            created_at=product["created_at"],
            updated_at=product["updated_at"]
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product ID")

@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, product_update: ProductUpdate, user=Depends(verify_user)):
    try:
        update_data = {k: v for k, v in product_update.dict().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_data["updated_at"] = datetime.utcnow()
        
        result = products_collection.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        
        updated_product = products_collection.find_one({"_id": ObjectId(product_id)})
        
        return ProductResponse(
            _id=str(updated_product["_id"]),
            name=updated_product["name"],
            description=updated_product["description"],
            price=updated_product["price"],
            quantity=updated_product["quantity"],
            category=updated_product["category"],
            sku=updated_product["sku"],
            image_url=updated_product.get("image_url"),
            created_at=updated_product["created_at"],
            updated_at=updated_product["updated_at"]
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product ID")

@app.patch("/products/{product_id}/inventory")
async def update_inventory(product_id: str, quantity_change: int):
    try:
        product = products_collection.find_one({"_id": ObjectId(product_id)})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        new_quantity = product["quantity"] + quantity_change
        if new_quantity < 0:
            raise HTTPException(status_code=400, detail="Insufficient inventory")
        
        products_collection.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": {"quantity": new_quantity, "updated_at": datetime.utcnow()}}
        )
        
        return {"message": "Inventory updated", "new_quantity": new_quantity}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product ID")

@app.delete("/products/{product_id}")
async def delete_product(product_id: str, user=Depends(verify_user)):
    try:
        result = products_collection.delete_one({"_id": ObjectId(product_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return {"message": "Product deleted successfully"}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product ID")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)