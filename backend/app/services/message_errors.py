class MessageError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 503) -> None:
        self.code, self.message, self.status = code, message, status
        super().__init__(message)
