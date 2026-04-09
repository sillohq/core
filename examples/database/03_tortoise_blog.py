from tortoise import Model, Tortoise, fields
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.expressions import Q
from tortoise.functions import Count

from nexios import NexiosApp
from nexios.http import Request, Response

app = NexiosApp()


# Define Tortoise ORM models
class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    email = fields.CharField(max_length=100, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    # Reverse relation to posts
    posts: fields.ReverseRelation["BlogPost"]

    class Meta:
        table = "users"


class BlogPost(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=200)
    content = fields.TextField()
    is_published = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    # Foreign key to User
    author = fields.ForeignKeyField("models.User", related_name="posts")

    # Many-to-many relationship with tags
    tags: fields.ManyToManyRelation["Tag"] = fields.ManyToManyField(
        "models.Tag", related_name="posts"
    )

    class Meta:
        table = "blog_posts"


class Tag(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, unique=True)

    # Reverse relation to posts
    posts: fields.ManyToManyRelation[BlogPost]

    class Meta:
        table = "tags"


# Create Pydantic models for validation and serialization
User_Pydantic = pydantic_model_creator(User, name="User")
UserCreate_Pydantic = pydantic_model_creator(
    User, name="UserCreate", exclude_readonly=True
)

BlogPost_Pydantic = pydantic_model_creator(BlogPost, name="BlogPost")
BlogPostCreate_Pydantic = pydantic_model_creator(
    BlogPost, name="BlogPostCreate", exclude_readonly=True
)

Tag_Pydantic = pydantic_model_creator(Tag, name="Tag")


# Initialize Tortoise ORM
@app.on_startup
async def init_db():
    await Tortoise.init(db_url="sqlite://db.sqlite3", modules={"models": ["__main__"]})
    await Tortoise.generate_schemas()


@app.on_shutdown
async def close_db():
    await Tortoise.close_connections()


# API Routes
@app.post("/users")
async def create_user(request: Request, response: Response) -> Response:
    data = await request.json
    user = await User.create(**data)
    return response.json(await User_Pydantic.from_tortoise_orm(user))


@app.get("/users/{user_id}/posts")
async def get_user_posts(request: Request, response: Response) -> Response:
    user_id = request.path_params["user_id"]
    user = await User.get_or_none(id=user_id)

    if not user:
        return response.json({"error": "User not found"}, status_code=404)

    posts = await BlogPost.filter(author=user).prefetch_related("tags")
    return response.json(
        [
            {
                "id": post.id,
                "title": post.title,
                "content": post.content,
                "is_published": post.is_published,
                "tags": [tag.name for tag in post.tags],
                "created_at": post.created_at.isoformat(),
                "updated_at": post.updated_at.isoformat(),
            }
            for post in posts
        ]
    )


@app.post("/posts")
async def create_post(request: Request, response: Response) -> Response:
    data = await request.json
    user = await User.get_or_none(id=data["author_id"])

    if not user:
        return response.json({"error": "Author not found"}, status_code=404)

    # Create post
    post = await BlogPost.create(
        title=data["title"],
        content=data["content"],
        is_published=data.get("is_published", False),
        author=user,
    )

    # Handle tags
    if "tags" in data:
        for tag_name in data["tags"]:
            tag, _ = await Tag.get_or_create(name=tag_name.lower())
            await post.tags.add(tag)

    # Fetch post with related data
    await post.fetch_related("tags")
    return response.json(
        {
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "is_published": post.is_published,
            "author": {"id": user.id, "username": user.username},
            "tags": [tag.name for tag in post.tags],
            "created_at": post.created_at.isoformat(),
            "updated_at": post.updated_at.isoformat(),
        },
        status_code=201,
    )


@app.get("/posts/search")
async def search_posts(request: Request, response: Response) -> Response:
    query = request.query_params.get("q", "")
    tag = request.query_params.get("tag")
    published_only = request.query_params.get("published", "true").lower() == "true"

    # Build query
    filters = Q()
    if query:
        filters |= Q(title__icontains=query) | Q(content__icontains=query)
    if tag:
        filters &= Q(tags__name=tag.lower())
    if published_only:
        filters &= Q(is_published=True)

    # Execute query with related data
    posts = await BlogPost.filter(filters).prefetch_related("author", "tags")

    return response.json(
        [
            {
                "id": post.id,
                "title": post.title,
                "content": post.content,
                "is_published": post.is_published,
                "author": {"id": post.author.id, "username": post.author.username},
                "tags": [tag.name for tag in post.tags],
                "created_at": post.created_at.isoformat(),
                "updated_at": post.updated_at.isoformat(),
            }
            for post in posts
        ]
    )


@app.get("/tags/popular")
async def get_popular_tags(request: Request, response: Response) -> Response:
    # Get tags with post count, ordered by popularity
    tags = await Tag.all().annotate(post_count=Count("posts")).order_by("-post_count")

    return response.json(
        [{"id": tag.id, "name": tag.name, "post_count": tag.post_count} for tag in tags]
    )
