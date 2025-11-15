# 📤 Response Models in Nexios

Response models define the structure and content of data your API returns. Nexios uses Pydantic models to provide automatic serialization, comprehensive OpenAPI documentation, and type-safe responses that ensure consistency across your API.

## 🎯 Why Use Response Models?

Response models provide essential benefits for API development:

- **Consistent Output**: Ensures all responses follow the same structure and format
- **Type Safety**: Full IDE support with autocompletion and type checking
- **Clear Documentation**: API consumers know exactly what to expect from each endpoint
- **Automatic Serialization**: Complex objects are automatically converted to JSON
- **Error Standardization**: Consistent error response formats across your API
- **Validation**: Ensures your API returns valid data structures

## 🏗️ Basic Response Models

Define response schemas using Pydantic's `BaseModel`:

```python
from nexios import NexiosApp
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class UserResponse(BaseModel):
    id: int = Field(..., description="Unique user identifier")
    username: str = Field(..., description="User's username")
    email: str = Field(..., description="User's email address")
    full_name: Optional[str] = Field(None, description="User's full name")
    is_active: bool = Field(..., description="Account activation status")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

app = NexiosApp()

@app.get(
    "/users/{user_id}",
    responses={200: UserResponse},
    summary="Get user by ID",
    description="Retrieves detailed information for a specific user"
)
async def get_user(request, response, user_id: int):
    # Fetch user data
    user_data = {
        "id": user_id,
        "username": "johndoe",
        "email": "john@example.com",
        "full_name": "John Doe",
        "is_active": True,
        "created_at": datetime.now(),
        "last_login": datetime.now()
    }
    
    # Return validated response
    user = UserResponse(**user_data)
    return response.json(user.dict())
```

## 🔄 Multiple Response Models

Document different responses for various status codes and scenarios:

```python
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool

class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    code: int = Field(..., description="Error code")
    details: Optional[dict] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")

class ValidationErrorResponse(BaseModel):
    error: str = Field("Validation failed", description="Error type")
    code: int = Field(400, description="HTTP status code")
    field_errors: List[dict] = Field(..., description="Field-specific validation errors")

@app.get(
    "/users/{user_id}",
    responses={
        200: UserResponse,
        404: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        500: ErrorResponse
    },
    summary="Get user with comprehensive error handling"
)
async def get_user_with_errors(request, response, user_id: int):
    try:
        # Simulate different error conditions
        if user_id < 0:
            error = ErrorResponse(
                error="Invalid user ID",
                code=400,
                details={"user_id": user_id, "reason": "Must be positive"}
            )
            return response.json(error.dict(), status=400)
        
        if user_id == 999:
            error = ErrorResponse(
                error="User not found",
                code=404,
                details={"user_id": user_id}
            )
            return response.json(error.dict(), status=404)
        
        # Return successful response
        user = UserResponse(
            id=user_id,
            username="johndoe",
            email="john@example.com",
            is_active=True
        )
        return response.json(user.dict())
        
    except Exception as e:
        error = ErrorResponse(
            error="Internal server error",
            code=500,
            details={"exception": str(e)}
        )
        return response.json(error.dict(), status=500)
```

## 📋 Collection Responses

Handle lists and paginated responses:

```python
class UserListItem(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool

class PaginatedUserResponse(BaseModel):
    users: List[UserListItem] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")

@app.get(
    "/users",
    responses={
        200: PaginatedUserResponse,
        400: ErrorResponse
    },
    summary="List users with pagination"
)
async def list_users(request, response):
    # Get pagination parameters
    page = int(request.query_params.get('page', 1))
    per_page = int(request.query_params.get('per_page', 20))
    
    # Simulate data fetching
    total_users = 150
    users_data = [
        {"id": i, "username": f"user{i}", "email": f"user{i}@example.com", "is_active": True}
        for i in range((page-1)*per_page + 1, min(page*per_page + 1, total_users + 1))
    ]
    
    # Create response
    response_data = PaginatedUserResponse(
        users=[UserListItem(**user) for user in users_data],
        total=total_users,
        page=page,
        per_page=per_page,
        pages=(total_users + per_page - 1) // per_page,
        has_next=page * per_page < total_users,
        has_prev=page > 1
    )
    
    return response.json(response_data.dict())

# Simple list response
@app.get(
    "/users/active",
    responses={200: List[UserListItem]},
    summary="Get all active users"
)
async def get_active_users(request, response):
    users = [
        UserListItem(id=1, username="alice", email="alice@example.com", is_active=True),
        UserListItem(id=2, username="bob", email="bob@example.com", is_active=True)
    ]
    return response.json([user.dict() for user in users])
```

## 🎨 Advanced Response Patterns

### Nested Response Models

Handle complex, hierarchical data:

```python
class AddressResponse(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str
    country: str

class ProfileResponse(BaseModel):
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    website: Optional[str] = None
    social_links: dict = Field(default_factory=dict)

class DetailedUserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    profile: ProfileResponse
    address: Optional[AddressResponse]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "id": 123,
                "username": "johndoe",
                "email": "john@example.com",
                "full_name": "John Doe",
                "profile": {
                    "bio": "Software developer",
                    "avatar_url": "https://example.com/avatar.jpg",
                    "website": "https://johndoe.dev",
                    "social_links": {
                        "twitter": "@johndoe",
                        "github": "johndoe"
                    }
                },
                "address": {
                    "street": "123 Main St",
                    "city": "Anytown",
                    "state": "CA",
                    "zip_code": "12345",
                    "country": "US"
                },
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z"
            }
        }

@app.get(
    "/users/{user_id}/detailed",
    responses={200: DetailedUserResponse, 404: ErrorResponse},
    summary="Get detailed user information"
)
async def get_detailed_user(request, response, user_id: int):
    # Fetch and return detailed user data
    pass
```

### Generic Response Wrappers

Create consistent response formats:

```python
from typing import TypeVar, Generic

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    data: Optional[T] = Field(None, description="Response data")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    request_id: Optional[str] = Field(None, description="Request tracking ID")

class ApiErrorResponse(BaseModel):
    success: bool = Field(False, description="Operation success status")
    error: str = Field(..., description="Error message")
    code: int = Field(..., description="Error code")
    details: Optional[dict] = Field(None, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request tracking ID")

# Usage with generic wrapper
@app.get(
    "/users/{user_id}/wrapped",
    responses={
        200: ApiResponse[UserResponse],
        404: ApiErrorResponse,
        500: ApiErrorResponse
    }
)
async def get_user_wrapped(request, response, user_id: int):
    try:
        user = UserResponse(
            id=user_id,
            username="johndoe",
            email="john@example.com",
            is_active=True,
            created_at=datetime.now()
        )
        
        wrapped_response = ApiResponse[UserResponse](
            success=True,
            message="User retrieved successfully",
            data=user,
            request_id=request.headers.get('X-Request-ID')
        )
        
        return response.json(wrapped_response.dict())
        
    except Exception as e:
        error_response = ApiErrorResponse(
            error="Failed to retrieve user",
            code=500,
            details={"exception": str(e)},
            request_id=request.headers.get('X-Request-ID')
        )
        return response.json(error_response.dict(), status=500)
```

## 🔧 Response Customization

### Custom Serialization

Handle special data types and formats:

```python
from decimal import Decimal
from enum import Enum

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"

class AccountResponse(BaseModel):
    id: int
    balance: Decimal = Field(..., description="Account balance")
    status: UserStatus = Field(..., description="Account status")
    created_at: datetime
    
    class Config:
        # Custom JSON encoders
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat()
        }
        
        # Allow enum values in schema
        use_enum_values = True

@app.get(
    "/accounts/{account_id}",
    responses={200: AccountResponse},
    summary="Get account information"
)
async def get_account(request, response, account_id: int):
    account = AccountResponse(
        id=account_id,
        balance=Decimal('1234.56'),
        status=UserStatus.ACTIVE,
        created_at=datetime.now()
    )
    return response.json(account.dict())
```

### Response Headers

Document custom response headers:

```python
@app.get(
    "/users/{user_id}/download",
    responses={
        200: {
            "description": "User data export",
            "content": {
                "application/json": {
                    "schema": UserResponse.schema()
                }
            },
            "headers": {
                "X-Export-Format": {
                    "description": "Export format used",
                    "schema": {"type": "string"}
                },
                "X-Record-Count": {
                    "description": "Number of records exported",
                    "schema": {"type": "integer"}
                }
            }
        }
    }
)
async def export_user_data(request, response, user_id: int):
    user_data = UserResponse(
        id=user_id,
        username="johndoe",
        email="john@example.com",
        is_active=True,
        created_at=datetime.now()
    )
    
    # Set custom headers
    response.headers['X-Export-Format'] = 'json'
    response.headers['X-Record-Count'] = '1'
    
    return response.json(user_data.dict())
```

## ✅ Best Practices

### Model Organization

```python
# models/responses.py
class BaseResponse(BaseModel):
    """Base response with common fields"""
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = None

class UserBaseResponse(BaseResponse):
    """Base user response fields"""
    id: int
    username: str
    email: str

class UserSummaryResponse(UserBaseResponse):
    """Minimal user information"""
    is_active: bool

class UserDetailResponse(UserBaseResponse):
    """Complete user information"""
    full_name: Optional[str]
    profile: ProfileResponse
    created_at: datetime
    updated_at: datetime
```

### Error Response Consistency

```python
class StandardErrorResponse(BaseModel):
    error: str
    code: int
    message: str
    details: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @classmethod
    def not_found(cls, resource: str, id: Any):
        return cls(
            error="NOT_FOUND",
            code=404,
            message=f"{resource} with id {id} not found",
            details={"resource": resource, "id": str(id)}
        )
    
    @classmethod
    def validation_error(cls, errors: List[dict]):
        return cls(
            error="VALIDATION_ERROR",
            code=400,
            message="Request validation failed",
            details={"field_errors": errors}
        )
```

### Testing Response Models

```python
def test_user_response_serialization():
    user_data = {
        "id": 123,
        "username": "testuser",
        "email": "test@example.com",
        "is_active": True,
        "created_at": datetime.now()
    }
    
    user_response = UserResponse(**user_data)
    json_data = user_response.dict()
    
    assert json_data["id"] == 123
    assert json_data["username"] == "testuser"
    assert "created_at" in json_data

def test_error_response_factory():
    error = StandardErrorResponse.not_found("User", 123)
    assert error.code == 404
    assert "User with id 123 not found" in error.message
```

Response models are crucial for creating consistent, well-documented APIs. They ensure that your API returns predictable data structures and provide clear contracts for API consumers, making integration easier and more reliable.
