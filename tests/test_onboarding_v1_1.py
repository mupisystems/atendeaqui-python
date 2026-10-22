"""Testes do que entrou na 1.1.0: occurred_at, e-mails de onboarding e update_flow."""
import json
from datetime import datetime, timedelta, timezone

import pytest
import responses

from atendeaqui import __version__

BASE_URL = 'https://test.atendeaqui.com.br'
FLOW_KEY = 'f47ac10b-58cc-4372-a567-0e02b2c3d479'
PROGRESS_URL = f'{BASE_URL}/api/onboarding/{FLOW_KEY}/progress/user-123'

PROGRESS_DATA = {
    'external_user_id': 'user-123',
    'status': 'IN_PROGRESS',
    'steps_completed': [],
    'steps_skipped': [],
    'step_data': {},
}

BRT = timezone(timedelta(hours=-3))
WHEN = datetime(2026, 10, 20, 9, 30, tzinfo=BRT)
WHEN_ISO = '2026-10-20T09:30:00-03:00'


def sent_body(index=0):
    body = responses.calls[index].request.body
    return json.loads(body) if body else None


class TestOccurredAt:
    @responses.activate
    def test_start_flow_sends_aware_datetime_as_iso(self, client):
        responses.add(responses.POST, f'{BASE_URL}/api/onboarding/{FLOW_KEY}/start/',
                      json=PROGRESS_DATA, status=201)

        client.onboarding.start_flow(user_id='user-123', occurred_at=WHEN)

        assert sent_body()['occurred_at'] == WHEN_ISO

    @responses.activate
    def test_iso_string_is_sent_as_is(self, client):
        responses.add(responses.POST, f'{PROGRESS_URL}/complete-step/', json=PROGRESS_DATA, status=200)

        client.onboarding.complete_step(user_id='user-123', step_key='welcome', occurred_at='2026-10-20T12:30:00Z')

        assert sent_body() == {'step_key': 'welcome', 'occurred_at': '2026-10-20T12:30:00Z'}

    @responses.activate
    def test_omitted_occurred_at_is_not_sent(self, client):
        responses.add(responses.POST, f'{PROGRESS_URL}/start-step/', json=PROGRESS_DATA, status=200)

        client.onboarding.start_step(user_id='user-123', step_key='welcome')

        assert 'occurred_at' not in sent_body()

    def test_naive_datetime_is_rejected_before_request(self, client):
        with responses.RequestsMock() as rsps:
            with pytest.raises(ValueError, match='fuso'):
                client.onboarding.start_step(
                    user_id='user-123', step_key='welcome', occurred_at=datetime(2026, 10, 20, 9, 30),
                )
            assert len(rsps.calls) == 0

    @responses.activate
    def test_step_actions_accept_occurred_at(self, client):
        responses.add(responses.POST, f'{PROGRESS_URL}/start-step/', json=PROGRESS_DATA, status=200)
        responses.add(responses.POST, f'{PROGRESS_URL}/skip-step/', json=PROGRESS_DATA, status=200)
        responses.add(responses.PATCH, f'{PROGRESS_URL}/metadata/', json=PROGRESS_DATA, status=200)

        client.onboarding.start_step(user_id='user-123', step_key='welcome', metadata={'source': 'menu'},
                                     occurred_at=WHEN)
        client.onboarding.skip_step(user_id='user-123', step_key='tour', occurred_at=WHEN)
        client.onboarding.update_metadata(user_id='user-123', metadata={'plan': 'pro'}, occurred_at=WHEN)

        assert sent_body(0) == {'step_key': 'welcome', 'metadata': {'source': 'menu'}, 'occurred_at': WHEN_ISO}
        assert sent_body(1) == {'step_key': 'tour', 'occurred_at': WHEN_ISO}
        assert sent_body(2) == {'metadata': {'plan': 'pro'}, 'occurred_at': WHEN_ISO}

    @pytest.mark.parametrize('method, path', [
        ('complete_flow', 'complete'),
        ('restart_flow', 'restart'),
        ('abandon_flow', 'abandon'),
    ])
    @responses.activate
    def test_flow_actions_accept_occurred_at(self, client, method, path):
        responses.add(responses.POST, f'{PROGRESS_URL}/{path}/', json=PROGRESS_DATA, status=200)

        getattr(client.onboarding, method)(user_id='user-123', occurred_at=WHEN)
        getattr(client.onboarding, method)(user_id='user-123')

        assert sent_body(0) == {'occurred_at': WHEN_ISO}
        assert sent_body(1) in (None, {})

    @responses.activate
    def test_batch_converts_each_step_time_without_changing_input(self, client):
        responses.add(responses.POST, f'{PROGRESS_URL}/complete-steps/', json=PROGRESS_DATA, status=200)
        steps = [
            {'step_key': 'welcome', 'occurred_at': WHEN},
            {'step_key': 'config', 'step_data': {'ok': True}},
        ]

        client.onboarding.complete_steps(user_id='user-123', steps=steps)

        assert sent_body() == {'steps': [
            {'step_key': 'welcome', 'occurred_at': WHEN_ISO},
            {'step_key': 'config', 'step_data': {'ok': True}},
        ]}
        assert steps[0]['occurred_at'] is WHEN

    def test_batch_rejects_naive_datetime(self, client):
        with pytest.raises(ValueError):
            client.onboarding.complete_steps(
                user_id='user-123', steps=[{'step_key': 'welcome', 'occurred_at': datetime(2026, 10, 20)}],
            )


class TestEmailAdmin:
    @responses.activate
    def test_get_email_rules(self, admin_client):
        rules = [{'event_type': 'flow_started', 'is_enabled': True}]
        responses.add(responses.GET, f'{BASE_URL}/api/onboarding/flows/meu-flow/email-rules/',
                      json=rules, status=200)

        assert admin_client.onboarding.get_email_rules('meu-flow') == rules

    @responses.activate
    def test_list_email_logs_sends_only_given_filters(self, admin_client):
        responses.add(responses.GET, f'{BASE_URL}/api/onboarding/flows/meu-flow/email-logs/',
                      json={'count': 1, 'results': [{'event_type': 'flow_completed'}]}, status=200)

        logs = admin_client.onboarding.list_email_logs(
            'meu-flow', status='failed', user_id='user-123', created_after=WHEN, page=2,
        )

        assert logs == [{'event_type': 'flow_completed'}]
        params = responses.calls[0].request.params
        assert params == {
            'status': 'failed', 'external_user_id': 'user-123', 'created_after': WHEN_ISO,
            'page': '2', 'page_size': '50',
        }

    @responses.activate
    def test_email_logs_summary(self, admin_client):
        summary = {'total': 3, 'by_event_type': []}
        responses.add(responses.GET, f'{BASE_URL}/api/onboarding/flows/meu-flow/email-logs/summary/',
                      json=summary, status=200)

        result = admin_client.onboarding.get_email_logs_summary('meu-flow', event_type='flow_completed',
                                                                created_before='2026-10-01')

        assert result == summary
        assert responses.calls[0].request.params == {
            'event_type': 'flow_completed', 'created_before': '2026-10-01',
        }


class TestUpdateFlow:
    @responses.activate
    def test_patches_given_fields(self, admin_client):
        responses.add(responses.PATCH, f'{BASE_URL}/api/onboarding/flows/meu-flow/',
                      json={'slug': 'meu-flow', 'step_stalled_after_hours': 48}, status=200)

        flow = admin_client.onboarding.update_flow(
            'meu-flow', step_stalled_after_hours=48, email_deadline_days=None,
        )

        assert flow['step_stalled_after_hours'] == 48
        assert sent_body() == {'step_stalled_after_hours': 48, 'email_deadline_days': None}

    def test_requires_a_field(self, admin_client):
        with pytest.raises(ValueError):
            admin_client.onboarding.update_flow('meu-flow')


class TestVersion:
    @responses.activate
    def test_user_agent_carries_package_version(self, client):
        responses.add(responses.POST, f'{PROGRESS_URL}/start-step/', json=PROGRESS_DATA, status=200)

        client.onboarding.start_step(user_id='user-123', step_key='welcome')

        assert __version__ == '1.1.0'
        assert responses.calls[0].request.headers['User-Agent'] == 'atendeaqui-python/1.1.0'
