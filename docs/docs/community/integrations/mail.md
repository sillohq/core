# Mail Integration

The Nexios Mail contrib module provides a comprehensive email sending solution with SMTP support, template integration, and background task processing.

## Overview

Nexios Mail is a powerful and easy-to-use email sending solution for Nexios applications that includes:

- **SMTP Support**: Full SMTP configuration with TLS/SSL support
- **Template Integration**: Jinja2-based HTML email templates
- **Background Tasks**: Async email sending with nexios-contrib tasks
- **Dependency Injection**: Easy integration with Nexios applications
- **Multiple Providers**: Pre-configured settings for Gmail, Outlook, SendGrid
- **Attachments**: Support for file attachments and inline images
- **Error Handling**: Comprehensive error reporting and logging

## Installation

```bash
# Basic installation
pip install nexios-contrib[mail]

# With template support
pip install nexios-contrib[mail,templating]

# With all features
pip install nexios-contrib[all]
```

## Direct MailClient Usage

The most straightforward way to send emails is by using the `MailClient` class directly. This approach gives you full control over the email sending process without requiring dependency injection.

### Creating a MailClient

```python
from nexios_contrib.mail import MailClient, MailConfig

# Create with default configuration (uses environment variables)
mail_client = MailClient()

# Or with explicit configuration
config = MailConfig(
    smtp_host="smtp.gmail.com",
    smtp_port=587,
    smtp_username="your-email@gmail.com",
    smtp_password="your-app-password",
    use_tls=True,
    default_from="Your Name <your-email@gmail.com>"
)
mail_client = MailClient(config=config)
```

### Basic Email Sending

```python
import asyncio

async def send_basic_email():
    # Start the client (establishes SMTP connection)
    await mail_client.start()
    
    try:
        # Send a simple email
        result = await mail_client.send_email(
            to="recipient@example.com",
            subject="Hello World",
            body="This is a plain text email",
            html_body="<h1>Hello World</h1><p>This is an HTML email.</p>"
        )
        
        if result.success:
            print(f"Email sent successfully! Message ID: {result.message_id}")
        else:
            print(f"Failed to send email: {result.error}")
    
    finally:
        # Always stop the client to close connections
        await mail_client.stop()

# Run the async function
asyncio.run(send_basic_email())
```

### Using Templates

Create templates in your `templates/emails/` directory:

**templates/emails/welcome.html**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Welcome {{ name }}!</title>
</head>
<body>
    <h1>Welcome {{ name }}!</h1>
    <p>Thank you for joining {{ company_name }}.</p>
    <p>Your account has been created with email: {{ email }}</p>
    <a href="{{ activation_url }}">Activate Your Account</a>
</body>
</html>
```

**templates/emails/welcome.txt**
```text
Welcome {{ name }}!

Thank you for joining {{ company_name }}.
Your account has been created with email: {{ email }}.

Activate Your Account: {{ activation_url }}
```

Send template emails:

```python
async def send_template_email():
    config = MailConfig(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_username="your-email@gmail.com",
        smtp_password="your-app-password",
        use_tls=True,
        template_directory="templates/emails"
    )
    mail_client = MailClient(config=config)
    
    await mail_client.start()
    
    try:
        result = await mail_client.send_template_email(
            to="newuser@example.com",
            subject="Welcome to Our Platform!",
            template_name="welcome",
            context={
                "name": "John Doe",
                "email": "newuser@example.com",
                "company_name": "Acme Corp",
                "activation_url": "https://example.com/activate/12345"
            }
        )
        
        print(f"Template email sent: {result.success}")
    
    finally:
        await mail_client.stop()

asyncio.run(send_template_email())
```

### Advanced Message Creation

For more control, create `EmailMessage` objects directly:

```python
from nexios_contrib.mail import EmailMessage

async def send_advanced_email():
    config = MailConfig(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_username="your-email@gmail.com",
        smtp_password="your-app-password",
        use_tls=True
    )
    mail_client = MailClient(config=config)
    
    await mail_client.start()
    
    try:
        # Create a detailed email message
        message = EmailMessage(
            to="recipient@example.com",
            subject="Advanced Email",
            body="Plain text content",
            html_body="<h1>HTML Content</h1>",
            cc="manager@example.com",
            bcc="archive@example.com"
        )
        
        # Add custom headers
        message.add_header("X-Campaign-ID", "summer-2024")
        message.add_header("X-Mailer", "Nexios Mail")
        
        # Add attachments
        message.add_attachment("report.pdf", b"PDF content", "application/pdf")
        
        # Send the message
        result = await mail_client.send_message(message)
        print(f"Advanced email sent: {result.success}")
    
    finally:
        await mail_client.stop()

asyncio.run(send_advanced_email())
```

## Integration with Nexios Applications

While direct MailClient usage is simple, integrating with Nexios applications provides additional benefits like automatic lifecycle management and dependency injection.

### Application Setup

For Nexios applications, use the `setup_mail` function for automatic lifecycle management:

```python
from nexios import NexiosApp
from nexios_contrib.mail import setup_mail, MailConfig

app = NexiosApp()

# Setup with environment variables
mail_client = setup_mail(app)

# Or with custom configuration
config = MailConfig(
    smtp_host="smtp.gmail.com",
    smtp_port=587,
    smtp_username="your-email@gmail.com",
    smtp_password="your-app-password",
    use_tls=True,
    default_from="Your Name <your-email@gmail.com>"
)
mail_client = setup_mail(app, config=config)
```

### Environment Variables

```bash
# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
SMTP_USE_SSL=false

# Email Defaults
MAIL_DEFAULT_FROM=Your Name <your-email@gmail.com>
MAIL_DEFAULT_REPLY_TO=support@yourcompany.com

# Template Directory
MAIL_TEMPLATE_DIR=templates/emails

# Debug Settings
MAIL_DEBUG=false
MAIL_SUPPRESS_SEND=false
```

### Dependency Injection

For cleaner code in your route handlers, use dependency injection:

```python
from nexios.http import Request, Response
from nexios_contrib.mail import MailDepend

@app.post("/send-email")
async def send_email(
    request: Request,
    response: Response,
    mail_client: MailClient = MailDepend()
):
    result = await mail_client.send_email(
        to="user@example.com",
        subject="Welcome to Our Service",
        body="Thank you for joining our platform!",
        html_body="<h1>Welcome!</h1><p>Thank you for joining our platform!</p>"
    )
    
    return response.json({
        "success": result.success,
        "message_id": result.message_id,
        "sent_at": result.sent_at.isoformat()
    })
```

### Getting MailClient from Request

Alternatively, get the mail client directly from the request:

```python
from nexios_contrib.mail import get_mail_from_request

@app.post("/send-email-manual")
async def send_email_manual(request: Request, response: Response):
    mail_client = get_mail_from_request(request)
    
    result = await mail_client.send_email(
        to="user@example.com",
        subject="Welcome to Our Service",
        body="Thank you for joining our platform!"
    )
    
    return response.json({"success": result.success, "message_id": result.message_id})
```

### Background Email Sending

Send emails asynchronously without blocking your API responses:

```python
from nexios_contrib.mail import send_email_async

@app.post("/send-async")
async def send_async_email(
    request: Request,
    response: Response
):
    task = await send_email_async(
        request=request,
        to="user@example.com",
        subject="Processing Your Request",
        body="We're processing your request and will notify you when complete."
    )
    
    return response.json({
        "message": "Email queued for sending",
        "task_id": task.id if task else None
    })
```

## Configuration

### Provider-Specific Configurations

#### Gmail
```python
config = MailConfig.for_gmail(
    username="your-email@gmail.com",
    password="your-app-password",  # Use app password, not regular password
    default_from="Your Name <your-email@gmail.com>"
)
```

#### Outlook/Office 365
```python
config = MailConfig.for_outlook(
    username="your-email@outlook.com",
    password="your-password",
    default_from="Your Name <your-email@outlook.com>"
)
```

#### SendGrid
```python
config = MailConfig.for_sendgrid(
    api_key="your-sendgrid-api-key",
    default_from="your-email@yourdomain.com"
)
```

## Advanced Features

### Custom Email Messages

```python
from nexios_contrib.mail import EmailMessage

# Create detailed email message
message = EmailMessage(
    to="recipient@example.com",
    subject="Custom Email",
    body="Plain text content",
    html_body="<h1>HTML Content</h1>",
    cc="manager@example.com",
    bcc="archive@example.com",
    priority=1  # High priority
)

# Add custom headers
message.add_header("X-Campaign-ID", "summer-2024")
message.add_header("X-Mailer", "Nexios Mail")

# Add attachments
message.add_attachment("report.pdf", b"PDF content", "application/pdf")

# Send the message
result = await mail_client.send_message(message)
```

### Template Custom Filters

```python
# Add custom Jinja2 filters
def format_currency(value, currency="USD"):
    return f"{value:.2f} {currency}"

# In your mail client setup
mail_client._template_env.filters["currency"] = format_currency

# Use in templates
{{ price | currency }}
```

## API Reference

### MailClient

The main mail client class for sending emails.

#### Methods

- `send_email(to, subject, body=None, html_body=None, **kwargs)` - Send an email
- `send_message(message)` - Send an EmailMessage object
- `send_template_email(to, subject, template_name, context=None, **kwargs)` - Send template email
- `create_message(to, subject, **kwargs)` - Create EmailMessage object

### EmailMessage

Represents an email message with all its components.

#### Properties

- `to` - Recipient email addresses
- `subject` - Email subject
- `body` - Plain text body
- `html_body` - HTML body
- `attachments` - List of attachments
- `headers` - Custom headers

#### Methods

- `add_attachment(filename, content, content_type=None, content_id=None)` - Add attachment
- `set_template(template_name, context=None)` - Set template
- `add_header(name, value)` - Add custom header

### MailConfig

Configuration for the mail client.

#### Class Methods

- `for_gmail(username, password, **kwargs)` - Gmail configuration
- `for_outlook(username, password, **kwargs)` - Outlook configuration
- `for_sendgrid(api_key, **kwargs)` - SendGrid configuration

## Best Practices

### Security

1. **Never hardcode credentials** - Always use environment variables
2. **Use app passwords** - For Gmail, generate app passwords instead of using your main password
3. **Enable TLS** - Always use TLS/SSL for secure connections
4. **Validate inputs** - Sanitize and validate all email inputs

### Performance

1. **Use background tasks** - Send emails asynchronously to avoid blocking responses
2. **Connection pooling** - Reuse SMTP connections when possible
3. **Template caching** - Templates are automatically cached for performance

### Reliability

1. **Error handling** - Always handle email sending errors gracefully
2. **Logging** - Enable debug mode during development
3. **Testing** - Use `suppress_send=True` for testing without actually sending emails

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Check SMTP credentials
   - For Gmail, use an App Password instead of your regular password
   - Verify 2FA settings

2. **Connection Timeout**
   - Check SMTP host and port
   - Verify firewall settings
   - Increase `smtp_timeout` value

3. **Template Not Found**
   - Verify template directory path
   - Check template file names and extensions
   - Ensure template files exist

4. **Background Tasks Not Working**
   - Install nexios-contrib tasks: `pip install nexios-contrib[tasks]`
   - Setup tasks in your app: `setup_tasks(app)`

### Debug Mode

Enable debug mode to see SMTP communication:

```python
config = MailConfig(
    debug=True,  # Enables SMTP debug logging
    suppress_send=True  # Test mode - don't actually send
)
```

## Integration with Other Modules

### Background Tasks

The mail module integrates seamlessly with the nexios-contrib tasks module for async email sending:

```python
from nexios_contrib.tasks import setup_tasks
from nexios_contrib.mail import setup_mail

app = NexiosApp()

# Setup tasks first
task_manager = setup_tasks(app)

# Then setup mail (will automatically integrate with tasks)
mail_client = setup_mail(app)
```

### Templates

The mail module uses Jinja2 for template rendering, which can be integrated with your existing template setup:

```python
# Share template environment with your web templates
from jinja2 import FileSystemLoader, Environment

# Create shared template environment
template_env = Environment(
    loader=FileSystemLoader(["templates/web", "templates/emails"])
)

# Use with mail client
mail_client._template_env = template_env
```

## Examples

### Complete Email Service

```python
from nexios import NexiosApp
from nexios_contrib.mail import setup_mail, MailConfig, MailDepend
from nexios_contrib.tasks import setup_tasks
import os

app = NexiosApp()

# Setup background tasks
task_manager = setup_tasks(app)

# Setup mail
config = MailConfig(
    smtp_host=os.getenv("SMTP_HOST"),
    smtp_port=int(os.getenv("SMTP_PORT")),
    smtp_username=os.getenv("SMTP_USERNAME"),
    smtp_password=os.getenv("SMTP_PASSWORD"),
    use_tls=True,
    default_from=os.getenv("MAIL_DEFAULT_FROM"),
    template_directory="templates/emails"
)
mail_client = setup_mail(app, config=config)

@app.post("/send-welcome")
async def send_welcome_email(
    request: Request,
    response: Response,
    mail_client: MailClient = MailDepend()
):
    data = await request.json
    
    result = await mail_client.send_template_email(
        to=data["email"],
        subject="Welcome to Our Platform!",
        template_name="welcome",
        context={
            "name": data["name"],
            "email": data["email"],
            "company_name": "Acme Corp"
        }
    )
    
    return response.json({
        "success": result.success,
        "message_id": result.message_id,
        "error": result.error
    })

@app.post("/send-async")
async def send_async_email(
    request: Request,
    response: Response
):
    data = await request.json
    
    task = await send_email_async(
        request=request,
        to=data["email"],
        subject=data["subject"],
        body=data["body"]
    )
    
    return response.json({
        "message": "Email queued for sending",
        "task_id": task.id if task else None
    })
```

This comprehensive mail integration provides everything you need to add professional email functionality to your Nexios applications with ease.
