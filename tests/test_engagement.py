"""Testes para o módulo de engajamento de uso (contrato: AtendeAqui docs/api-engagement-usage.md, seção 4)."""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import responses

from atendeaqui import AtendeAquiClient, UsageResult, ValidationError

BASE_URL = 'https://test.atendeaqui.com.br'
USAGE_URL = f'{BASE_URL}/api/engagement/usage/'

EVENT_ID = '7c9e6679-7425-40de-944b-e07fc1f90ae7'
OK = {'accepted': 1, 'duplicates': 0, 'errors': []}
NOT_FOUND = 'cliente não encontrado'


@pytest.fixture
def admin_client():
    return AtendeAquiClient(api_token='test-token', _base_url=f'{BASE_URL}/api')


def sent_events(mocked_responses):
    return json.loads(mocked_responses.calls[0].request.body)['events']


def page_view(**extra):
    return {
        'type': 'page_view', 'client_id': '1842', 'user_id': '77',
        'feature': 'employers:job_list', 'feature_name': 'Processos seletivos', **extra,
    }


class TestTrack:

    def test_login_is_sent_as_batch_of_one(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, json=OK, status=201)

        result = admin_client.engagement.track(type='login', client_id='1842', user_id='77')

        assert result.accepted == 1
        [event] = sent_events(mocked_responses)
        assert event['type'] == 'login'
        assert event['client_id'] == '1842'
        assert event['user_id'] == '77'
        assert 'feature' not in event

    def test_generates_event_id_and_occurred_at_when_missing(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, json=OK, status=201)

        admin_client.engagement.track(type='login', client_id='1842', user_id='77')

        [event] = sent_events(mocked_responses)
        uuid.UUID(event['event_id'])  # é um UUID válido
        occurred_at = datetime.fromisoformat(event['occurred_at'].replace('Z', '+00:00'))
        assert occurred_at.tzinfo is not None
        assert abs(datetime.now(timezone.utc) - occurred_at) < timedelta(minutes=1)


class TestTrackBatch:

    def test_keeps_given_event_id_and_occurred_at(self, admin_client, mocked_responses):
        """Reenvio de fila: o event_id e o horário originais não podem mudar."""
        mocked_responses.add(responses.POST, USAGE_URL, json=OK, status=201)

        admin_client.engagement.track_batch([page_view(event_id=EVENT_ID, occurred_at='2026-10-20T13:02:15Z')])

        [event] = sent_events(mocked_responses)
        assert event['event_id'] == EVENT_ID
        assert event['occurred_at'] == '2026-10-20T13:02:15Z'

    def test_datetime_occurred_at_is_sent_as_iso_with_timezone(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, json=OK, status=201)
        when = datetime(2026, 10, 20, 13, 2, 15, tzinfo=timezone.utc)

        admin_client.engagement.track_batch([page_view(occurred_at=when)])

        [event] = sent_events(mocked_responses)
        assert datetime.fromisoformat(event['occurred_at'].replace('Z', '+00:00')) == when

    def test_ids_are_sent_as_text(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, json=OK, status=201)

        admin_client.engagement.track_batch([page_view(client_id=1842, user_id=77)])

        [event] = sent_events(mocked_responses)
        assert event['client_id'] == '1842'
        assert event['user_id'] == '77'

    def test_does_not_modify_the_callers_dict(self, admin_client, mocked_responses):
        """A fila do eTalentos guarda o dict: o SDK não pode mexer nele."""
        mocked_responses.add(responses.POST, USAGE_URL, json=OK, status=201)
        event = page_view()

        admin_client.engagement.track_batch([event])

        assert event == page_view()

    def test_each_event_gets_its_own_event_id(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, json={**OK, 'accepted': 2}, status=201)

        admin_client.engagement.track_batch([page_view(), page_view()])

        first, second = sent_events(mocked_responses)
        assert first['event_id'] != second['event_id']

    def test_parses_partial_errors(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, status=201, json={
            'accepted': 3, 'duplicates': 2,
            'errors': [{'index': 4, 'event_id': EVENT_ID, 'code': 'CLIENT_NOT_FOUND', 'error': 'cliente não encontrado'}],
        })

        result = admin_client.engagement.track_batch([page_view(event_id=EVENT_ID)])

        assert isinstance(result, UsageResult)
        assert (result.accepted, result.duplicates) == (3, 2)
        [error] = result.errors
        assert error.index == 4
        assert error.event_id == EVENT_ID
        assert error.is_client_not_found

    def test_other_errors_are_not_client_not_found(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, status=201, json={
            'accepted': 0, 'duplicates': 0, 'errors': [{'index': 0, 'code': 'INVALID_EVENT', 'error': 'feature inválida'}],
        })

        result = admin_client.engagement.track_batch([page_view(feature='Tela Inválida')])

        assert not result.errors[0].is_client_not_found

    def test_empty_batch_is_rejected_before_sending(self, admin_client, mocked_responses):
        with pytest.raises(ValueError):
            admin_client.engagement.track_batch([])
        assert len(mocked_responses.calls) == 0

    def test_more_than_500_events_is_rejected_before_sending(self, admin_client, mocked_responses):
        with pytest.raises(ValueError):
            admin_client.engagement.track_batch([page_view() for _ in range(501)])
        assert len(mocked_responses.calls) == 0

    def test_invalid_envelope_raises_validation_error(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, status=400,
                             json={'events': ['Envie de 1 a 500 eventos.']})

        with pytest.raises(ValidationError):
            admin_client.engagement.track_batch([page_view()])


def body_events(mocked_responses, call):
    return json.loads(mocked_responses.calls[call].request.body)['events']


class TestCompanyMissing:

    def test_missing_client_is_created_and_its_events_resent(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, status=201, json={
            'accepted': 1, 'duplicates': 0,
            'errors': [{'index': 1, 'event_id': 'e2', 'code': 'CLIENT_NOT_FOUND', 'error': NOT_FOUND}],
        })
        mocked_responses.add(responses.POST, USAGE_URL, status=201, json=OK)
        created = []

        result = admin_client.engagement.track_batch(
            [page_view(event_id='e1'), page_view(event_id='e2', client_id='99')],
            on_client_missing=created.extend,
        )

        assert created == ['99']
        assert [event['event_id'] for event in body_events(mocked_responses, 1)] == ['e2']
        assert result.accepted == 2
        assert result.errors == []

    def test_resend_keeps_the_event_id_generated_on_the_first_send(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, status=201, json={
            'accepted': 0, 'duplicates': 0,
            'errors': [{'index': 0, 'event_id': None, 'code': 'CLIENT_NOT_FOUND', 'error': NOT_FOUND}],
        })
        mocked_responses.add(responses.POST, USAGE_URL, status=201, json=OK)

        admin_client.engagement.track_batch([page_view()], on_client_missing=lambda ids: None)

        [first] = body_events(mocked_responses, 0)
        [resent] = body_events(mocked_responses, 1)
        assert resent['event_id'] == first['event_id']
        assert resent['occurred_at'] == first['occurred_at']

    def test_error_index_of_the_resend_points_to_the_original_list(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, status=201, json={
            'accepted': 2, 'duplicates': 0,
            'errors': [{'index': 2, 'event_id': 'e3', 'code': 'CLIENT_NOT_FOUND', 'error': NOT_FOUND}],
        })
        mocked_responses.add(responses.POST, USAGE_URL, status=201, json={
            'accepted': 0, 'duplicates': 0,
            'errors': [{'index': 0, 'event_id': 'e3', 'code': 'CLIENT_NOT_FOUND', 'error': NOT_FOUND}],
        })

        result = admin_client.engagement.track_batch(
            [page_view(event_id='e1'), page_view(event_id='e2'), page_view(event_id='e3')],
            on_client_missing=lambda ids: None,
        )

        [error] = result.errors
        assert error.index == 2
        assert len(mocked_responses.calls) == 2  # reenvia uma vez só

    def test_without_the_callback_errors_come_back_untouched(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, status=201, json={
            'accepted': 0, 'duplicates': 0,
            'errors': [{'index': 0, 'event_id': 'e1', 'code': 'CLIENT_NOT_FOUND', 'error': NOT_FOUND}],
        })

        result = admin_client.engagement.track_batch([page_view(event_id='e1')])

        assert result.errors[0].is_client_not_found
        assert len(mocked_responses.calls) == 1

    def test_other_errors_are_not_resent(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, status=201, json={
            'accepted': 0, 'duplicates': 0,
            'errors': [{'index': 0, 'event_id': 'e1', 'code': 'INVALID_EVENT', 'error': 'feature inválida'}],
        })
        called = []

        result = admin_client.engagement.track_batch(
            [page_view(event_id='e1')], on_client_missing=called.append,
        )

        assert called == []
        assert len(result.errors) == 1
        assert len(mocked_responses.calls) == 1

    def test_callback_error_reaches_the_caller(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, status=201, json={
            'accepted': 0, 'duplicates': 0,
            'errors': [{'index': 0, 'event_id': 'e1', 'code': 'CLIENT_NOT_FOUND', 'error': NOT_FOUND}],
        })

        def crm_down(ids):
            raise RuntimeError('CRM fora do ar')

        with pytest.raises(RuntimeError):
            admin_client.engagement.track_batch([page_view(event_id='e1')], on_client_missing=crm_down)
        assert len(mocked_responses.calls) == 1
