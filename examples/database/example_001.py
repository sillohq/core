import sqlite3
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from nexios import Depends, NexiosApp
from nexios.types import Request, Response, State

# Database setup
DB_PATH = "example.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            completed BOOLEAN NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        )


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    async def connect(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            init_db()

    async def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def get_connection(self) -> sqlite3.Connection:
        if self.conn is None:
            raise RuntimeError("Database is not connected")
        return self.conn


# Application lifespan
@asynccontextmanager
async def lifespan(app: NexiosApp) -> AsyncGenerator[State, None]:
    # Startup: Initialize database connection
    db = Database(DB_PATH)
    await db.connect()

    # Make database available to routes
    state = State()
    state.db = db

    yield state  # Application runs here

    # Cleanup: Close database connection
    await db.close()


app = NexiosApp(lifespan=lifespan)


# Dependency to get database connection
async def get_db(state: State) -> Database:
    return state.db


@app.get("/todos")
async def list_todos(
    request: Request, response: Response, db: Database = Depends(get_db)
) -> Response:
    conn = db.get_connection()
    todos = conn.execute("SELECT * FROM todos ORDER BY created_at DESC").fetchall()
    return response.json(
        [
            {
                "id": todo["id"],
                "title": todo["title"],
                "completed": bool(todo["completed"]),
                "created_at": todo["created_at"],
            }
            for todo in todos
        ]
    )


@app.post("/todos")
async def create_todo(
    request: Request, response: Response, db: Database = Depends(get_db)
) -> Response:
    data = await request.json
    title = data.get("title")

    if not title:
        return response.json({"error": "Title is required"}, status_code=400)

    conn = db.get_connection()
    cursor = conn.execute("INSERT INTO todos (title) VALUES (?)", (title,))
    conn.commit()

    # Get the created todo
    todo = conn.execute(
        "SELECT * FROM todos WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()

    return response.json(
        {
            "id": todo["id"],
            "title": todo["title"],
            "completed": bool(todo["completed"]),
            "created_at": todo["created_at"],
        },
        status_code=201,
    )


@app.put("/todos/{todo_id}")
async def update_todo(
    request: Request, response: Response, todo_id: str, db: Database = Depends(get_db)
) -> Response:
    data = await request.json
    conn = db.get_connection()

    # Check if todo exists
    todo = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()

    if not todo:
        return response.json({"error": "Todo not found"}, status_code=404)

    # Update fields
    updates = []
    values = []
    if "title" in data:
        updates.append("title = ?")
        values.append(data["title"])
    if "completed" in data:
        updates.append("completed = ?")
        values.append(1 if data["completed"] else 0)

    if updates:
        values.append(todo_id)
        conn.execute(f"UPDATE todos SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()

    # Get updated todo
    todo = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()

    return response.json(
        {
            "id": todo["id"],
            "title": todo["title"],
            "completed": bool(todo["completed"]),
            "created_at": todo["created_at"],
        }
    )


@app.delete("/todos/{todo_id}")
async def delete_todo(
    request: Request, response: Response, todo_id: str, db: Database = Depends(get_db)
) -> Response:
    conn = db.get_connection()

    # Check if todo exists
    todo = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()

    if not todo:
        return response.json({"error": "Todo not found"}, status_code=404)

    # Delete todo
    conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    conn.commit()

    return response.json({"message": "Todo deleted successfully", "id": todo_id})
