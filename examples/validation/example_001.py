from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ValidationError, constr

from nexios import NexiosApp
from nexios.http import Request, Response

app = NexiosApp()


# Enums for validation
class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


# Request Models
class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=50)
    email: EmailStr
    password: constr(min_length=8)
    full_name: str
    birth_date: Optional[date] = None
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.ACTIVE


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    birth_date: Optional[date] = None
    status: Optional[UserStatus] = None


# Response Models
class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: str
    birth_date: Optional[date]
    role: UserRole
    status: UserStatus
    created_at: datetime


# Custom validation middleware
class ValidationMiddleware:
    def __init__(self, request_model=None, response_model=None):
        self.request_model = request_model
        self.response_model = response_model

    def __call__(self, handler):
        async def wrapper(request, response):
            # Validate request data if model is provided
            if self.request_model:
                try:
                    data = await request.json
                    validated_data = self.request_model(**data)
                    request.validated_data = validated_data
                except ValidationError as e:
                    return response.json(
                        {"error": "Validation error", "details": e.errors()},
                        status_code=422,
                    )

            # Call handler
            result = await handler(request, response)

            # Validate response data if model is provided
            if self.response_model and not isinstance(result, Response):
                try:
                    validated_response = self.response_model(**result)
                    return response.json(validated_response.dict())
                except ValidationError:
                    return response.json(
                        {"error": "Response validation error"}, status_code=500
                    )

            return result

        return wrapper


# Example routes with validation
@app.post("/users")
@ValidationMiddleware(request_model=UserCreate, response_model=UserResponse)
async def create_user(request: Request, response: Response) -> dict:
    data = request.validated_data

    # Simulate user creation
    user = {"id": 1, **data.dict(), "created_at": datetime.now()}

    return user


@app.put("/users/{user_id}")
@ValidationMiddleware(request_model=UserUpdate, response_model=UserResponse)
async def update_user(request: Request, response: Response) -> dict:
    user_id = request.path_params["user_id"]
    data = request.validated_data

    # Simulate user update
    user = {
        "id": int(user_id),
        "username": "existing_user",
        "email": "user@example.com",
        "full_name": "Existing User",
        "birth_date": date(1990, 1, 1),
        "role": UserRole.USER,
        "status": UserStatus.ACTIVE,
        "created_at": datetime.now(),
    }

    # Update fields
    for field, value in data.dict(exclude_unset=True).items():
        user[field] = value

    return user


# Example of validation with query parameters
class PaginationParams(BaseModel):
    page: int = Field(ge=1, default=1)
    limit: int = Field(ge=1, le=100, default=10)
    sort_by: str = Field(default="created_at")
    order: str = Field(default="desc")


@app.get("/users")
async def list_users(request: Request, response: Response) -> Response:
    try:
        # Validate query parameters
        params = PaginationParams(
            page=int(request.query_params.get("page", 1)),
            limit=int(request.query_params.get("limit", 10)),
            sort_by=request.query_params.get("sort_by", "created_at"),
            order=request.query_params.get("order", "desc"),
        )
    except ValidationError as e:
        return response.json(
            {"error": "Invalid query parameters", "details": e.errors()},
            status_code=422,
        )

    # Simulate paginated response
    users = [
        {
            "id": i,
            "username": f"user{i}",
            "email": f"user{i}@example.com",
            "full_name": f"User {i}",
            "role": UserRole.USER,
            "status": UserStatus.ACTIVE,
            "created_at": datetime.now(),
        }
        for i in range(1, 6)
    ]

    return response.json(
        {
            "items": users,
            "total": len(users),
            "page": params.page,
            "limit": params.limit,
        }
    )
