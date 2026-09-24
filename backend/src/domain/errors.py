class DomainError(ValueError):
    """Business input or state rejected by the wallet."""


class InvalidMoney(DomainError):
    pass


class InvalidAccount(DomainError):
    pass


class InvalidDeposit(DomainError):
    pass


class AccountNotFound(DomainError):
    pass


class DuplicateHandle(DomainError):
    pass


class InvalidTransfer(DomainError):
    pass


class InsufficientFunds(DomainError):
    pass


class SameAccountTransfer(DomainError):
    pass


class IdempotencyConflict(DomainError):
    pass


class DuplicateIdempotencyKey(DomainError):
    pass
