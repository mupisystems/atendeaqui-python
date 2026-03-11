"""
Hierarquia de exceções do SDK AtendeAqui.

Todas as exceções herdam de AtendeAquiError, que fornece:
- message: descrição legível do erro
- code: código de erro da API (ex: STEP_NOT_FOUND)
- status_code: HTTP status code da resposta
- response: objeto Response original (quando disponível)
"""


class AtendeAquiError(Exception):
    """Exceção base para todos os erros do SDK."""

    def __init__(self, message, code=None, status_code=None, response=None):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.response = response
        super().__init__(message)

    def __repr__(self):
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"


class AuthenticationError(AtendeAquiError):
    """Erro de autenticação (401/403)."""
    pass


class NotFoundError(AtendeAquiError):
    """Recurso não encontrado (404)."""
    pass


class ValidationError(AtendeAquiError):
    """Erro de validação (400)."""
    pass


class StepNotFoundError(ValidationError):
    """Step de onboarding não encontrado no flow."""
    pass


class StepNotSkippableError(ValidationError):
    """Step de onboarding não pode ser pulado."""
    pass


class OriginNotAllowedError(AtendeAquiError):
    """Origem (CORS) não permitida."""
    pass


class RateLimitError(AtendeAquiError):
    """Limite de requisições excedido (429)."""
    pass


class ServerError(AtendeAquiError):
    """Erro interno do servidor (5xx)."""
    pass


# Mapeamento de códigos da API para classes de exceção
ERROR_CODE_MAP = {
    'FLOW_NOT_FOUND': NotFoundError,
    'PROGRESS_NOT_FOUND': NotFoundError,
    'NOT_FOUND': NotFoundError,
    'STEP_NOT_FOUND': StepNotFoundError,
    'STEP_NOT_SKIPPABLE': StepNotSkippableError,
    'ORIGIN_NOT_ALLOWED': OriginNotAllowedError,
    'VALIDATION_ERROR': ValidationError,
    'AUTH_REQUIRED': AuthenticationError,
    'TOKEN_EXPIRED': AuthenticationError,
    'PERMISSION_DENIED': AuthenticationError,
}
