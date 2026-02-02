import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Optional

from tortoise import Tortoise, fields, models

from nexios import NexiosApp
from nexios.types import Request, Response, State

# Database configuration
DATABASE_URL = "sqlite://./example_tortoise.db"


# Define models
class Note(models.Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255, index=True)
    content = fields.TextField()
    is_public = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "notes"


# Application lifespan
@asynccontextmanager
async def lifespan(app: NexiosApp) -> AsyncGenerator[State, None]:
    # Startup: Initialize database connection
    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={"models": ["__main__"]},
    )
    # Generate schemas (equivalent to Base.metadata.create_all)
    await Tortoise.generate_schemas()

    yield State()  # Application runs here

    # Cleanup: Close database connections
    await Tortoise.close_connections()


# Initialize app with lifespan
app = NexiosApp(lifespan=lifespan)


@app.post("/notes")
async def create_note(
    request: Request,
    response: Response,
):
    data = await request.json

    note = await Note.create(
        title=data["title"],
        content=data["content"],
        is_public=data.get("is_public", False),
    )

    return response.json(
        {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "is_public": note.is_public,
            "created_at": note.created_at.isoformat(),
            "updated_at": note.updated_at.isoformat(),
        },
        status_code=201,
    )


@app.get("/notes")
async def list_notes(
    request: Request,
    response: Response,
):
    show_private = request.query_params.get("show_private", "false").lower() == "true"

    if show_private:
        notes = await Note.all().order_by("-created_at")
    else:
        notes = await Note.filter(is_public=True).order_by("-created_at")

    return response.json(
        [
            {
                "id": note.id,
                "title": note.title,
                "content": note.content,
                "is_public": note.is_public,
                "created_at": note.created_at.isoformat(),
                "updated_at": note.updated_at.isoformat(),
            }
            for note in notes
        ]
    )


@app.get("/notes/{note_id}")
async def get_note(
    request: Request,
    response: Response,
    note_id: int,
):
    note = await Note.get_or_none(id=note_id)

    if not note:
        return response.json({"error": "Note not found"}, status_code=404)

    if not note.is_public:
        return response.json({"error": "Note is private"}, status_code=403)

    return response.json(
        {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "is_public": note.is_public,
            "created_at": note.created_at.isoformat(),
            "updated_at": note.updated_at.isoformat(),
        }
    )


@app.put("/notes/{note_id}")
async def update_note(
    request: Request,
    response: Response,
    note_id: int,
):
    data = await request.json
    note = await Note.get_or_none(id=note_id)

    if not note:
        return response.json({"error": "Note not found"}, status_code=404)

    # Update fields
    if "title" in data:
        note.title = data["title"]
    if "content" in data:
        note.content = data["content"]
    if "is_public" in data:
        note.is_public = data["is_public"]

    await note.save()

    return response.json(
        {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "is_public": note.is_public,
            "created_at": note.created_at.isoformat(),
            "updated_at": note.updated_at.isoformat(),
        }
    )


@app.delete("/notes/{note_id}")
async def delete_note(
    request: Request,
    response: Response,
    note_id: int,
):
    note = await Note.get_or_none(id=note_id)

    if not note:
        return response.json({"error": "Note not found"}, status_code=404)

    await note.delete()

    return response.json({"message": "Note deleted successfully", "id": note_id})
