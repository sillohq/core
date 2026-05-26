from typing import Literal

from pydantic import ValidationError

from nexios.application import NexiosApp
from nexios.http import Request, Response


def _make_pydantic_error_handler(
    style: Literal["flat", "list", "nested"] = "nested", status_code: int = 400
):
    """
    Factory that creates a Pydantic error handler with a chosen style.
    """

    async def pydantic_error_handler(
        _: Request, response: Response, exc: ValidationError
    ):
        errors = exc.errors()

        if style == "flat":
            error_dict = {".".join(map(str, e["loc"])): e["msg"] for e in errors}
            return response.json(
                {"error": "Validation Error", "errors": error_dict},
                status_code=status_code,
            )

        elif style == "list":
            error_list = [
                {"field": ".".join(map(str, e["loc"])), "message": e["msg"]}
                for e in errors
            ]
            return response.json(
                {"error": "Validation Error", "errors": error_list},
                status_code=status_code,
            )

        elif style == "nested":
            error_dict = {}
            for e in errors:
                loc, msg = e["loc"], e["msg"]
                if len(loc) == 1:
                    error_dict[loc[0]] = msg
                elif len(loc) == 2:
                    if loc[0] not in error_dict:
                        error_dict[loc[0]] = {}
                    error_dict[loc[0]][loc[1]] = msg  # ty :ignore[invalid-assignment]
                else:
                    error_dict[".".join(map(str, loc))] = msg
            return response.json(
                {"error": "Validation Error", "errors": error_dict},
                status_code=status_code,
            )

        else:
            return response.json(
                {"error": "Validation Error", "errors": "Invalid style option"},
                status_code=status_code,
            )

    return pydantic_error_handler


def add_pydantic_error_handler(
    app: NexiosApp,
    style: Literal["flat", "list", "nested"] = "nested",
    status_code: int = 400,
):
    """
    Add a Pydantic error handler to the app with a chosen style.
    """
    app.add_exception_handler(
        ValidationError, _make_pydantic_error_handler(style, status_code)
    )
