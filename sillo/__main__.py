__version__: str = "0.0.1a1"

ascii_art = f"""
   _____ _ _ _       
  / ____(_) | |      
 | (___  _| | | ___  
  \___ \| | | |/ _ \ 
  ____) | | | | (_) |
 |_____/|_|_|_|\___/ 

      Async Python web framework
       Version: {__version__}
"""

try:
    from sillo.cli import cli
except ImportError:
    cli = None  # ty: ignore[invalid-assignment]

if __name__ == "__main__":
    print(ascii_art)

    # Allow direct module execution to invoke the CLI.
    if cli is not None:
        cli()
    else:
        print("CLI tools not available. Make sure sillo is properly installed.")
