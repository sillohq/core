from nexios import NexiosApp
from nexios.routing import Routes

app = NexiosApp()


# GET /users
async def get_users(req, res):
    return res.json({"message": "List of users"})


# GET /users/:user_id
async def get_user(req, res, user_id):
    return res.json({"user_id": user_id})


# POST /users
async def create_user(req, res):
    return res.json({"message": "User created"})


# PUT /users/:user_id
async def update_user(req, res, user_id):
    return res.json({"user_id": user_id})


# DELETE /users/:user_id
async def delete_user(req, res, user_id):
    return res.json({"user_id": user_id})


app.add_route(Routes("/users", get_users, methods=["GET"]))
app.add_route(Routes("/users/{user_id}", get_user, methods=["GET"]))
app.add_route(Routes("/users", create_user, methods=["POST"]))
app.add_route(Routes("/users/{user_id}", update_user, methods=["PUT"]))
app.add_route(Routes("/users/{user_id}", delete_user, methods=["DELETE"]))
