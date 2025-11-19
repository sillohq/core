__version__: str = "3.3.1"

# Version bump test - this comment will be removed after testing
ascii_art = f"""
  _   _                  _
 | \\ | |               (_)
 |  \\| |   ___  __  __  _    ___    ___
 | . ` |  / _ \\ \\ \\/ / | |  / _ \\  / __|
 | |\\  | |  __/  >  <  | | | (_) | \\__ \\
 |_| \\_|  \\___| /_/\\_\\ |_|  \\___/  |___/

    🚀 Welcome to Nexios 🚀
      The sleek ASGI Backend Framework
      Version: {__version__}
"""

if __name__ == "__main__":
    print(ascii_art)

    # Allow direct module execution to invoke the CLI
    try:
        from nexios.cli import cli

        cli()
    except ImportError:
        print("CLI tools not available. Make sure Nexios is properly installed.")
