"""Testes para exceções do SDK."""
import pytest

from atendeaqui.exceptions import (
    AtendeAquiError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    StepNotFoundError,
    StepNotSkippableError,
    OriginNotAllowedError,
    RateLimitError,
    ServerError,
    ERROR_CODE_MAP,
)


class TestExceptionHierarchy:
    def test_base_exception(self):
        exc = AtendeAquiError('test', code='TEST', status_code=400)
        assert exc.message == 'test'
        assert exc.code == 'TEST'

    def test_repr(self):
        exc = AtendeAquiError('msg', code='CODE')
        assert "AtendeAquiError(code='CODE', message='msg')" == repr(exc)

    def test_inheritance(self):
        assert issubclass(StepNotFoundError, ValidationError)
        assert issubclass(StepNotSkippableError, ValidationError)
        assert issubclass(ValidationError, AtendeAquiError)
        assert issubclass(NotFoundError, AtendeAquiError)

    def test_catch_specific_before_base(self):
        with pytest.raises(StepNotFoundError):
            raise StepNotFoundError('not found')

        with pytest.raises(ValidationError):
            raise StepNotFoundError('not found')

        with pytest.raises(AtendeAquiError):
            raise StepNotFoundError('not found')


class TestErrorCodeMap:
    def test_all_codes_mapped(self):
        expected = [
            'FLOW_NOT_FOUND', 'PROGRESS_NOT_FOUND', 'NOT_FOUND',
            'STEP_NOT_FOUND', 'STEP_NOT_SKIPPABLE', 'ORIGIN_NOT_ALLOWED',
            'VALIDATION_ERROR', 'AUTH_REQUIRED', 'TOKEN_EXPIRED', 'PERMISSION_DENIED',
        ]
        for code in expected:
            assert code in ERROR_CODE_MAP

    def test_correct_mapping(self):
        assert ERROR_CODE_MAP['STEP_NOT_FOUND'] is StepNotFoundError
        assert ERROR_CODE_MAP['FLOW_NOT_FOUND'] is NotFoundError
