"""
Módulo de Engajamento de Uso do SDK AtendeAqui.

Acessado via client.engagement:

    from atendeaqui import AtendeAquiClient

    client = AtendeAquiClient(api_token="...")
    client.engagement.track(type="login", company_platform_id="1842", user_id="77")
    client.engagement.track_batch([
        {"type": "page_view", "company_platform_id": "1842", "user_id": "77",
         "feature": "employers:job_list", "feature_name": "Processos seletivos"},
    ])

Contrato: AtendeAqui `docs/api-engagement-usage.md`, seção 4.

Quem guarda eventos numa fila para enviar depois deve gerar o `event_id` ao
enfileirar e passá-lo explicitamente: é ele que faz o reenvio não duplicar.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .models import UsageResult

if TYPE_CHECKING:
    from .._http import HttpClient

MAX_BATCH_SIZE = 500


def _prepare_event(event: dict) -> dict:
    """Devolve uma cópia do evento pronta para o contrato.

    - `event_id` e `occurred_at` só são gerados quando não vieram.
    - `occurred_at` em datetime vira ISO 8601 com fuso.
    - `company_platform_id` e `user_id` vão como texto.
    - Não altera o dict recebido.
    """

    # 1) Copia: o dict original (da fila do eTalentos) não pode mudar
    prepared = dict(event)

    # 2) Sem número de rastreio? Gera um. Com número? NÃO mexe.
    if not prepared.get('event_id'):
        prepared['event_id'] = str(uuid.uuid4())

    # 3) Sem data? Usa agora. Data em datetime? Vira texto
    occurred_at = prepared.get('occurred_at')
    if occurred_at is None:
        prepared['occurred_at'] = datetime.now(timezone.utc).isoformat()
    elif isinstance(occurred_at, datetime):
        prepared['occurred_at'] = occurred_at.isoformat()

    # 4) IDs sempre como texto
    prepared['company_platform_id'] = str(prepared['company_platform_id'])
    prepared['user_id'] = str(prepared['user_id'])

    return prepared


class EngagementModule:
    """
    Módulo de Engajamento de Uso — acesso via client.engagement.

    Requer api_token (Bearer token). A empresa precisa existir no CRM
    (client.crm.upsert_company) antes dos eventos dela.
    """

    def __init__(self, http: HttpClient):
        self._http = http

    def track(
        self,
        type: str,
        company_platform_id: str,
        user_id: str,
        feature: str | None = None,
        feature_name: str | None = None,
        event_id: str | None = None,
        occurred_at: datetime | str | None = None,
    ) -> UsageResult:
        """
        Envia um único evento (atalho para um lote de 1).

        Args:
            type: "login" ou "page_view".
            company_platform_id: platform_id da empresa no CRM.
            user_id: ID do usuário na plataforma.
            feature: Chave estável da tela (só no page_view), ex.: "employers:job_list".
            feature_name: Nome exibido da tela (só no page_view).
            event_id: UUID do evento. Gerado se omitido.
            occurred_at: Quando aconteceu. Agora (UTC) se omitido.
        """
        event = {'type': type, 'company_platform_id': company_platform_id, 'user_id': user_id}
        for key, value in (('feature', feature), ('feature_name', feature_name),
                           ('event_id', event_id), ('occurred_at', occurred_at)):
            if value is not None:
                event[key] = value
        return self.track_batch([event])

    def track_batch(self, events: list[dict]) -> UsageResult:
        """
        Envia de 1 a 500 eventos num lote.

        Cada evento é gravado individualmente: os que tiverem problema voltam
        em `UsageResult.errors` (resposta 201), sem derrubar o lote. Reenviar
        com os mesmos `event_id` conta como `duplicates`, não como erro.

        Raises:
            ValueError: lista vazia ou com mais de 500 eventos.
            ValidationError: envelope recusado pelo AtendeAqui (400).
        """
        if not events:
            raise ValueError('Envie ao menos 1 evento.')
        if len(events) > MAX_BATCH_SIZE:
            raise ValueError(f'Envie no máximo {MAX_BATCH_SIZE} eventos por lote.')

        payload = {'events': [_prepare_event(event) for event in events]}
        data = self._http.post('engagement/usage/', json=payload)
        return UsageResult.from_dict(data)
