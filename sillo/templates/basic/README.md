# {{project_name_title}}

A modern web application built with the sillo framework.

## Features

- High performance ASGI-based web server
- Modern Python async code
- Easy API development
- Flexible configuration

## Getting Started

### Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

### Running the Application

Start the development server:

```bash
sillo run
```

Or with custom settings:

```bash
sillo run --host 0.0.0.0 --port 8000
```

Alternatively:

```bash
python -m uvicorn main:app --reload
```

The application will be available at http://127.0.0.1:4000

## Project Structure

```
{{project_name}}/
├── main.py           # Application entry point
├── requirements.txt  # Project dependencies
└── .env              # Environment variables
```

## API Documentation

Once the server is running, visit:

- http://127.0.0.1:8000/docs - OpenAPI documentation

## Development

This project was created using the sillo CLI. For more information about sillo, visit:
https://sillo-labs.gitbook.io/sillo
