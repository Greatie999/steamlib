class InvalidDataError(Exception):
    pass


class TooManyLoginFailures(Exception):
    pass


class FailToLogout(Exception):
    pass


class LoginRequired(Exception):
    pass