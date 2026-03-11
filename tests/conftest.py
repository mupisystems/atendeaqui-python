"""Fixtures compartilhadas para testes do SDK."""
import pytest
import responses

from atendeaqui import AtendeAquiClient

FLOW_KEY = 'f47ac10b-58cc-4372-a567-0e02b2c3d479'
# _base_url é parâmetro interno, usado apenas em testes
_TEST_BASE_URL = 'https://test.atendeaqui.com.br/api'


@pytest.fixture
def mocked_responses():
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def client():
    """Cliente com flow_key default (API pública de onboarding)."""
    return AtendeAquiClient(
        flow_key=FLOW_KEY,
        timeout=5,
        _base_url=_TEST_BASE_URL,
    )


@pytest.fixture
def admin_client():
    """Cliente com api_token + flow_key default (API admin + pública)."""
    return AtendeAquiClient(
        api_token='test-bearer-token-123',
        flow_key=FLOW_KEY,
        timeout=5,
        _base_url=_TEST_BASE_URL,
    )


@pytest.fixture
def admin_only_client():
    """Cliente com api_token apenas (API admin sem flow_key default)."""
    return AtendeAquiClient(
        api_token='test-bearer-token-123',
        timeout=5,
        _base_url=_TEST_BASE_URL,
    )
