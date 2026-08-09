"""Advanced validation with sillo's built-in Pydantic engine.

Everything here is framework-native: request bodies, path and query
parameters, form uploads, and response shaping. No middleware, no manual
try/except around ValidationError, and no type annotations required.

JSON bodies are declared once on the decorator with ``request_model=`` and
injected into the handler's first plain parameter. Every other location uses a
marker, with the type on the marker itself.

Run with:  uvicorn 01_advanced:app --reload
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, constr

from sillo import File, Form, Path, Query, SilloApp

app = SilloApp(title="Validation Example", version="1.0.0")


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


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


class UserResponse(BaseModel):
    """Note the absence of ``password`` — response_model drops it for us."""

    id: int
    username: str
    email: EmailStr
    full_name: str
    birth_date: Optional[date] = None
    role: UserRole
    status: UserStatus
    created_at: datetime


# ---------------------------------------------------------------------------
# Request body validation
# ---------------------------------------------------------------------------


@app.post("/users", request_model=UserCreate, response_model=UserResponse)
async def create_user(request, response, user):
    """Validate the body against UserCreate and shape the reply as UserResponse.

    A bad payload never reaches this function; it returns 422 with the failing
    fields under ``loc: ["body", ...]``. The password is present on ``user``
    but is dropped on the way out because UserResponse does not declare it.
    """
    return {"id": 1, **user.model_dump(), "created_at": datetime.now()}


@app.put("/users/{user_id}", request_model=UserUpdate, response_model=UserResponse)
async def update_user(request, response, changes, user_id=Path(type=int)):
    """Combine a validated path parameter with a partial body model."""
    user = {
        "id": user_id,
        "username": "existing_user",
        "email": "user@example.com",
        "full_name": "Existing User",
        "birth_date": date(1990, 1, 1),
        "role": UserRole.USER,
        "status": UserStatus.ACTIVE,
        "created_at": datetime.now(),
    }
    user.update(changes.model_dump(exclude_unset=True))
    return user


# ---------------------------------------------------------------------------
# Query parameter validation
# ---------------------------------------------------------------------------


@app.get("/users", response_model=UserResponse, response_model_many=True)
async def list_users(
    request,
    response,
    page=Query(1, type=int, ge=1, description="Page number"),
    limit=Query(10, type=int, ge=1, le=100, description="Items per page"),
    roles=Query([], type=List[UserRole], description="Filter by role"),
    order=Query("desc", type=str, pattern="^(asc|desc)$"),
):
    """Constraints are enforced and published to OpenAPI from one declaration.

    ``?page=0`` returns 422 rather than a 500 or a silently wrong query, and
    ``?roles=admin&roles=user`` arrives as a list of validated enum members.
    """
    return [
        {
            "id": i,
            "username": f"user{i}",
            "email": f"user{i}@example.com",
            "full_name": f"User {i}",
            "role": roles[0] if roles else UserRole.USER,
            "status": UserStatus.ACTIVE,
            "created_at": datetime.now(),
        }
        for i in range(1, limit + 1)
    ]


# ---------------------------------------------------------------------------
# Forms and uploads
# ---------------------------------------------------------------------------


class Credentials(BaseModel):
    username: str
    password: constr(min_length=8)


class Token(BaseModel):
    access_token: str
    expires_in: int = Field(description="Lifetime in seconds")


@app.post("/login", request_model=Credentials, response_model=Token)
async def login(request, response, creds):
    """request_model composes with everything — here it is the only input."""
    return {"access_token": f"token-for-{creds.username}", "expires_in": 3600}


@app.post("/users/{user_id}/avatar")
async def upload_avatar(
    request,
    response,
    user_id=Path(type=int),
    caption=Form("", type=str, max_length=140),
    avatar=File(..., description="Profile image"),
):
    """Declaring Form/File switches the route to multipart parsing."""
    content = await avatar.read()
    return {
        "user_id": user_id,
        "caption": caption,
        "filename": avatar.filename,
        "content_type": avatar.content_type,
        "size": len(content),
    }
