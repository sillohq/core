# 📦 Request Schemas in Nexios

Request schemas define the structure and documentation for incoming data in your API. Nexios uses Pydantic models to provide comprehensive OpenAPI documentation and type definitions for all request bodies.

::: warning Manual Validation Required
Nexios does **not** automatically validate request data against Pydantic models. The `request_model` parameter is used solely for OpenAPI documentation generation. You must implement your own validation logic in your handlers if you want to validate incoming data against the schema.
:::

## 🎯 Why Use Request Schemas?

Request schemas provide multiple benefits for API development:

- **Clear Documentation**: Schemas are automatically reflected in OpenAPI docs
- **Type Safety**: Full IDE support with autocompletion and type checking  
- **API Contracts**: Define clear expectations for API consumers
- **Code Generation**: Enable client SDK generation with proper types
- **Developer Experience**: Interactive documentation with examples

## 🏗️ Basic Request Models

Define request schemas using Pydantic's `BaseModel`. These work with POST, PUT, PATCH, and any endpoint expecting a request body:

```python
from nexios import NexiosApp
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    full_name: Optional[str] = Field(None, description="User's full name")
    is_active: bool = Field(True, description="Account activation status")

app = NexiosApp()

@app.post(
    "/users",
    request_model=UserCreateRequest,
    summary="Create new user account",
    description="Creates a new user account (manual validation required)"
)
async def create_user(request, response):
    # Get raw request data
    user_data = await request.json
    
    # Manual validation (if desired)
    try:
        validated_data = UserCreateRequest(**user_data)
        username = validated_data.username
        email = validated_data.email
        password = validated_data.password
    except Exception as e:
        return response.json({"error": "Invalid data", "details": str(e)}, status=400)
    
    # Create user logic here
    return response.json({"id": 123, "username": username}, status=201)
```

## 🔧 Advanced Request Schemas

### Nested Models for Complex Data

Handle complex, hierarchical data structures:

```python
class Address(BaseModel):
    street: str = Field(..., description="Street address")
    city: str = Field(..., description="City name")
    state: str = Field(..., min_length=2, max_length=2, description="State code")
    zip_code: str = Field(..., regex=r'^\d{5}(-\d{4})?$', description="ZIP code")
    country: str = Field("US", description="Country code")

class ContactInfo(BaseModel):
    phone: Optional[str] = Field(None, regex=r'^\+?1?\d{9,15}$', description="Phone number")
    emergency_contact: Optional[str] = Field(None, description="Emergency contact name")

class UserProfileRequest(BaseModel):
    personal_info: dict = Field(..., description="Personal information")
    address: Address = Field(..., description="User's address")
    contact: ContactInfo = Field(..., description="Contact information")
    preferences: dict = Field(default_factory=dict, description="User preferences")

@app.put(
    "/users/{user_id}/profile",
    request_model=UserProfileRequest,
    summary="Update user profile",
    description="Updates user profile with nested address and contact information"
)
async def update_profile(request, response, user_id: int):
    # Get raw request data
    profile_data = await request.json
    
    # Manual validation (if desired)
    try:
        validated_data = UserProfileRequest(**profile_data)
        street = validated_data.address.street
        phone = validated_data.contact.phone
    except Exception as e:
        return response.json({"error": "Invalid profile data"}, status=400)
    
    return response.json({"updated": True})
```

### Custom Business Logic Models

Define models with business logic for manual validation:

```python
from pydantic import validator, root_validator
from typing import List

class OrderRequest(BaseModel):
    items: List[dict] = Field(..., min_items=1, description="Order items")
    shipping_method: str = Field(..., description="Shipping method")
    discount_code: Optional[str] = Field(None, description="Discount code")
    total_amount: float = Field(..., gt=0, description="Total order amount")
    
    @validator('shipping_method')
    def validate_shipping(cls, v):
        allowed_methods = ['standard', 'express', 'overnight']
        if v not in allowed_methods:
            raise ValueError(f'Shipping method must be one of: {allowed_methods}')
        return v
    
    @validator('discount_code')
    def validate_discount(cls, v):
        if v and not v.startswith('SAVE'):
            raise ValueError('Discount codes must start with "SAVE"')
        return v
    
    @root_validator
    def validate_order_total(cls, values):
        items = values.get('items', [])
        total = values.get('total_amount', 0)
        
        # Business logic validation
        calculated_total = sum(item.get('price', 0) * item.get('quantity', 0) for item in items)
        if abs(calculated_total - total) > 0.01:
            raise ValueError('Total amount does not match item prices')
        
        return values

@app.post(
    "/orders",
    request_model=OrderRequest,
    responses={
        201: {"description": "Order created successfully"},
        400: {"description": "Validation errors"},
        422: {"description": "Business rule violations"}
    }
)
async def create_order(request, response):
    # Get raw request data
    order_data = await request.json
    
    # Manual validation using the Pydantic model
    try:
        validated_order = OrderRequest(**order_data)
        # Process validated order
        return response.json({"order_id": 12345}, status=201)
    except Exception as e:
        return response.json({"error": "Order validation failed", "details": str(e)}, status=400)
```

## 📝 Content Type Support

Nexios supports multiple content types for request bodies:

### JSON Requests (Default)

```python
@app.post(
    "/api/data",
    request_model=DataModel,
    request_content_type="application/json"
)
async def handle_json(request, response):
    data = await request.json
    return response.json({"received": True})
```

### Form Data Requests

```python
class ContactForm(BaseModel):
    name: str
    email: EmailStr
    message: str
    subscribe: bool = False

@app.post(
    "/contact",
    request_model=ContactForm,
    request_content_type="application/x-www-form-urlencoded"
)
async def handle_contact_form(request, response):
    form_data = await request.form()
    # Process form submission (manual validation if needed)
    return response.json({"submitted": True})
```

### File Upload with Multipart

```python
from nexios.structs import UploadedFile

class FileUploadRequest(BaseModel):
    title: str = Field(..., description="File title")
    description: Optional[str] = Field(None, description="File description")
    category: str = Field(..., description="File category")
    file: UploadedFile = Field(..., description="File to upload")

@app.post(
    "/files/upload",
    request_model=FileUploadRequest,
    request_content_type="multipart/form-data"
)
async def upload_file(request, response):
    # Get form data and files
    form_data = await request.form()
    files = request.files
    
    # Access file and metadata manually
    file = files.get('file')
    title = form_data.get('title')
    
    if not file or not title:
        return response.json({"error": "File and title required"}, status=400)
    
    # Process file upload
    file_content = await file.read()
    
    return response.json({
        "filename": file.filename,
        "size": len(file_content),
        "title": title
    })
```

## 🎨 Documentation Enhancement

### Field Documentation and Examples

Provide rich documentation for better developer experience:

```python
class ProductRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Product name",
        example="Premium Wireless Headphones"
    )
    price: float = Field(
        ...,
        gt=0,
        le=10000,
        description="Product price in USD",
        example=299.99
    )
    category: str = Field(
        ...,
        description="Product category",
        example="Electronics"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Product tags for search and filtering",
        example=["wireless", "audio", "premium"]
    )
    specifications: dict = Field(
        default_factory=dict,
        description="Technical specifications",
        example={
            "battery_life": "30 hours",
            "connectivity": "Bluetooth 5.0",
            "weight": "250g"
        }
    )

    class Config:
        schema_extra = {
            "example": {
                "name": "Premium Wireless Headphones",
                "price": 299.99,
                "category": "Electronics",
                "tags": ["wireless", "audio", "premium"],
                "specifications": {
                    "battery_life": "30 hours",
                    "connectivity": "Bluetooth 5.0",
                    "weight": "250g"
                }
            }
        }
```

### Conditional Business Logic

Handle different business rules based on context:

```python
class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8)
    current_password: Optional[str] = None
    
    @root_validator
    def validate_password_change(cls, values):
        password = values.get('password')
        current_password = values.get('current_password')
        
        if password and not current_password:
            raise ValueError('Current password required when changing password')
        
        return values

@app.patch(
    "/users/{user_id}",
    request_model=UserUpdateRequest,
    summary="Update user information",
    description="Partial update of user data with conditional business rules"
)
async def update_user(request, response, user_id: int):
    # Get raw request data
    update_data = await request.json
    
    # Manual validation using the model (if desired)
    try:
        validated_data = UserUpdateRequest(**update_data)
        # Handle partial updates with validated data
        return response.json({"updated": True})
    except Exception as e:
        return response.json({"error": "Update validation failed"}, status=400)
```

## ✅ Best Practices

### Model Organization

```python
# models/user.py
class UserBase(BaseModel):
    """Base user fields shared across requests"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr

class UserCreateRequest(UserBase):
    """User creation with password"""
    password: str = Field(..., min_length=8)
    confirm_password: str
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v

class UserUpdateRequest(BaseModel):
    """Partial user updates"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
```

### Manual Error Handling

```python
from pydantic import ValidationError

@app.post("/users", request_model=UserCreateRequest)
async def create_user(request, response):
    try:
        # Get raw request data
        user_data = await request.json
        
        # Manual validation using Pydantic model
        validated_user = UserCreateRequest(**user_data)
        
        # Process user creation with validated data
        return response.json({"created": True}, status=201)
    except ValidationError as e:
        return response.json({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except Exception as e:
        return response.json({
            "error": "Invalid request data"
        }, status=400)
```

### Testing Request Schemas

```python
def test_user_create_schema():
    # Test valid data structure
    valid_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "securepass123"
    }
    user = UserCreateRequest(**valid_data)
    assert user.username == "testuser"
    
    # Test schema validation (for manual validation)
    with pytest.raises(ValidationError):
        UserCreateRequest(username="ab")  # Too short
```

Request schemas are fundamental to building well-documented APIs. They provide the foundation for clear API contracts, comprehensive documentation, and type safety that make your API easier to use and maintain. Remember that in Nexios, these schemas are primarily for documentation - you must implement your own validation logic if you want to validate incoming data.
