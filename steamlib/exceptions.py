class InvalidDataError(Exception):
    
    def __str__(self) -> str:
        return 'Invalid login, password or 2FA'
