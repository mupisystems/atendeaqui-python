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


@pytest.fixture
def admin_client():
    return AtendeAquiClient(api_token='test-token', _base_url=f'{BASE_URL}/api')


def sent_events(mocked_responses):
    return json.loads(mocked_responses.calls[0].request.body)['events']


def page_view(**extra):
    return {
        'type': 'page_view', 'company_platform_id': '1842', 'user_id': '77',
        'feature': 'employers:job_list', 'feature_name': 'Processos seletivos', **extra,
    }


class TestTrack:

    def test_login_is_sent_as_batch_of_one(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, json=OK, status=201)

        result = admin_client.engagement.track(type='login', company_platform_id='1842', user_id='77')

        assert result.accepted == 1
        [event] = sent_events(mocked_responses)
        assert event['type'] == 'login'
        assert event['company_platform_id'] == '1842'
        assert event['user_id'] == '77'
        assert 'feature' not in event

    def test_generates_event_id_and_occurred_at_when_missing(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, json=OK, status=201)

        admin_client.engagement.track(type='login', company_platform_id='1842', user_id='77')

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

        admin_client.engagement.track_batch([page_view(company_platform_id=1842, user_id=77)])

        [event] = sent_events(mocked_responses)
        assert event['company_platform_id'] == '1842'
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
            'errors': [{'index': 4, 'event_id': EVENT_ID, 'error': 'empresa não encontrada'}],
        })

        result = admin_client.engagement.track_batch([page_view(event_id=EVENT_ID)])

        assert isinstance(result, UsageResult)
        assert (result.accepted, result.duplicates) == (3, 2)
        [error] = result.errors
        assert error.index == 4
        assert error.event_id == EVENT_ID
        assert error.is_company_not_found

    def test_other_errors_are_not_company_not_found(self, admin_client, mocked_responses):
        mocked_responses.add(responses.POST, USAGE_URL, status=201, json={
            'accepted': 0, 'duplicates': 0, 'errors': [{'index': 0, 'error': 'feature inválida'}],
        })

        result = admin_client.engagement.track_batch([page_view(feature='Tela Inválida')])

        assert not result.errors[0].is_company_not_found

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
