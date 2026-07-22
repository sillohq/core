__version__: str = "3.3.1"

# Version bump test - this comment will be removed after testing
ascii_art = f"""
  _   _                  _
 | \\ | |               (_)
 |  \\| |   ___  __  __  _    ___    ___
 | . ` |  / _ \\ \\ \\/ / | |  / _ \\  / __|
 | |\\  | |  __/  >  <  | | | (_) | \\__ \\
 |_| \\_|  \\___| /_/\\_\\ |_|  \\___/  |___/

     Welcome to sillo 
      The sleek ASGI Backend Framework
      Version: {__version__}
"""

try:
    from sillo.cli import cli
except ImportError:
    cli = None  # type: ignore[assignment]

if __name__ == "__main__":
    print(ascii_art)

    # Allow direct module execution to invoke the CLI
    if cli is not None:
        cli()
    else:
        print("CLI tools not available. Make sure sillo is properly installed.")
