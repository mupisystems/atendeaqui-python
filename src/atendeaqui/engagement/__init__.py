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

Para anotar agora e enviar depois, use o UsageBuffer (engagement/buffer.py):
ele gera o `event_id` na anotação, e é esse id que faz o reenvio não duplicar.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

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

    def track_batch(
        self,
        events: list[dict],
        on_company_missing: Callable[[set[str]], object] | None = None,
    ) -> UsageResult:
        """
        Envia de 1 a 500 eventos num lote.

        Cada evento é gravado individualmente: os que tiverem problema voltam
        em `UsageResult.errors` (resposta 201), sem derrubar o lote. Reenviar
        com os mesmos `event_id` conta como `duplicates`, não como erro.

        Args:
            events: Os eventos, nos campos de track().
            on_company_missing: Função chamada com os company_platform_id que
                ainda não existem no CRM. Ela deve cadastrá-los
                (client.crm.upsert_company); depois o SDK reenvia, uma vez
                só, os eventos dessas empresas, com o mesmo event_id. Sem
                ela, esses eventos voltam em `errors`.

        Raises:
            ValueError: lista vazia ou com mais de 500 eventos.
            ValidationError: envelope recusado pelo AtendeAqui (400).
        """
        if not events:
            raise ValueError('Envie ao menos 1 evento.')
        if len(events) > MAX_BATCH_SIZE:
            raise ValueError(f'Envie no máximo {MAX_BATCH_SIZE} eventos por lote.')

        # Preparados uma vez só: o reenvio usa estes mesmos, com o mesmo event_id
        prepared = [_prepare_event(event) for event in events]
        result = self._send(prepared)

        missing = [
            error for error in result.errors
            if error.is_company_not_found and 0 <= error.index < len(prepared)
        ]
        if not on_company_missing or not missing:
            return result

        indexes = [error.index for error in missing]
        on_company_missing({prepared[i]['company_platform_id'] for i in indexes})
        retry = self._send([prepared[i] for i in indexes])

        # O AtendeAqui conta o index dentro do lote que recebeu. O reenvio é um
        # lote menor: o index volta para a posição na lista original
        for error in retry.errors:
            if 0 <= error.index < len(indexes):
                error.index = indexes[error.index]
        return UsageResult(
            accepted=result.accepted + retry.accepted,
            duplicates=result.duplicates + retry.duplicates,
            errors=[error for error in result.errors if error not in missing] + retry.errors,
        )

    def _send(self, prepared: list[dict]) -> UsageResult:
        data = self._http.post('engagement/usage/', json={'events': prepared})
        return UsageResult.from_dict(data)
