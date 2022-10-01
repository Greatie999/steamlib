class InvalidDataError(Exception):
    pass


class TooManyLoginFailures(Exception):
    pass


class FailToLogout(Exception):
    pass


class LoginRequired(Exception):
    pass


class TooManyRequests(Exception):
    def __str__(self) -> str:
        return "You can make no more than 20 requests per minute"


class ApiException(Exception):
    pass


class InvalidUrlException(Exception):
    def __str__(self) -> str:
        return "Invalid url"


class NoConfirmations(Exception):
    pass


class BanException(Exception):
    pass