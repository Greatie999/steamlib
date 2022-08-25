class InvalidDataError(Exception):
    def __str__(self) -> str:
        return "Invalid login, password or 2FA"


class TooManyRequests(Exception):
    def __str__(self) -> str:
        return "You can make no more than 20 requests per minute"


class ApiException(Exception):
    pass


class InvalidUrlException(Exception):
    def __str__(self) -> str:
        return "Invalid url"
