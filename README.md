# Real-time Inventory Management System

## Challenge Description
Design and implement a real-time inventory management system for an e-commerce platform that handles complex inventory operations, multiple warehouses, product variants, and real-time analytics.

### Core Requirements
1. Track inventory levels across multiple warehouses
2. Handle concurrent order processing with transaction management
3. Support product variants and bundles
4. Implement real-time inventory updates and analytics
5. Handle backorders and pre-orders
6. Implement inventory forecasting
7. Support multi-warehouse order fulfillment
8. Implement rate limiting and caching

### Technical Requirements
- Use Python for implementation
- Implement a REST API using FastAPI
- Use PostgreSQL for data storage
- Implement Redis for caching and rate limiting
- Use WebSocket for real-time updates
- Implement background tasks for analytics
- Add authentication and authorization
- Implement request validation and rate limiting

### API Endpoints to Implement
1. `GET /inventory/{product_id}` - Get current inventory level across warehouses
2. `POST /inventory/{product_id}/update` - Update inventory level in specific warehouse
3. `POST /orders` - Place an order with warehouse selection
4. `GET /inventory/low-stock` - Get products with low stock across warehouses
5. `POST /products/variants` - Create product variants
6. `POST /products/bundles` - Create product bundles
7. `GET /analytics/inventory` - Get inventory analytics
8. `POST /backorders` - Create backorders
9. `GET /warehouses` - List all warehouses
10. `POST /warehouses/{id}/transfer` - Transfer inventory between warehouses

### Data Models
```python
class Product:
    id: int
    name: str
    description: str
    sku: str
    category: str
    variants: List[ProductVariant]
    bundles: List[ProductBundle]

class ProductVariant:
    id: int
    product_id: int
    name: str
    sku: str
    attributes: Dict[str, str]

class ProductBundle:
    id: int
    name: str
    components: List[BundleComponent]

class Warehouse:
    id: int
    name: str
    location: str
    capacity: int

class Inventory:
    id: int
    product_id: int
    warehouse_id: int
    quantity: int
    reserved_quantity: int
    low_stock_threshold: int

class Order:
    id: int
    customer_id: int
    status: str
    items: List[OrderItem]
    warehouse_id: int
    created_at: datetime
    updated_at: datetime

class Backorder:
    id: int
    product_id: int
    customer_id: int
    quantity: int
    expected_date: datetime
    status: str
```

### Additional Features
1. Real-time inventory analytics dashboard
2. Multi-warehouse inventory management
3. Product variant and bundle support
4. Backorder and pre-order system
5. Inventory forecasting based on historical data
6. Rate limiting and caching
7. Authentication and authorization
8. Background tasks for analytics processing
9. WebSocket-based real-time updates
10. Transaction management for concurrent operations

## Setup Instructions
1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install fastapi uvicorn sqlalchemy websockets redis psycopg2-binary python-jose[cryptography] passlib[bcrypt] python-multipart
   ```

3. Set up PostgreSQL and Redis:
   ```bash
   # Install PostgreSQL and Redis
   # Create database and user
   # Update configuration in config.py
   ```

4. Run the application:
   ```bash
   uvicorn main:app --reload
   ```

## Evaluation Criteria
- System architecture and design
- Database schema design
- API design and implementation
- Concurrent operation handling
- Real-time functionality
- Caching and performance optimization
- Error handling and validation
- Security implementation
- Testing strategy
- Scalability considerations

## Time Management
- 15 minutes: System design discussion
- 40 minutes: Implementation
- 15 minutes: Testing and optimization
- 10 minutes: Questions and discussion 