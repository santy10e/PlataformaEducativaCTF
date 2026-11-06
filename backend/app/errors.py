from fastapi import HTTPException


class ApiError(HTTPException):
    """HTTPException carrying a stable machine-readable code for the CONTRACT error envelope."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code
