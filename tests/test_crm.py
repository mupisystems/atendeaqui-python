"""Testes para o módulo de CRM (contrato: AtendeAqui docs/api-engagement-usage.md, seção 3)."""
import json
from decimal import Decimal

import pytest
import responses

from atendeaqui import AtendeAquiClient, AuthenticationError, Company, ValidationError

BASE_URL = 'https://test.atendeaqui.com.br'
COMPANIES_URL = f'{BASE_URL}/api/crm/companies/'

COMPANY_DATA = {
    'platform_id': '1842',
    'name': 'Construtora Alfa',
    'segment': None,
    'porte': None,
    'status': 'cliente',
    'mrr': '349.90',
    'conversion_date': '2026-10-20',
    'monthly_volume': None,
    'website': None,
}


@pytest.fixture
def admin_client():
    return AtendeAquiClient(api_token='test-token', _base_url=f'{BASE_URL}/api')


def sent_body(mocked_responses):
    return json.loads(mocked_responses.calls[0].request.body)


class TestUpsertCompany:

    def test_posts_and_returns_company(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, COMPANIES_URL, json=COMPANY_DATA, status=201)

        company = admin_client.crm.upsert_company(
            platform_id='1842', name='Construtora Alfa', status='cliente', mrr='349.90',
        )

        assert isinstance(company, Company)
        assert company.platform_id == '1842'
        assert company.mrr == '349.90'
        assert company.conversion_date == '2026-10-20'
        assert sent_body(mocked_responses) == {
            'platform_id': '1842', 'name': 'Construtora Alfa', 'status': 'cliente', 'mrr': '349.90',
        }
        assert mocked_responses.calls[0].request.headers['Authorization'] == 'Bearer test-token'

    def test_omitted_fields_are_not_sent(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, COMPANIES_URL, json=COMPANY_DATA, status=200)

        admin_client.crm.upsert_company(platform_id='1842', name='Construtora Alfa')

        assert sent_body(mocked_responses) == {'platform_id': '1842', 'name': 'Construtora Alfa'}

    def test_mrr_none_clears_the_value(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, COMPANIES_URL, json={**COMPANY_DATA, 'mrr': None})

        admin_client.crm.upsert_company(platform_id='1842', name='Construtora Alfa', mrr=None)

        assert sent_body(mocked_responses)['mrr'] is None

    def test_decimal_mrr_and_int_platform_id_are_sent_as_text(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, COMPANIES_URL, json=COMPANY_DATA)

        admin_client.crm.upsert_company(platform_id=1842, name='Construtora Alfa', mrr=Decimal('349.90'))

        body = sent_body(mocked_responses)
        assert body['platform_id'] == '1842'
        assert body['mrr'] == '349.90'

    def test_name_in_use_raises_validation_error(self, admin_client, mocked_responses):
        mocked_responses.add(
            responses.POST, COMPANIES_URL, status=409,
            json={'name': ['Já existe outra empresa com este nome nesta organização.']},
        )

        with pytest.raises(ValidationError) as exc_info:
            admin_client.crm.upsert_company(platform_id='1842', name='Construtora Alfa')
        assert exc_info.value.status_code == 409
        assert 'Já existe outra empresa' in exc_info.value.message

    def test_invalid_token_raises_authentication_error(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, COMPANIES_URL, status=401,
                             json={'detail': 'Token inválido.'})

        with pytest.raises(AuthenticationError):
            admin_client.crm.upsert_company(platform_id='1842', name='Construtora Alfa')
