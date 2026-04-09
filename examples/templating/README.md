# Nexios Templating Examples

This directory contains examples demonstrating various features of the Nexios templating system, which is built on top of Jinja2.

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Create the template directory structure:
```bash
mkdir -p templates/components templates/pages templates/blog
```

## Examples

### 1. Basic Template Usage (01_basic.py)
- Basic template configuration
- Async template rendering
- Context passing
- URL parameter handling

### 2. Template Inheritance (02_inheritance.py)
- Template inheritance with base templates
- Component includes
- Template blocks
- Basic filters

### 3. Advanced Features (03_custom_filters.py)
- Custom template filters
- Global template variables
- Markdown rendering
- Number formatting
- Date/time handling

## Template Structure

The examples expect the following template files:

```
templates/
├── base.html                 # Base template with common structure
├── components/
│   ├── header.html          # Reusable header component
│   └── footer.html          # Reusable footer component
├── pages/
│   ├── home.html            # Home page template
│   └── blog_post.html       # Blog post template
└── blog/
    └── list.html            # Blog listing template
```

## Running the Examples

Each example can be run directly:

```bash
python 01_basic.py  # Basic example
python 02_inheritance.py  # Inheritance example
python 03_custom_filters.py  # Advanced features
```

The server will start on `http://localhost:8000`

## Key Features Demonstrated

1. Template Configuration
   - Custom template directories
   - Auto-reload for development
   - Whitespace control
   - Async rendering

2. Template Inheritance
   - Base templates
   - Block overriding
   - Component inclusion
   - Template organization

3. Filters and Functions
   - Built-in Jinja2 filters
   - Custom filters
   - Global variables
   - Date formatting
   - Markdown rendering
   - Number humanization 