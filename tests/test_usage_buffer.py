"""Testes do bloquinho de eventos de uso (UsageBuffer)."""
import json
import threading
from datetime import datetime, timezone

import pytest

from atendeaqui import UsageBuffer

EVENT_ID = '7c9e6679-7425-40de-944b-e07fc1f90ae7'


def login(user_id='77', **extra):
    return {'type': 'login', 'company_platform_id': '1842', 'user_id': user_id, **extra}


class Recorder:
    """Faz o papel do send: guarda cada lote e avisa quando chega um."""

    def __init__(self):
        self.batches = []
        self.arrived = threading.Event()

    def __call__(self, events):
        self.batches.append(events)
        self.arrived.set()


class TestAdd:

    def test_generates_event_id_and_occurred_at(self):
        buffer = UsageBuffer(send=Recorder(), background=False)

        event = buffer.add(**login())

        assert event['event_id']
        assert event['occurred_at']

    def test_keeps_the_given_event_id(self):
        buffer = UsageBuffer(send=Recorder(), background=False)

        event = buffer.add(**login(event_id=EVENT_ID))

        assert event['event_id'] == EVENT_ID

    def test_event_can_travel_as_json(self):
        """O Celery manda o lote em JSON: nada de datetime nem número nos ids."""
        buffer = UsageBuffer(send=Recorder(), background=False)

        event = buffer.add(
            type='login', company_platform_id=1842, user_id=77,
            occurred_at=datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
        )

        assert json.loads(json.dumps(event)) == event
        assert event['occurred_at'] == '2026-10-30T12:00:00+00:00'
        assert event['company_platform_id'] == '1842'

    def test_full_buffer_drops_the_oldest(self):
        send = Recorder()
        buffer = UsageBuffer(send=send, max_size=3, background=False)

        for user_id in ['1', '2', '3', '4', '5']:
            buffer.add(**login(user_id))
        buffer.flush()

        [batch] = send.batches
        assert [event['user_id'] for event in batch] == ['3', '4', '5']

    def test_batch_size_above_the_api_limit_is_rejected(self):
        with pytest.raises(ValueError):
            UsageBuffer(send=Recorder(), batch_size=501)


class TestFlush:

    def test_sends_in_batches_of_batch_size(self):
        send = Recorder()
        buffer = UsageBuffer(send=send, background=False)

        for _ in range(250):
            buffer.add(**login())
        buffer.flush()

        assert [len(batch) for batch in send.batches] == [100, 100, 50]
        assert len(buffer) == 0

    def test_empty_buffer_sends_nothing(self):
        send = Recorder()
        buffer = UsageBuffer(send=send, background=False)

        buffer.flush()

        assert send.batches == []

    def test_send_error_keeps_the_rest_for_later(self):
        def send(events):
            raise ConnectionError('sem broker')

        buffer = UsageBuffer(send=send, batch_size=2, background=False)
        for _ in range(5):
            buffer.add(**login())

        with pytest.raises(ConnectionError):
            buffer.flush()
        assert len(buffer) == 3  # o lote que falhou se perdeu; o resto ficou


class TestHelperThread:

    def test_full_batch_wakes_the_helper_without_waiting_the_interval(self):
        send = Recorder()
        buffer = UsageBuffer(send=send, batch_size=2, interval=60)

        buffer.add(**login())
        buffer.add(**login())

        assert send.arrived.wait(timeout=5), 'a ajudante não enviou o lote cheio'
        assert len(send.batches[0]) == 2

    def test_helper_survives_a_send_error(self, caplog):
        send = Recorder()
        failed = threading.Event()

        def flaky_send(events):
            if not failed.is_set():
                failed.set()
                raise ConnectionError('sem broker')
            send(events)

        buffer = UsageBuffer(send=flaky_send, batch_size=1, interval=60)

        buffer.add(**login('1'))
        assert failed.wait(timeout=5)
        buffer.add(**login('2'))

        assert send.arrived.wait(timeout=5), 'a ajudante parou depois do erro'
        assert send.batches[0][0]['user_id'] == '2'
        assert 'falha ao enviar eventos de uso' in caplog.text
