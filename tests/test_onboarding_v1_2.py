"""Testes do que entrou na 1.2.0: regras e peças de e-mail, prévia, cobertura e descadastro."""
import json

import pytest
import responses

from atendeaqui import UserProgress, ValidationError

BASE_URL = 'https://test.atendeaqui.com.br/api/onboarding/flows/meu-flow'


def sent_body(index=0):
    body = responses.calls[index].request.body
    return json.loads(body) if body else None


class TestEmailRules:
    @responses.activate
    def test_create_update_delete(self, admin_client):
        responses.add(responses.POST, f'{BASE_URL}/email-rules/', json={'id': 7, 'send_mode': 'simulate'}, status=201)
        responses.add(responses.PATCH, f'{BASE_URL}/email-rules/7/', json={'id': 7, 'send_mode': 'send'}, status=200)
        responses.add(responses.DELETE, f'{BASE_URL}/email-rules/7/', status=204)

        rule = admin_client.onboarding.create_email_rule('meu-flow', 'step_stalled', delay_minutes=30)
        admin_client.onboarding.update_email_rule('meu-flow', rule['id'], send_mode='send')
        admin_client.onboarding.delete_email_rule('meu-flow', rule['id'])

        assert sent_body(0) == {'event_type': 'step_stalled', 'delay_minutes': 30}
        assert sent_body(1) == {'send_mode': 'send'}
        assert responses.calls[2].request.method == 'DELETE'

    def test_update_requires_a_field(self, admin_client):
        with pytest.raises(ValueError):
            admin_client.onboarding.update_email_rule('meu-flow', 7)


class TestEmailPieces:
    @responses.activate
    def test_list_with_filters_and_conditions(self, admin_client):
        responses.add(responses.GET, f'{BASE_URL}/email-pieces/', json={'count': 1, 'results': [{'id': 1}]},
                      status=200)

        pieces = admin_client.onboarding.list_email_pieces(
            'meu-flow', block='dica', status='draft', conditions={'segment': 'saude', 'plan_code': 'trial'},
        )

        assert pieces == [{'id': 1}]
        request = responses.calls[0].request
        assert request.params == {
            'block': 'dica', 'status': 'draft', 'page': '1', 'page_size': '50',
            'condition': ['segment:saude', 'plan_code:trial'],
        }

    @responses.activate
    def test_create_sends_only_given_fields(self, admin_client):
        responses.add(responses.POST, f'{BASE_URL}/email-pieces/', json={'id': 3, 'status': 'draft'}, status=201)

        admin_client.onboarding.create_email_piece(
            'meu-flow', 'corpo', 'Olá, {NOME}!', subject='Bem-vinda', event_type='flow_started',
            conditions={'segment': 'saude'}, cta_label='Começar',
        )

        assert sent_body() == {
            'block': 'corpo', 'body': 'Olá, {NOME}!', 'subject': 'Bem-vinda', 'event_type': 'flow_started',
            'conditions': {'segment': 'saude'}, 'cta_label': 'Começar',
        }

    @responses.activate
    def test_update_may_return_a_new_version(self, admin_client):
        responses.add(responses.PATCH, f'{BASE_URL}/email-pieces/3/', json={'id': 9, 'version': 2, 'status': 'draft'},
                      status=201)

        piece = admin_client.onboarding.update_email_piece('meu-flow', 3, body='Novo texto')

        assert (piece['id'], piece['version']) == (9, 2)
        assert sent_body() == {'body': 'Novo texto'}

    @responses.activate
    def test_approve_problems_raise_validation_error(self, admin_client):
        responses.add(responses.POST, f'{BASE_URL}/email-pieces/3/approve/',
                      json={'problems': ['Variável desconhecida: {CUPOM}.']}, status=400)

        with pytest.raises(ValidationError) as excinfo:
            admin_client.onboarding.approve_email_piece('meu-flow', 3)

        assert 'CUPOM' in str(excinfo.value)
        assert excinfo.value.response.json()['problems'] == ['Variável desconhecida: {CUPOM}.']

    @responses.activate
    def test_archive_and_delete(self, admin_client):
        responses.add(responses.POST, f'{BASE_URL}/email-pieces/3/archive/', json={'status': 'archived'}, status=200)
        responses.add(responses.DELETE, f'{BASE_URL}/email-pieces/4/', status=204)

        assert admin_client.onboarding.archive_email_piece('meu-flow', 3)['status'] == 'archived'
        assert admin_client.onboarding.delete_email_piece('meu-flow', 4) is None

    @responses.activate
    def test_preview_for_example_user_and_real_user(self, admin_client):
        responses.add(responses.POST, f'{BASE_URL}/email-pieces/preview/', json={'subject': 'Oi'}, status=200)

        admin_client.onboarding.preview_email(
            'meu-flow', 'step_stalled', step_key='first-appointment', name='Bia', metadata={'segment': 'saude'},
        )
        admin_client.onboarding.preview_email('meu-flow', 'flow_started', user_id='org-siga-12',
                                               include_drafts=False)

        assert sent_body(0) == {
            'event_type': 'step_stalled', 'include_drafts': True, 'step_key': 'first-appointment',
            'name': 'Bia', 'metadata': {'segment': 'saude'},
        }
        assert sent_body(1) == {'event_type': 'flow_started', 'include_drafts': False,
                                'external_user_id': 'org-siga-12'}

    @responses.activate
    def test_coverage(self, admin_client):
        responses.add(responses.GET, f'{BASE_URL}/email-pieces/coverage/',
                      json={'events_without_generic_body': ['step_stalled']}, status=200)

        data = admin_client.onboarding.get_email_coverage('meu-flow', language='pt-BR')

        assert data['events_without_generic_body'] == ['step_stalled']
        assert responses.calls[0].request.params == {'language': 'pt-BR'}


class TestEmailSubscription:
    @responses.activate
    def test_unsubscribe_and_resubscribe(self, admin_client):
        url = f'{BASE_URL}/progress/org-siga-12/email-subscription/'
        responses.add(responses.PATCH, url, json={'email_unsubscribed': True}, status=200)

        admin_client.onboarding.set_email_subscription('meu-flow', 'org-siga-12', True)
        admin_client.onboarding.set_email_subscription('meu-flow', 'org-siga-12', False)

        assert sent_body(0) == {'unsubscribed': True}
        assert sent_body(1) == {'unsubscribed': False}

    def test_progress_exposes_unsubscribe_state(self):
        assert UserProgress.from_dict({'email_unsubscribed': True}).email_unsubscribed is True
        assert UserProgress.from_dict({}).email_unsubscribed is False
