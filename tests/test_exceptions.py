"""Testes para exceções do SDK."""
import pytest
import requests
import responses

from atendeaqui import AtendeAquiClient
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
    NetworkError,
    ERROR_CODE_MAP,
)

BASE_URL = 'https://test.atendeaqui.com.br/api'


@pytest.fixture
def admin_client():
    return AtendeAquiClient(api_token='test-token', _base_url=BASE_URL)


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


class TestIsRetryable:
    @pytest.mark.parametrize('exc_class', [ServerError, RateLimitError, NetworkError])
    def test_temporary_errors_can_be_retried(self, exc_class):
        assert exc_class('x').is_retryable is True

    @pytest.mark.parametrize('exc_class', [
        AtendeAquiError, AuthenticationError, NotFoundError, ValidationError,
        StepNotFoundError, StepNotSkippableError, OriginNotAllowedError,
    ])
    def test_permanent_errors_are_not_retried(self, exc_class):
        assert exc_class('x').is_retryable is False

    def test_network_error_is_still_a_requests_error(self):
        with pytest.raises(requests.exceptions.RequestException):
            raise NetworkError('sem rede')


class TestNetworkFailure:
    @pytest.mark.parametrize('failure', [
        requests.exceptions.ConnectionError('conexão recusada'),
        requests.exceptions.ReadTimeout('demorou demais'),
    ])
    def test_network_failure_becomes_network_error(self, admin_client, mocked_responses, failure):
        mocked_responses.add(responses.POST, f'{BASE_URL}/crm/companies/', body=failure)

        with pytest.raises(NetworkError) as caught:
            admin_client.crm.upsert_company(platform_id='1842', name='Construtora Alfa')

        assert caught.value.is_retryable is True
        assert caught.value.code == 'NETWORK_ERROR'
        assert caught.value.__cause__ is failure
