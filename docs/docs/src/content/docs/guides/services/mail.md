---
title: Mail Service
description: Send emails with SMTP, templates, and attachments via sillo.services.mail.
---

# Mail (`sillo.services.mail`)

```python
from sillo.services.mail import MailConfig, MailClient, EmailMessage, setup_mail

# Setup at startup
mail = setup_mail(app, config=MailConfig.for_gmail("user@gmail.com", "app-password"))

# In a handler
@app.post("/send")
async def send(request, response):
    result = await mail.send_email(
        to="user@example.com",
        subject="Welcome!",
        body="Thanks for signing up.",
        html_body="<h1>Welcome!</h1><p>Thanks for signing up.</p>",
    )
    return response.json(result.to_dict())
```

## Quick Configs

```python
MailConfig.for_gmail("user@gmail.com", "app-password")
MailConfig.for_outlook("user@outlook.com", "password")
MailConfig.for_sendgrid("SG.api-key")
```

## Templates

Requires `jinja2`. Point `template_directory` to a folder with `.html` / `.txt` files:

```python
config = MailConfig(template_directory="templates/mail")
mail = setup_mail(app, config)

result = await mail.send_template_email(
    to="user@example.com",
    subject="Welcome",
    template_name="welcome",
    context={"user_name": "Alice"},
)
```

## Attachments

```python
msg = EmailMessage(to=["user@example.com"], subject="Report")
msg.add_attachment("report.pdf", "/path/to/report.pdf")
msg.add_attachment("logo.png", b"\x89PNG...", content_type="image/png")
await mail.send_message(msg)
```
