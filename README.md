# Microservices E-commerce Application

A complete microservices architecture using FastAPI, AWS-ready with API Gateway integration.

## Architecture Overview

### Services
1. **User Service** (Port 8001)
   - Authentication & Authorization (JWT)
   - User management
   - Database: PostgreSQL

2. **Product Service** (Port 8002)
   - Product catalog management
   - Inventory tracking
   - Database: MongoDB

3. **Order Service** (Port 8003)
   - Order processing
   - Order status tracking
   - Database: MySQL

### Key Features
- **API Gateway**: Single entry point for all services
- **JWT Authentication**: Secure cross-service authentication
- **Service Communication**: REST APIs between services
- **Database Isolation**: Each service has its own database
- **Docker Support**: Complete docker-compose setup

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- AWS Account (for deployment)

### Local Development

1. Clone the repository
2. Start all services:
```bash
cd microservices-app
docker-compose up -d
```

3. Services will be available at:
   - API Gateway: http://localhost
   - User Service: http://localhost:8001
   - Product Service: http://localhost:8002
   - Order Service: http://localhost:8003

### API Endpoints

#### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user info

#### Products
- `GET /products` - List products (with filters)
- `POST /products` - Create product (auth required)
- `GET /products/{id}` - Get product details
- `PUT /products/{id}` - Update product (auth required)
- `DELETE /products/{id}` - Delete product (auth required)

#### Orders
- `GET /orders` - Get user orders (auth required)
- `POST /orders` - Create order (auth required)
- `GET /orders/{id}` - Get order details (auth required)
- `PATCH /orders/{id}/status` - Update order status
- `GET /orders/stats/summary` - Get order statistics

### Testing the Application

1. Register a user:
```bash
curl -X POST http://localhost/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"testuser","full_name":"Test User","password":"password123"}'
```

2. Login:
```bash
curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=password123"
```

3. Use the received token for authenticated requests:
```bash
curl -X POST http://localhost/products \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Product","description":"A test product","price":29.99,"quantity":100,"category":"Electronics","sku":"TEST001"}'
```

## AWS Deployment

### Using AWS API Gateway
1. Import the `api-gateway.yaml` OpenAPI specification
2. Configure VPC links or Lambda integrations
3. Deploy each service to ECS/EKS/EC2
4. Update service URLs in API Gateway

### Database Setup on AWS
- User Service: Amazon RDS (PostgreSQL)
- Product Service: Amazon DocumentDB or MongoDB Atlas
- Order Service: Amazon RDS (MySQL)

### Additional AWS Services
- **Amazon Cognito**: Alternative to JWT authentication
- **AWS Lambda**: For serverless deployment
- **Amazon SQS**: For async communication
- **Amazon ElastiCache**: For caching
- **AWS CloudWatch**: For monitoring and logging

## Security Considerations
- Use environment variables for sensitive data
- Implement rate limiting
- Add CORS configuration
- Use HTTPS in production
- Implement API key authentication for API Gateway
- Regular security audits

## Scaling Considerations
- Implement caching strategies
- Use message queues for async operations
- Database read replicas
- Service auto-scaling
- Load balancing

## Future Enhancements
- GraphQL API Gateway
- Event-driven architecture with Kafka/RabbitMQ
- Service mesh (Istio/Linkerd)
- Distributed tracing (Jaeger)
- Circuit breakers
- Health checks and monitoring dashboards