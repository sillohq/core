"""
sillo test application — Recorder Admin with SQLite, auto-migration, default admin user.

Run: uvicorn test_app:app --reload
Visit: http://localhost:8000/admin/
Login: admin@admin.com / admin
"""
from sillo.session import SessionMiddleware

from sillo import silloApp
from sillo.services.admin import setup_admin, ModelAdmin
from sillo.services.admin.models import AdminUser, AdminRole, AdminActivity
from sillo.record import setup_record, DatabaseConfig, Model
from sillo.session import SessionConfig, SessionMiddleware
from tortoise import fields

app = silloApp(title="Sillo Demo")

# ── Session middleware (required for admin auth) ──────────────────────

db = setup_record(app, DatabaseConfig.sqlite("demo.db"), model_modules=[__name__])

# ── Models ────────────────────────────────────────────────────────────

class User(Model):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True)
    name = fields.CharField(max_length=100, null=True)
    is_active = fields.BooleanField(default=True)
    plan = fields.CharField(max_length=50, default="free")

class Post(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=200)
    content = fields.TextField(null=True)
    published = fields.BooleanField(default=False)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField("models.User", related_name="posts")

# ── Startup: auto-create admin role + user ────────────────────────────

@app.on_startup
async def seed_admin():
    from sillo.helpers.hashing import hash_password

    role = await AdminRole.get_or_none(slug="super-admin")
    if not role:
        role = await AdminRole.create(name="Super Admin", slug="super-admin", permissions=["*"])

    if not await AdminUser.get_or_none(email="admin@admin.com"):
        await AdminUser.create(
            email="admin@admin.com", username="admin",
            password_hash=hash_password("admin"),
            is_active=True, is_superuser=True, role=role,
        )
        print("[startup] Default admin created: admin@admin.com / admin")

# ── Admin ─────────────────────────────────────────────────────────────

admin = setup_admin(app, title="Sillo Admin", prefix="/admin")
app.use(SessionMiddleware(secret_key="bocdldlcbldbl"))

@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ["id", "email", "name", "is_active", "plan", "created_at"]
    search_fields = ["email", "name"]
    ordering = ["-created_at"]

@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["id", "title", "user_id", "published", "created_at"]
    search_fields = ["title", "content"]
    ordering = ["-created_at"]

@admin.register(AdminUser)
class AdminUserAdmin(ModelAdmin):
    list_display = ["id", "email", "username", "is_active", "is_superuser", "last_login"]
    search_fields = ["email", "username"]

@admin.register(AdminRole)
class AdminRoleAdmin(ModelAdmin):
    list_display = ["id", "name", "slug", "created_at"]
    search_fields = ["name"]

@admin.register(AdminActivity)
class AdminActivityAdmin(ModelAdmin):
    list_display = ["id", "user_email", "action", "model_name", "created_at"]
    ordering = ["-created_at"]

@app.get("/")
async def home(request, response):
    return response.json({"app": "Sillo Demo", "admin": "/admin/"})

@app.get("/test")
async def home(request, response):
    return response.json({"app": "Sillo Demo", "admin": "/admin/","posts":Post.all().values()})

app.use(SessionMiddleware(
    secret_key="bocdldlcbldbl"
))
