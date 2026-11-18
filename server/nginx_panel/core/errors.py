"""业务异常，API 层统一转换成 HTTP 错误。"""


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, detail=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail