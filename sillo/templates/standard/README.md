# {{project_name_title}}

A full-featured sillo application with authentication, CORS, and database integration.

## Features

- REST API endpoints with CRUD operations
- Basic authentication middleware
- CORS support
- Error handling
- SQLite database integration (async)
- API documentation (Swagger UI and ReDoc)

## Getting Started

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python main.py
   ```
   
   Or using the sillo CLI:
   ```bash
   sillo run
   ```

3. Access the API documentation:
   - Swagger UI: http://localhost:4000/docs
   - ReDoc: http://localhost:4000/redoc

## Project Structure

```
{{project_name}}
├── main.py           # Main application file
├── requirements.txt  # Project dependencies
├── README.md        # Project documentation
└── .gitignore       # Git ignore file
```

## API Endpoints

- `GET /`: Welcome message
- `GET /items`: List all items
- `GET /items/{item_id}`: Get a specific item
- `POST /items`: Create a new item
- `DELETE /items/{item_id}`: Delete an item

## Authentication

The API uses basic authentication. Include an `Authorization` header with your requests:

```
Authorization: Bearer your-token-here
```

## Development

To run the application in development mode with auto-reload:

```bash
sillo run --reload
```

## License

This project is licensed under the MIT License.

