import datetime
import html
import inspect
import json
import os
import platform
import sys
import traceback
import typing
import uuid

from nexios.__main__ import __version__ as nexios_version
from nexios.config import get_config
from nexios.http import Request, Response
from nexios.logging import DEBUG, create_logger
from nexios.middleware.base import BaseMiddleware

logger = create_logger(__name__, log_level=DEBUG)
STYLES = """
:root {
    --primary: #3b82f6;
    --primary-dark: #2563eb;
    --primary-light: #dbeafe;
    --secondary: #10b981;
    --background: #ffffff;
    --surface: #f8fafc;
    --surface-light: #f1f5f9;
    --error: #02ba42;
    --error-light: #fef2f2;
    --warning: #f59e0b;
    --success: #10b981;
    --text: #1e293b;
    --text-secondary: #64748b;
    --text-tertiary: #94a3b8;
    --border: #e2e8f0;
    --border-light: #f1f5f9;
    --code-bg: #1e293b;
    --code-fg: #e2e8f0;
    --highlight: #fbbf24;
    --highlight-bg: rgba(251, 191, 36, 0.1);
    --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
    --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    background-color: var(--background);
    color: var(--text);
    margin: 0;
    padding: 0;
    line-height: 1.6;
    font-size: 14px;
}

h1, h2, h3, h4, h5, h6 {
    font-weight: 600;
    line-height: 1.4;
}

h1 {
    color: var(--text);
    font-size: 28px;
    margin-bottom: 8px;
    font-weight: 700;
}

h2 {
    color: var(--text);
    font-size: 20px;
    margin-top: 8px;
    margin-bottom: 20px;
    font-weight: 600;
}

h3 {
    color: var(--text);
    font-size: 16px;
    margin-top: 20px;
    margin-bottom: 12px;
    font-weight: 600;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 32px 24px;
}

.error-header {
    background: linear-gradient(135deg, #02ba42 0%, #02bb42 100%);
    color: white;
    padding: 32px 24px;
    margin: -32px -24px 32px -24px;
    border-radius: 0 0 16px 16px;
    box-shadow: var(--shadow-lg);
}

.error-header h1 {
    color: white;
    font-size: 32px;
    margin-bottom: 8px;
    font-weight: 700;
}

.error-header .error-message {
    font-size: 18px;
    opacity: 0.9;
    margin-bottom: 16px;
}

.error-meta {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
    font-size: 14px;
    opacity: 0.8;
}

.error-meta-item {
    display: flex;
    align-items: center;
    gap: 8px;
}

.error-meta-item strong {
    font-weight: 600;
}

.section {
    margin-bottom: 24px;
    border: 1px solid var(--border);
    background: var(--surface);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: var(--shadow);
    transition: all 0.2s ease;
}

.section:hover {
    box-shadow: var(--shadow-lg);
}

.section-title {
    background-color: var(--surface-light);
    color: var(--text);
    padding: 16px 20px;
    font-size: 16px;
    font-weight: 600;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    transition: background-color 0.2s ease;
}

.section-title:hover {
    background-color: var(--border-light);
}

.section-content {
    padding: 20px;
    max-height: none;
    overflow: hidden;
    transition: all 0.3s ease;
}

.section-content.collapsed {
    max-height: 0;
    padding-top: 0;
    padding-bottom: 0;
}

.traceback-container {
    background: var(--surface);
    border-radius: 8px;
    overflow: hidden;
}

.frame-title {
    font-weight: 500;
    padding: 16px 20px;
    background-color: var(--surface-light);
    color: var(--text);
    font-size: 14px;
    border-radius: 8px;
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-left: 4px solid var(--primary);
    cursor: pointer;
    transition: all 0.2s ease;
}

.frame-title:hover {
    background-color: var(--border-light);
}

.frame-container {
    margin-bottom: 16px;
}

.frame-info {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
}

.frame-icon {
    font-size: 16px;
    opacity: 0.7;
}

.frame-filename {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
    font-weight: 600;
    color: var(--primary);
}

.frame-separator {
    color: var(--text-tertiary);
    font-weight: 400;
}

.frame-lineno {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
    color: var(--warning);
    font-weight: 600;
}

.frame-function {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
    color: var(--secondary);
    font-weight: 600;
}

.source-code {
    background: var(--code-bg);
    border-radius: 8px;
    padding: 16px;
    margin: 8px 0;
    overflow-x: auto;
    max-height: none;
    transition: all 0.3s ease;
}

.source-code.collapsed {
    max-height: 0;
    padding-top: 0;
    padding-bottom: 0;
    overflow: hidden;
}

.frame-line {
    padding-left: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
    color: var(--code-fg);
    line-height: 1.5;
}

.center-line {
    background-color: var(--error);
    color: white;
    padding: 8px 12px;
    font-weight: 600;
    border-radius: 6px;
    margin: 4px 0;
}

.lineno {
    margin-right: 12px;
    color: var(--text-tertiary);
    user-select: none;
    min-width: 40px;
    display: inline-block;
}

.collapse-btn {
    background: var(--primary);
    color: white;
    border: none;
    width: 28px;
    height: 28px;
    font-size: 16px;
    cursor: pointer;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-left: 12px;
    transition: all 0.2s ease;
    font-weight: 600;
}

.collapse-btn:hover {
    background: var(--primary-dark);
    transform: scale(1.05);
}

.collapse-btn:active {
    transform: scale(0.95);
}

.info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 24px;
    margin-bottom: 24px;
}

.info-block {
    background: white;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
}

.info-block h3 {
    margin-bottom: 16px;
    color: var(--text);
    font-size: 16px;
    font-weight: 600;
}

.info-item {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-light);
}

.info-item:last-child {
    border-bottom: none;
}

.info-label {
    font-weight: 500;
    color: var(--text-secondary);
    min-width: 120px;
}

.info-value {
    color: var(--text);
    text-align: right;
    word-break: break-all;
    max-width: 200px;
}

.key-value-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
}

.key-value-table th,
.key-value-table td {
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border-light);
    font-size: 13px;
}

.key-value-table th {
    background-color: var(--surface-light);
    font-weight: 600;
    color: var(--text-secondary);
}

.key-value-table td:first-child {
    font-weight: 500;
    color: var(--text-secondary);
    min-width: 120px;
}

.key-value-table td:last-child {
    word-break: break-all;
    max-width: 300px;
}

.suggestion {
    background: white;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
}

.suggestion-title {
    font-weight: 600;
    color: var(--text);
    margin-bottom: 8px;
    font-size: 14px;
}

.code-box {
    background: var(--code-bg);
    border-radius: 8px;
    overflow: hidden;
}

.code-header {
    background: var(--surface-light);
    color: var(--text);
    padding: 12px 16px;
    font-weight: 600;
    font-size: 14px;
    border-bottom: 1px solid var(--border);
}

.code-content {
    padding: 16px;
    color: var(--code-fg);
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.5;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-word;
}

.stack-locals {
    background: var(--highlight-bg);
    border: 1px solid var(--highlight);
    border-radius: 6px;
    padding: 12px;
    margin-top: 8px;
}

.stack-locals h4 {
    color: var(--warning);
    margin-bottom: 8px;
    font-size: 14px;
    font-weight: 600;
}

.stack-locals div {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
    font-size: 13px;
    margin-bottom: 4px;
    word-break: break-all;
}

@media (max-width: 768px) {
    .container {
        padding: 16px;
    }
    
    .error-header {
        margin: -16px -16px 24px -16px;
        padding: 24px 16px;
    }
    
    .error-meta {
        flex-direction: column;
        gap: 12px;
    }
    
    .info-grid {
        grid-template-columns: 1fr;
        gap: 16px;
    }
    
    .section-title {
        padding: 12px 16px;
    }
    
    .section-content {
        padding: 16px;
    }
}
"""

JS = """
<script type="text/javascript">
    // Enhanced collapse function with smooth animations
    function collapse(element) {
        const targetId = element.getAttribute("data-target-id");
        const target = document.getElementById(targetId);
        
        if (!target) return;
        
        const isCollapsed = target.classList.contains("collapsed");
        
        if (isCollapsed) {
            // Expand
            element.innerHTML = "&#8210;"; // Minus symbol
            target.classList.remove("collapsed");
            target.style.maxHeight = target.scrollHeight + "px";
            setTimeout(() => {
                target.style.maxHeight = "none";
            }, 300);
        } else {
            // Collapse
            element.innerHTML = "+"; // Plus symbol
            target.style.maxHeight = target.scrollHeight + "px";
            setTimeout(() => {
                target.classList.add("collapsed");
                target.style.maxHeight = "0";
            }, 10);
        }
    }

    // Enhanced section toggle with smooth animations
    function toggleSection(sectionId) {
        const section = document.getElementById(sectionId);
        const button = document.querySelector(`[data-section="${sectionId}"]`);
        
        if (!section || !button) return;
        
        const isCollapsed = section.classList.contains("collapsed");
        
        if (isCollapsed) {
            // Expand
            section.classList.remove("collapsed");
            button.innerHTML = "&#8210;"; // Minus symbol
            section.style.maxHeight = section.scrollHeight + "px";
            setTimeout(() => {
                section.style.maxHeight = "none";
            }, 300);
        } else {
            // Collapse
            button.innerHTML = "+"; // Plus symbol
            section.style.maxHeight = section.scrollHeight + "px";
            setTimeout(() => {
                section.classList.add("collapsed");
                section.style.maxHeight = "0";
            }, 10);
        }
    }

    // Keyboard shortcuts
    function handleKeyboardShortcuts(event) {
        // Ctrl/Cmd + 1-6 to toggle sections
        if ((event.ctrlKey || event.metaKey) && event.key >= '1' && event.key <= '6') {
            event.preventDefault();
            const sectionMap = {
                '1': 'traceback-section',
                '2': 'request-section', 
                '3': 'system-section',
                '4': 'suggestions-section',
                '5': 'json-section'
            };
            const sectionId = sectionMap[event.key];
            if (sectionId) {
                toggleSection(sectionId);
            }
        }
        
        // Escape to collapse all sections
        if (event.key === 'Escape') {
            collapseAllSections();
        }
        
        // Ctrl/Cmd + A to expand all sections
        if ((event.ctrlKey || event.metaKey) && event.key === 'a') {
            event.preventDefault();
            expandAllSections();
        }
    }

    // Collapse all sections
    function collapseAllSections() {
        const sections = document.querySelectorAll('.section-content');
        const buttons = document.querySelectorAll('.collapse-btn[data-section]');
        
        sections.forEach(section => {
            if (!section.classList.contains("collapsed")) {
                section.classList.add("collapsed");
                section.style.maxHeight = "0";
            }
        });
        
        buttons.forEach(button => {
            button.innerHTML = "+";
        });
    }

    // Expand all sections
    function expandAllSections() {
        const sections = document.querySelectorAll('.section-content');
        const buttons = document.querySelectorAll('.collapse-btn[data-section]');
        
        sections.forEach(section => {
            section.classList.remove("collapsed");
            section.style.maxHeight = "none";
        });
        
        buttons.forEach(button => {
            button.innerHTML = "&#8210;";
        });
    }

    // Copy error details to clipboard
    function copyErrorDetails() {
        const errorType = document.querySelector('.error-header h1').textContent;
        const errorMessage = document.querySelector('.error-header .error-message').textContent;
        const traceback = document.querySelector('#traceback-section').textContent;
        
        const errorText = `Error: ${errorType}\\nMessage: ${errorMessage}\\n\\nTraceback:\\n${traceback}`;
        
        navigator.clipboard.writeText(errorText).then(() => {
            showNotification('Error details copied to clipboard!');
        }).catch(() => {
            showNotification('Failed to copy error details');
        });
    }

    // Show notification
    function showNotification(message) {
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--primary);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: var(--shadow-lg);
            z-index: 1000;
            font-weight: 500;
            transform: translateX(100%);
            transition: transform 0.3s ease;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 100);
        
        setTimeout(() => {
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }

    // Initialize when DOM is loaded
    document.addEventListener('DOMContentLoaded', function() {
        // Initialize sections - keep traceback expanded, collapse others
        const sections = document.querySelectorAll('.section-content');
        sections.forEach(section => {
            if (section.id !== 'traceback-section') {
                section.classList.add('collapsed');
                section.style.maxHeight = '0';
                const button = document.querySelector(`[data-section="${section.id}"]`);
                if (button) button.innerHTML = "+";
            }
        });
        
        // Add keyboard event listener
        document.addEventListener('keydown', handleKeyboardShortcuts);
        
        // Add copy button to error header
        const errorHeader = document.querySelector('.error-header');
        if (errorHeader) {
            const copyButton = document.createElement('button');
            copyButton.innerHTML = '📋 Copy Error';
            copyButton.style.cssText = `
                background: rgba(255, 255, 255, 0.2);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.3);
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                transition: all 0.2s ease;
                margin-top: 16px;
            `;
            copyButton.onmouseover = () => {
                copyButton.style.background = 'rgba(255, 255, 255, 0.3)';
            };
            copyButton.onmouseout = () => {
                copyButton.style.background = 'rgba(255, 255, 255, 0.2)';
            };
            copyButton.onclick = copyErrorDetails;
            errorHeader.appendChild(copyButton);
        }
        
        // Add keyboard shortcuts help
        const helpText = document.createElement('div');
        helpText.innerHTML = `
            <div style="
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: var(--surface);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 12px;
                font-size: 12px;
                color: var(--text-secondary);
                box-shadow: var(--shadow);
                z-index: 1000;
                max-width: 200px;
            ">
                <strong>Keyboard Shortcuts:</strong><br>
                Ctrl+1-5: Toggle sections<br>
                Ctrl+A: Expand all<br>
                Esc: Collapse all
            </div>
        `;
        document.body.appendChild(helpText);
        
        // Auto-hide help after 10 seconds
        setTimeout(() => {
            helpText.style.opacity = '0';
            helpText.style.transition = 'opacity 0.5s ease';
            setTimeout(() => {
                if (helpText.parentNode) {
                    helpText.parentNode.removeChild(helpText);
                }
            }, 500);
        }, 10000);
    });
</script>
"""
TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style type='text/css'>
            {styles}
        </style>
        <title>Nexios Debug - {error_type}</title>
    </head>
    <body>
        <div class="container">
            <!-- Error Header -->
            <div class="error-header">
                <h1>{error_type}</h1>
                <div class="error-message">{error}</div>
                <div class="error-meta">
                    <div class="error-meta-item">
                        <strong>Error ID:</strong> {error_id}
                    </div>
                    <div class="error-meta-item">
                        <strong>Time:</strong> {timestamp}
                    </div>
                    <div class="error-meta-item">
                        <strong>Status:</strong> 500 Internal Server Error
                    </div>
                </div>
            </div>

            <!-- Traceback Section (Always visible) -->
            <div class="section">
                <div class="section-title" onclick="toggleSection('traceback-section')">
                    <span>🔍 Traceback & Stack Trace</span>
                    <button class="collapse-btn" data-section="traceback-section" onclick="event.stopPropagation(); toggleSection('traceback-section')">&#8210;</button>
                </div>
                <div id="traceback-section" class="section-content">
                    <div>{exc_html}</div>
                </div>
            </div>

            <!-- Request Information Section -->
            <div class="section">
                <div class="section-title" onclick="toggleSection('request-section')">
                    <span>📡 Request Information</span>
                    <button class="collapse-btn" data-section="request-section" onclick="event.stopPropagation(); toggleSection('request-section')">+</button>
                </div>
                <div id="request-section" class="section-content">
                    {request_info}
                </div>
            </div>

            <!-- System Information Section -->
            <div class="section">
                <div class="section-title" onclick="toggleSection('system-section')">
                    <span>⚙️ System Information</span>
                    <button class="collapse-btn" data-section="system-section" onclick="event.stopPropagation(); toggleSection('system-section')">+</button>
                </div>
                <div id="system-section" class="section-content">
                    {system_info}
                </div>
            </div>

            <!-- Debugging Suggestions Section -->
            <div class="section">
                <div class="section-title" onclick="toggleSection('suggestions-section')">
                    <span>💡 Debugging Suggestions</span>
                    <button class="collapse-btn" data-section="suggestions-section" onclick="event.stopPropagation(); toggleSection('suggestions-section')">+</button>
                </div>
                <div id="suggestions-section" class="section-content">
                    {debugging_suggestions}
                </div>
            </div>

            <!-- JSON Data Section -->
            <div class="section">
                <div class="section-title" onclick="toggleSection('json-section')">
                    <span>📄 Error JSON Data</span>
                    <button class="collapse-btn" data-section="json-section" onclick="event.stopPropagation(); toggleSection('json-section')">+</button>
                </div>
                <div id="json-section" class="section-content">
                    <div class="code-box">
                        <div class="code-header">Error Data (JSON)</div>
                        <pre class="code-content">{error_json}</pre>
                    </div>
                </div>
            </div>
        </div>
        {js}
    </body>
</html>
"""
FRAME_TEMPLATE = """
<div class="frame-container">
    <div class="frame-title" onclick="collapse(this.querySelector('.collapse-btn'))">
        <div class="frame-info">
            <span class="frame-icon">📁</span>
            <span class="frame-filename">{frame_filename}</span>
            <span class="frame-separator">:</span>
            <span class="frame-lineno">{frame_lineno}</span>
            <span class="frame-separator">in</span>
            <span class="frame-function">{frame_name}</span>
        </div>
        <button class="collapse-btn" data-target-id="{frame_filename}-{frame_lineno}">
            {collapse_button}
        </button>
    </div>
    <div id="{frame_filename}-{frame_lineno}" class="source-code {collapsed}">
        {code_context}
    </div>
    {locals_html}
</div>
"""

LINE = """
<p><span class="frame-line">
<span class="lineno">{lineno}.</span> {line}</span></p>
"""

CENTER_LINE = """
<p class="center-line"><span class="frame-line">
<span class="lineno">{lineno}.</span> {line}</span></p>
"""


ServerErrHandlerType = typing.Callable[[Request, Response, Exception], typing.Any]


class ServerErrorMiddleware(BaseMiddleware):
    def __init__(self, handler: typing.Optional[ServerErrHandlerType] = None):
        self.handler = handler

    async def __call__(
        self,
        request: Request,
        response: Response,
        next_middleware: typing.Callable[[], typing.Awaitable[Response]],
    ) -> typing.Any:
        # Store the current request for error context
        self.current_request = request
        # Get debug mode from config
        try:
            self.debug = get_config().debug or True
        except Exception:  # pragma: no cover
            self.debug = True
        try:
            return await next_middleware()
        except Exception as exc:
            if self.handler:
                response = await self.handler(request, response, exc)
            if self.debug:
                response = self.get_debug_response(request, response, exc)
            else:
                response = self.error_response(response)
            headers = request.scope.get("server_error_headers", {})
            response.set_headers(headers)
            err = traceback.format_exc()
            logger.error(err)
            return response

    def error_response(self, res: Response):
        return res.text("Internal Server Error", status_code=500)

    def get_debug_response(
        self, request: Request, response: Response, exc: Exception
    ) -> Response:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            content: str = self.generate_html(exc)
            return response.html(content, status_code=500)
        content = self.generate_plain_text(exc)
        return response.text(content, status_code=500)

    def format_line(
        self, index: int, line: str, frame_lineno: int, frame_index: int
    ) -> str:
        values: typing.Dict[str, typing.Any] = {
            # HTML escape - line could contain < or >
            "line": html.escape(line).replace(" ", "&nbsp"),
            "lineno": (frame_lineno - frame_index) + index,
        }

        if index != frame_index:
            return LINE.format(**values)
        return CENTER_LINE.format(**values)

    def _format_locals(self, frame_locals: typing.Dict[str, typing.Any]) -> str:
        """Format local variables for display in the error template."""
        if not frame_locals:
            return ""

        locals_html = "<div class='stack-locals'><h4>Local Variables:</h4>\n"
        for var_name, var_value in frame_locals.items():
            try:
                # Skip internal variables
                if var_name.startswith("__") and var_name.endswith("__"):
                    continue

                # Format value safely
                value_str = html.escape(repr(var_value))
                if len(value_str) > 500:  # Truncate long values
                    value_str = value_str[:500] + "..."

                locals_html += f"<div><span style='color: #f39c12;'>{html.escape(var_name)}</span> = {value_str}</div>\n"
            except Exception:
                locals_html += f"<div><span style='color: #f39c12;'>{html.escape(var_name)}</span> = <error displaying value></div>\n"

        locals_html += "</div>"
        return locals_html

    def generate_frame_html(self, frame: inspect.FrameInfo, is_collapsed: bool) -> str:
        code_context: str = "".join(  # type:ignore
            self.format_line(
                index,
                line,
                frame.lineno,
                frame.index,  # type:ignore
            )
            for index, line in enumerate(frame.code_context or [])  # type:ignore
        )

        # Format local variables if available
        locals_html = (
            self._format_locals(frame.frame.f_locals) if hasattr(frame, "frame") else ""
        )

        values: typing.Dict[str, typing.Any] = {
            "frame_filename": html.escape(frame.filename),
            "frame_lineno": frame.lineno,
            "frame_name": html.escape(frame.function),
            "code_context": code_context,
            "collapsed": "collapsed" if is_collapsed else "",
            "collapse_button": "+" if is_collapsed else "&#8210;",
            "locals_html": locals_html,
        }
        return FRAME_TEMPLATE.format(**values)

    def generate_plain_text(self, exc: Exception) -> str:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    def _format_request_info(self, request: Request) -> str:
        """Format request information for display in the error template."""
        method = request.method
        url = str(request.url)

        # General request info
        _html = f"""
        <div class="info-grid">
            <div class="info-block">
                <h3>Request Details</h3>
                <div class="info-item">
                    <div class="info-label">Method:</div>
                    <div class="info-value">{html.escape(method)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">URL:</div>
                    <div class="info-value">{html.escape(url)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Path:</div>
                    <div class="info-value">{html.escape(request.path)}</div>
                </div>
                
            </div>
            
            <div class="info-block">
                <h3>Headers</h3>
                <table class="key-value-table">
        """

        # Add headers
        for name, value in request.headers.items():
            _html += f"""
                    <tr>
                        <td>{html.escape(name)}</td>
                        <td>{html.escape(value)}</td>
                    </tr>
            """

        _html += """
                </table>
            </div>
        </div>
        """

        # Add query parameters if available
        if hasattr(request, "query_params") and request.query_params:
            _html += """
            <div class="info-block">
                <h3>Query Parameters</h3>
                <table class="key-value-table">
            """

            for name, value in request.query_params.items():
                _html += f"""
                    <tr>
                        <td>{html.escape(name)}</td>
                        <td>{html.escape(str(value))}</td>
                    </tr>
                """

            _html += """
                </table>
            </div>
            """

        return _html

    def _format_system_info(self) -> str:
        """Format system information for display in the error template."""
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        _html = f"""
        <div class="info-grid">
            <div class="info-block">
                <h3>Nexios</h3>
                <div class="info-item">
                    <div class="info-label">Nexios Version:</div>
                    <div class="info-value">{html.escape(nexios_version)}</div> 
                </div>
                <div class="info-item">
                    <div class="info-label">Debug Mode:</div>
                    <div class="info-value">{self.debug}</div>
                </div>
            </div>
            
            <div class="info-block">
                <h3>Python</h3>
                <div class="info-item">
                    <div class="info-label">Python Version:</div>
                    <div class="info-value">{html.escape(python_version)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Python Path:</div>
                    <div class="info-value">{html.escape(sys.executable)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Python Implementation:</div>
                    <div class="info-value">{html.escape(platform.python_implementation())}</div>
                </div>
            </div>
        </div>
        
        <div class="info-grid">
            <div class="info-block">
                <h3>System</h3>
                <div class="info-item">
                    <div class="info-label">Platform:</div>
                    <div class="info-value">{html.escape(platform.platform())}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">OS:</div>
                    <div class="info-value">{html.escape(platform.system())} {html.escape(platform.release())}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Architecture:</div>
                    <div class="info-value">{html.escape(platform.machine())}</div>
                </div>
            </div>
            
            <div class="info-block">
                <h3>Environment</h3>
                <div class="info-item">
                    <div class="info-label">Process ID:</div>
                    <div class="info-value">{os.getpid()}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Current Directory:</div>
                    <div class="info-value">{html.escape(os.getcwd())}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Python Path:</div>
                    <div class="info-value">{html.escape(str(sys.path))}</div>
                </div>
            </div>
        </div>
        """

        return _html

    def _generate_error_json(self, exc: Exception, exc_type_str: str) -> str:
        """Generate a JSON representation of the error for debugging."""
        error_data: typing.Dict[str, typing.Any] = {
            "error": {
                "type": exc_type_str,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
            "system": {
                "nexios_version": nexios_version,
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "platform": platform.platform(),
                "debug_mode": self.debug,
            },
            "timestamp": datetime.datetime.now().isoformat(),
            "error_id": str(uuid.uuid4()),
        }

        try:
            return json.dumps(error_data, indent=2)
        except Exception as _:
            # If JSON serialization fails, provide a simplified version
            return json.dumps(
                {
                    "error": {
                        "type": exc_type_str,
                        "message": str(exc),
                        "note": "Full error data could not be serialized to JSON",
                    }
                },
                indent=2,
            )

    def _generate_debugging_suggestions(self, exc: Exception, exc_type_str: str) -> str:
        """Generate debugging suggestions based on the error type."""
        suggestions: typing.List[typing.Dict[str, str]] = []

        # Common error types and suggestions
        if "ImportError" in exc_type_str or "ModuleNotFoundError" in exc_type_str:
            suggestions.append(
                {
                    "title": "Missing Module",
                    "text": "This error typically occurs when Python cannot find a required module. Check that all dependencies are installed correctly. Try running 'pip install -r requirements.txt'.",
                }
            )

        elif "SyntaxError" in exc_type_str:
            suggestions.append(
                {
                    "title": "Syntax Error",
                    "text": "There's a syntax error in your code. Check the line indicated in the traceback for mismatched parentheses, missing colons, or incorrect indentation.",
                }
            )

        elif "AttributeError" in exc_type_str:
            suggestions.append(
                {
                    "title": "Attribute Error",
                    "text": "You're trying to access an attribute or method that doesn't exist on the object. Check for typos or make sure the object is of the expected type before accessing its attributes.",
                }
            )

        elif "KeyError" in exc_type_str:
            suggestions.append(
                {
                    "title": "Key Error",
                    "text": "You're trying to access a dictionary key that doesn't exist. Make sure the key exists before trying to access it, or use dictionary.get(key) method with a default value.",
                }
            )

        elif "NameError" in exc_type_str:
            suggestions.append(
                {
                    "title": "Name Error",
                    "text": "You're trying to use a variable that hasn't been defined. Check for typos or make sure to define the variable before using it.",
                }
            )

        elif "TypeError" in exc_type_str:
            suggestions.append(
                {
                    "title": "Type Error",
                    "text": "An operation is being performed on an object of an inappropriate type. Check the types of your variables and make sure they match what the operation expects.",
                }
            )

        elif "ValueError" in exc_type_str:
            suggestions.append(
                {
                    "title": "Value Error",
                    "text": "An operation is receiving an argument with the right type but an inappropriate value. Check the value of the arguments you're passing to functions.",
                }
            )

        elif "IndexError" in exc_type_str:
            suggestions.append(
                {
                    "title": "Index Error",
                    "text": "You're trying to access an index that's out of range. Make sure the index is valid before accessing it, or use a try/except block to handle the error.",
                }
            )

        elif "FileNotFoundError" in exc_type_str:
            suggestions.append(
                {
                    "title": "File Not Found",
                    "text": "The system cannot find the file specified. Check the file path and make sure the file exists.",
                }
            )

        elif "PermissionError" in exc_type_str:
            suggestions.append(
                {
                    "title": "Permission Error",
                    "text": "You don't have permission to access the specified file or directory. Check the file permissions or run the application with higher privileges.",
                }
            )

        # Add a general debugging strategy for all errors
        suggestions.append(
            {
                "title": "General Debugging Steps",
                "text": "1. Check the traceback to find where the error occurred.<br>2. Review the variables at that point using the local variables section.<br>3. Add logging statements around the error to track variable values.<br>4. Use a debugger to step through the code execution.",
            }
        )

        # Format the suggestions as HTML
        _html = ""
        for suggestion in suggestions:
            _html += f"""
            <div class="suggestion">
                <div class="suggestion-title">{html.escape(suggestion["title"])}</div>
                <div>{suggestion["text"]}</div>
            </div>
            """

        return _html

    def generate_html(self, exc: Exception, limit: int = 7) -> str:
        """Generate an enhanced HTML page for displaying error information."""
        # Generate a unique error ID for tracking
        error_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get exception information
        traceback_obj = traceback.TracebackException.from_exception(
            exc, capture_locals=True
        )

        # Get exception type name
        if sys.version_info >= (3, 13):
            exc_type_str = traceback_obj.exc_type_str
        else:
            exc_type_str = traceback_obj.exc_type.__name__

        # Format the error message
        error = f"{html.escape(exc_type_str)}: {html.escape(str(traceback_obj))}"

        # Generate traceback HTML
        exc_html = ""
        is_collapsed = False
        exc_traceback = exc.__traceback__
        if exc_traceback is not None:
            frames = inspect.getinnerframes(exc_traceback, limit)
            for frame in reversed(frames):
                exc_html += self.generate_frame_html(frame, is_collapsed)
                is_collapsed = True

        # Get request information if available
        try:
            request_info = self._format_request_info(self.current_request)
        except Exception as e:
            request_info = f"<div class='info-block'><h3>Error retrieving request information</h3><p>{html.escape(str(e))}</p></div>"

        # Get system information
        try:
            system_info = self._format_system_info()
        except Exception as e:
            system_info = f"<div class='info-block'><h3>Error retrieving system information</h3><p>{html.escape(str(e))}</p></div>"

        # Generate debugging suggestions
        try:
            debugging_suggestions = self._generate_debugging_suggestions(
                exc, exc_type_str
            )
        except Exception as e:
            debugging_suggestions = f"<div class='info-block'><h3>Error generating debugging suggestions</h3><p>{html.escape(str(e))}</p></div>"

        # Generate JSON representation of the error
        try:
            error_json = html.escape(self._generate_error_json(exc, exc_type_str))
        except Exception as e:
            error_json = html.escape(f"Error generating JSON data: {str(e)}")

        # Put everything together in the template
        return TEMPLATE.format(
            styles=STYLES,
            js=JS,
            error=error,
            error_type=html.escape(exc_type_str),
            error_id=error_id,
            timestamp=timestamp,
            exc_html=exc_html,
            request_info=request_info,
            system_info=system_info,
            debugging_suggestions=debugging_suggestions,
            error_json=error_json,
        )
