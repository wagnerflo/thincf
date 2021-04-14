from starlette.exceptions import HTTPException

class BadRequest(HTTPException):
    def __init__(self, *detail) -> None:
        super().__init__(400, ''.join(*detail))

class Forbidden(HTTPException):
    def __init__(self, *detail) -> None:
        super().__init__(403, ''.join(*detail))

class InternalServerError(HTTPException):
    def __init__(self, *detail) -> None:
        super().__init__(500, ''.join(*detail))

class ServiceUnavailable(HTTPException):
    def __init__(self, *detail) -> None:
        super().__init__(503, ''.join(*detail))
