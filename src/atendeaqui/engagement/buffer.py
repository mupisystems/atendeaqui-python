"""
Bloquinho de eventos de uso: anota agora e envia em lote depois, fora da requisição.

    from atendeaqui import AtendeAquiClient, UsageBuffer

    client = AtendeAquiClient(api_token="...")
    buffer = UsageBuffer(send=client.engagement.track_batch)
    buffer.add(type="login", client_id="3f2b...", user_id="77")

Cada processo tem o seu bloquinho. Uma thread ajudante esvazia o bloquinho a
cada `interval` segundos, ou antes, quando ele junta `batch_size` eventos.
No uWSGI, ligue `enable-threads`: sem isso a thread não roda.
"""
from __future__ import annotations

import atexit
import logging
import threading
from collections import deque
from typing import Callable

from . import MAX_BATCH_SIZE, _prepare_event

logger = logging.getLogger(__name__)


class UsageBuffer:
    """
    Bloquinho em memória de eventos de uso.

    Args:
        send: Função que recebe uma lista de eventos e os envia. Ex.:
            client.engagement.track_batch, ou uma função que entrega o lote
            a uma fila (Celery). Os eventos chegam só com texto: podem ir
            por JSON.
        batch_size: Eventos por lote, de 1 a 500. Ao juntar essa quantidade,
            a ajudante é acordada sem esperar o intervalo.
        interval: Segundos entre uma esvaziada e outra.
        max_size: Limite do bloquinho. Cheio, o evento mais antigo sai para o
            novo entrar: o AtendeAqui fora do ar não pode encher a memória.
        background: False não liga a thread nem o envio na saída do processo;
            quem usa chama flush(). Para testes.
    """

    def __init__(
        self,
        send: Callable[[list[dict]], object],
        batch_size: int = 100,
        interval: float = 10,
        max_size: int = 5000,
        background: bool = True,
    ):
        if not 1 <= batch_size <= MAX_BATCH_SIZE:
            raise ValueError(f'batch_size deve ficar entre 1 e {MAX_BATCH_SIZE}.')
        self._send = send
        self._batch_size = batch_size
        self._interval = interval
        self._background = background
        self._events: deque[dict] = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._wake_up = threading.Event()
        self._helper: threading.Thread | None = None
        if background:
            # Processo reciclado (ex.: max-requests do uWSGI): envia o que sobrou antes de sair
            atexit.register(self._flush_and_log)

    def __len__(self) -> int:
        return len(self._events)

    def add(self, **event) -> dict:
        """
        Anota um evento e devolve como ele ficou anotado.

        event_id e occurred_at são gerados agora, se não vieram: o reenvio de
        um lote não conta o evento duas vezes, e a hora é a da ação, não a do
        envio.
        """
        event = _prepare_event(event)
        with self._lock:
            self._events.append(event)
            full = len(self._events) >= self._batch_size
            if self._background:
                self._start_helper()
        if full:
            self._wake_up.set()
        return event

    def flush(self) -> None:
        """
        Envia tudo o que está no bloquinho, em lotes de batch_size.

        Erro no send sobe para quem chamou: o lote que falhou se perde e o
        resto fica para a próxima vez.
        """
        while batch := self._take_batch():
            self._send(batch)

    def _take_batch(self) -> list[dict]:
        with self._lock:
            size = min(self._batch_size, len(self._events))
            return [self._events.popleft() for _ in range(size)]

    def _flush_and_log(self) -> None:
        try:
            self.flush()
        except Exception:
            logger.exception('UsageBuffer: falha ao enviar eventos de uso')

    def _start_helper(self) -> None:
        """
        Liga a ajudante deste processo, se ela ainda não estiver rodando.

        Chamado no add, e não no __init__: quando o servidor importa o código e
        só depois cria os processos (fork, como o uWSGI sem lazy-apps), a
        thread não passa para os processos novos.
        """
        if self._helper is None or not self._helper.is_alive():
            self._helper = threading.Thread(
                target=self._helper_loop, name='atendeaqui-usage-buffer', daemon=True,
            )
            self._helper.start()

    def _helper_loop(self) -> None:
        while True:
            self._wake_up.wait(self._interval)
            self._wake_up.clear()
            self._flush_and_log()
