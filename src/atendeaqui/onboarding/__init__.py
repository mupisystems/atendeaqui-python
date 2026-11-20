"""
Módulo de Onboarding do SDK AtendeAqui.

Acessado via client.onboarding:

    from atendeaqui import AtendeAquiClient

    client = AtendeAquiClient(api_token="...")
    client.onboarding.start_flow(flow_key="uuid-do-flow", user_id="user-123")
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .models import FlowStructure, UserProgress, WidgetToken, FlowAnalytics

if TYPE_CHECKING:
    from .._http import HttpClient


def _format_occurred_at(occurred_at: datetime | str | None) -> str | None:
    """
    ``occurred_at`` como ISO 8601 para a API.

    datetime sem fuso é recusado: a API o leria no fuso do servidor, e o
    evento ficaria registrado horas antes ou depois do que aconteceu.
    """
    if occurred_at is None or isinstance(occurred_at, str):
        return occurred_at
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise ValueError(
            'occurred_at precisa ter fuso horário (ex.: datetime.now(timezone.utc) '
            'ou django.utils.timezone.now()).'
        )
    return occurred_at.isoformat()


def _with_occurred_at(body: dict, occurred_at: datetime | str | None) -> dict:
    """Inclui occurred_at no corpo quando informado."""
    formatted = _format_occurred_at(occurred_at)
    if formatted:
        body['occurred_at'] = formatted
    return body


class OnboardingModule:
    """
    Módulo de Onboarding — acesso via client.onboarding.

    Fornece métodos para a API pública (flow_key) e administrativa (api_token).

    O ``flow_key`` pode ser definido como default na inicialização do client
    (via ``AtendeAquiClient(flow_key=...)``) ou passado por chamada de método.
    O valor passado no método sempre tem prioridade.
    """

    def __init__(self, http: HttpClient, default_flow_key: str | None = None):
        self._http = http
        self._default_flow_key = default_flow_key

    def _resolve_flow_key(self, flow_key: str | None) -> str:
        """Resolve o flow_key: parâmetro do método > default do client."""
        key = flow_key or self._default_flow_key
        if not key:
            raise ValueError(
                'flow_key é obrigatório. Passe como parâmetro do método '
                'ou defina um default via AtendeAquiClient(flow_key=...).'
            )
        return key

    def _flow_headers(self, flow_key: str) -> dict:
        """Retorna header X-Onboarding-Key para autenticação do flow."""
        return {'X-Onboarding-Key': flow_key}

    # =========================================================================
    # API PÚBLICA (requer flow_key)
    # =========================================================================

    def get_structure(
        self,
        flow_key: str | None = None,
        language: str | None = None,
    ) -> FlowStructure:
        """
        Retorna a estrutura completa do flow (steps, configuração, idiomas).

        Args:
            flow_key: UUID público do flow. Usa o default do client se omitido.
            language: Código do idioma (ex: "pt-BR", "en-US"). Se omitido, usa o padrão.
        """
        fk = self._resolve_flow_key(flow_key)
        params = {}
        if language:
            params['language'] = language

        data = self._http.get(
            f'onboarding/{fk}/structure/',
            params=params,
            headers=self._flow_headers(fk),
        )
        return FlowStructure.from_dict(data)

    def start_flow(
        self,
        user_id: str,
        flow_key: str | None = None,
        name: str | None = None,
        email: str | None = None,
        metadata: dict | None = None,
        client_id: str | None = None,
        occurred_at: datetime | str | None = None,
    ) -> UserProgress:
        """
        Inicia o flow de onboarding para um usuário externo.

        Se o usuário já iniciou, retorna o progresso existente.

        Args:
            user_id: Identificador único do usuário no sistema externo.
            flow_key: UUID público do flow. Usa o default do client se omitido.
            name: Nome do usuário (usado em e-mails automáticos e busca).
            email: Email do usuário (opcional, mas recomendado para e-mails automáticos).
            metadata: Dados adicionais (ex: empresa, setor, preferred_language).
            client_id: UUID do cliente na organização (opcional, vincula onboarding ao cliente).
            occurred_at: Quando aconteceu na sua aplicação (datetime com fuso ou
                ISO 8601). Use ao enviar depois do fato (fila, reprocessamento,
                carga retroativa). Padrão: horário do servidor.
        """
        fk = self._resolve_flow_key(flow_key)
        body: dict = {'external_user_id': user_id}
        if name:
            body['name'] = name
        if email:
            body['external_user_email'] = email
        if metadata:
            body['metadata'] = metadata
        if client_id:
            body['client_id'] = client_id
        _with_occurred_at(body, occurred_at)

        data = self._http.post(
            f'onboarding/{fk}/start/',
            json=body,
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def get_progress(self, user_id: str, flow_key: str | None = None) -> UserProgress:
        """
        Retorna o progresso atual do usuário no flow.

        Args:
            user_id: Identificador único do usuário no sistema externo.
            flow_key: UUID público do flow. Usa o default do client se omitido.

        Raises:
            NotFoundError: Se o usuário não iniciou o flow.
        """
        fk = self._resolve_flow_key(flow_key)
        data = self._http.get(
            f'onboarding/{fk}/progress/{user_id}/',
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def complete_step(
        self,
        user_id: str,
        step_key: str,
        flow_key: str | None = None,
        step_data: dict | None = None,
        occurred_at: datetime | str | None = None,
    ) -> UserProgress:
        """
        Marca um step como completo e avança no flow.

        Se todos os steps obrigatórios forem completados, o flow é
        automaticamente marcado como COMPLETED.

        Args:
            user_id: Identificador único do usuário no sistema externo.
            step_key: Chave do step a completar.
            flow_key: UUID público do flow. Usa o default do client se omitido.
            step_data: Dados do step (JSON livre).
            occurred_at: Quando aconteceu na sua aplicação (datetime com fuso ou
                ISO 8601). Use ao enviar depois do fato (fila, reprocessamento,
                carga retroativa). Padrão: horário do servidor.

        Raises:
            StepNotFoundError: Se o step_key não existe no flow.
        """
        fk = self._resolve_flow_key(flow_key)
        body: dict = {'step_key': step_key}
        if step_data:
            body['step_data'] = step_data
        _with_occurred_at(body, occurred_at)

        data = self._http.post(
            f'onboarding/{fk}/progress/{user_id}/complete-step/',
            json=body,
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def start_step(
        self,
        user_id: str,
        step_key: str,
        flow_key: str | None = None,
        metadata: dict | None = None,
        occurred_at: datetime | str | None = None,
    ) -> UserProgress:
        """
        Registra que o usuário iniciou um step (sem marcá-lo como completo).

        Útil para rastrear tempo de permanência em cada step e detectar
        abandono antes da conclusão.

        Args:
            user_id: Identificador único do usuário no sistema externo.
            step_key: Chave do step que o usuário iniciou.
            flow_key: UUID público do flow. Usa o default do client se omitido.
            metadata: Dados contextuais opcionais (ex: source, device).
            occurred_at: Quando aconteceu na sua aplicação (datetime com fuso ou
                ISO 8601). Use ao enviar depois do fato (fila, reprocessamento,
                carga retroativa). Padrão: horário do servidor.

        Raises:
            StepNotFoundError: Se o step_key não existe no flow.
        """
        fk = self._resolve_flow_key(flow_key)
        body: dict = {'step_key': step_key}
        if metadata:
            body['metadata'] = metadata
        _with_occurred_at(body, occurred_at)

        data = self._http.post(
            f'onboarding/{fk}/progress/{user_id}/start-step/',
            json=body,
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def complete_steps(
        self,
        user_id: str,
        steps: list[dict],
        flow_key: str | None = None,
    ) -> UserProgress:
        """
        Completa múltiplos steps de uma vez (batch).

        Args:
            user_id: Identificador único do usuário no sistema externo.
            steps: Lista de dicts com step_key e, opcionais, step_data e occurred_at
                (datetime com fuso ou ISO 8601: quando cada step foi concluído).
                Ex: [{"step_key": "welcome"}, {"step_key": "config", "step_data": {...}}]
            flow_key: UUID público do flow. Usa o default do client se omitido.

        Raises:
            ValidationError: Se algum step_key não existe.
        """
        fk = self._resolve_flow_key(flow_key)
        items = []
        for step in steps:
            item = {key: value for key, value in step.items() if key != 'occurred_at'}
            items.append(_with_occurred_at(item, step.get('occurred_at')))
        data = self._http.post(
            f'onboarding/{fk}/progress/{user_id}/complete-steps/',
            json={'steps': items},
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def skip_step(
        self,
        user_id: str,
        step_key: str,
        flow_key: str | None = None,
        occurred_at: datetime | str | None = None,
    ) -> UserProgress:
        """
        Pula um step opcional.

        Args:
            user_id: Identificador único do usuário no sistema externo.
            step_key: Chave do step a pular.
            flow_key: UUID público do flow. Usa o default do client se omitido.
            occurred_at: Quando aconteceu na sua aplicação (datetime com fuso ou
                ISO 8601). Use ao enviar depois do fato (fila, reprocessamento,
                carga retroativa). Padrão: horário do servidor.

        Raises:
            StepNotSkippableError: Se o step é obrigatório.
        """
        fk = self._resolve_flow_key(flow_key)
        data = self._http.post(
            f'onboarding/{fk}/progress/{user_id}/skip-step/',
            json=_with_occurred_at({'step_key': step_key}, occurred_at),
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def complete_flow(
        self,
        user_id: str,
        flow_key: str | None = None,
        occurred_at: datetime | str | None = None,
    ) -> UserProgress:
        """Marca o flow como completo manualmente. ``occurred_at``: quando aconteceu (padrão: agora)."""
        fk = self._resolve_flow_key(flow_key)
        data = self._http.post(
            f'onboarding/{fk}/progress/{user_id}/complete/',
            json=_with_occurred_at({}, occurred_at),
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def restart_flow(
        self,
        user_id: str,
        flow_key: str | None = None,
        occurred_at: datetime | str | None = None,
    ) -> UserProgress:
        """Reinicia o progresso do usuário do zero. ``occurred_at``: quando aconteceu (padrão: agora)."""
        fk = self._resolve_flow_key(flow_key)
        data = self._http.post(
            f'onboarding/{fk}/progress/{user_id}/restart/',
            json=_with_occurred_at({}, occurred_at),
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def abandon_flow(
        self,
        user_id: str,
        flow_key: str | None = None,
        occurred_at: datetime | str | None = None,
    ) -> UserProgress:
        """Marca o flow como abandonado. ``occurred_at``: quando aconteceu (padrão: agora)."""
        fk = self._resolve_flow_key(flow_key)
        data = self._http.post(
            f'onboarding/{fk}/progress/{user_id}/abandon/',
            json=_with_occurred_at({}, occurred_at),
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def update_metadata(
        self,
        user_id: str,
        metadata: dict,
        flow_key: str | None = None,
        occurred_at: datetime | str | None = None,
    ) -> UserProgress:
        """
        Atualiza os metadados do usuário (merge com dados existentes).

        Args:
            user_id: Identificador único do usuário no sistema externo.
            metadata: Dicionário com dados a adicionar/atualizar.
            flow_key: UUID público do flow. Usa o default do client se omitido.
            occurred_at: Quando aconteceu na sua aplicação (datetime com fuso ou
                ISO 8601). Use ao enviar depois do fato (fila, reprocessamento,
                carga retroativa). Padrão: horário do servidor.
        """
        fk = self._resolve_flow_key(flow_key)
        data = self._http.patch(
            f'onboarding/{fk}/progress/{user_id}/metadata/',
            json=_with_occurred_at({'metadata': metadata}, occurred_at),
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def get_widget_token(
        self,
        flow_key: str | None = None,
        user_id: str | None = None,
        client_id: str | None = None,
        ttl: int = 600,
    ) -> WidgetToken:
        """
        Gera um token JWT de curta duração para uso em widgets frontend.

        Args:
            flow_key: UUID público do flow. Usa o default do client se omitido.
            user_id: ID do usuário externo (opcional).
            client_id: ID do cliente (opcional).
            ttl: Tempo de vida em segundos (60-3600). Padrão: 600.
        """
        fk = self._resolve_flow_key(flow_key)
        body: dict = {'ttl': ttl}
        if user_id:
            body['external_user_id'] = user_id
        if client_id:
            body['client_id'] = client_id

        data = self._http.post(
            'onboarding/auth/token/',
            json=body,
            headers=self._flow_headers(fk),
        )
        return WidgetToken.from_dict(data)

    # =========================================================================
    # API ADMINISTRATIVA (requer api_token)
    # =========================================================================

    def list_flows(self, page: int = 1, page_size: int = 50) -> list[dict]:
        """Lista todos os flows da organização (requer api_token)."""
        params = {'page': page, 'page_size': page_size}
        data = self._http.get('onboarding/flows/', params=params)
        return data.get('results', data) if isinstance(data, dict) else data

    def get_flow(self, slug: str) -> dict:
        """Retorna detalhes completos de um flow (requer api_token)."""
        return self._http.get(f'onboarding/flows/{slug}/')

    def update_flow(self, slug: str, **fields) -> dict:
        """
        Atualiza campos de um flow (PATCH; requer api_token com escrita).

        Exemplo, automação de acompanhamento::

            client.onboarding.update_flow(
                'meu-flow',
                step_stalled_after_hours=48,   # step iniciado e não concluído = travado
                email_deadline_days=30,          # sem e-mails depois de 30 dias do início (None = sem prazo)
                abandon_after_inactive_days=30,  # abandona quem fica 30 dias sem atividade (None = nunca)
            )

        E-mails do flow: email_provider_config (id do provedor, ex.: Postmark do
        produto), email_from_name, email_blocks, email_dimensions,
        email_message_stream e email_brand ({"logo_url", "color", "signature",
        "footer"}). Cada um altera só a sua chave no flow_config; None a remove.

        Também aceita os demais campos editáveis do flow (name, description,
        is_active...). Evite mandar flow_config inteiro: ele substitui todas as
        chaves.
        """
        if not fields:
            raise ValueError('Informe ao menos um campo para atualizar.')
        return self._http.patch(f'onboarding/flows/{slug}/', json=fields)

    def get_analytics(self, slug: str) -> FlowAnalytics:
        """Retorna analytics e métricas de um flow (requer api_token)."""
        data = self._http.get(f'onboarding/flows/{slug}/analytics/')
        return FlowAnalytics.from_dict(data)

    def list_progress(self, slug: str, page: int = 1, page_size: int = 50) -> list[dict]:
        """Lista progresso de todos os usuários em um flow (requer api_token)."""
        params = {'page': page, 'page_size': page_size}
        data = self._http.get(f'onboarding/flows/{slug}/progress/', params=params)
        return data.get('results', data) if isinstance(data, dict) else data

    def get_email_rules(self, slug: str) -> list[dict]:
        """Regras de e-mail automático do flow, ativas ou não (requer api_token)."""
        return self._http.get(f'onboarding/flows/{slug}/email-rules/')

    @staticmethod
    def _email_log_filters(
        status: str | None,
        event_type: str | None,
        user_id: str | None,
        created_after: datetime | str | None,
        created_before: datetime | str | None,
    ) -> dict:
        params = {
            'status': status,
            'event_type': event_type,
            'external_user_id': user_id,
            'created_after': created_after.isoformat() if isinstance(created_after, datetime) else created_after,
            'created_before': created_before.isoformat() if isinstance(created_before, datetime) else created_before,
        }
        return {key: value for key, value in params.items() if value}

    def list_email_logs(
        self,
        slug: str,
        status: str | None = None,
        event_type: str | None = None,
        user_id: str | None = None,
        created_after: datetime | str | None = None,
        created_before: datetime | str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[dict]:
        """
        E-mails gerados para os usuários do flow, do mais recente ao mais
        antigo, sem o corpo da mensagem (requer api_token).

        Args:
            slug: Slug do flow.
            status: pending, queued, sent, failed ou skipped.
            event_type: Evento da regra (ex.: flow_started, flow_completed, reminder).
            user_id: ID do usuário no sistema externo.
            created_after / created_before: data (ex.: "2026-10-01") ou datetime.
        """
        params = self._email_log_filters(status, event_type, user_id, created_after, created_before)
        params.update(page=page, page_size=page_size)
        data = self._http.get(f'onboarding/flows/{slug}/email-logs/', params=params)
        return data.get('results', data) if isinstance(data, dict) else data

    def get_email_logs_summary(
        self,
        slug: str,
        status: str | None = None,
        event_type: str | None = None,
        user_id: str | None = None,
        created_after: datetime | str | None = None,
        created_before: datetime | str | None = None,
    ) -> dict:
        """
        Totais dos e-mails do flow por tipo de evento: por status, aberturas,
        cliques e bounces (requer api_token). Aceita os filtros de list_email_logs.

        Retorno: ``{"total": int, "by_event_type": [{"event_type", "total",
        "opened", "clicked", "bounced", "by_status": {...}}, ...]}``
        """
        params = self._email_log_filters(status, event_type, user_id, created_after, created_before)
        return self._http.get(f'onboarding/flows/{slug}/email-logs/summary/', params=params)

    # =========================================================================
    # E-MAILS: REGRAS, PEÇAS E DESCADASTRO (requer api_token)
    # =========================================================================

    def create_email_rule(self, slug: str, event_type: str, **fields) -> dict:
        """
        Cria a regra de e-mail de um evento (uma por evento). Começa em
        simulação: o e-mail é montado e registrado, sem ir para o destinatário.

        Campos opcionais: is_enabled, send_mode ("simulate" ou "send"),
        email_provider_config, delay_minutes, reminder_after_hours (obrigatório
        para "reminder"), max_reminders, send_only_business_hours.
        """
        return self._http.post(f'onboarding/flows/{slug}/email-rules/', json={'event_type': event_type, **fields})

    def update_email_rule(self, slug: str, rule_id: int, **fields) -> dict:
        """
        Altera campos da regra. send_mode="send" exige provedor (na regra ou
        no flow), email_from_name e email_brand.footer no flow.
        """
        if not fields:
            raise ValueError('Informe ao menos um campo para atualizar.')
        return self._http.patch(f'onboarding/flows/{slug}/email-rules/{rule_id}/', json=fields)

    def delete_email_rule(self, slug: str, rule_id: int) -> None:
        """Exclui a regra de e-mail."""
        self._http.delete(f'onboarding/flows/{slug}/email-rules/{rule_id}/')

    def list_email_pieces(
        self,
        slug: str,
        block: str | None = None,
        event_type: str | None = None,
        step_key: str | None = None,
        status: str | None = None,
        language: str | None = None,
        conditions: dict | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[dict]:
        """
        Peças de e-mail do flow.

        Args:
            status: draft, approved ou archived.
            conditions: filtra por condição, ex.: {"segment": "estetica"}.
        """
        params: dict = {
            'block': block, 'event_type': event_type, 'step_key': step_key,
            'status': status, 'language': language, 'page': page, 'page_size': page_size,
        }
        params = {key: value for key, value in params.items() if value is not None}
        if conditions:
            params['condition'] = [f'{key}:{value}' for key, value in conditions.items()]
        data = self._http.get(f'onboarding/flows/{slug}/email-pieces/', params=params)
        return data.get('results', data) if isinstance(data, dict) else data

    def get_email_piece(self, slug: str, piece_id: int) -> dict:
        """Detalhe da peça, com o histórico de versões e os problemas que impedem aprovar."""
        return self._http.get(f'onboarding/flows/{slug}/email-pieces/{piece_id}/')

    def create_email_piece(
        self,
        slug: str,
        block: str,
        body: str,
        subject: str | None = None,
        event_type: str | None = None,
        step_key: str | None = None,
        conditions: dict | None = None,
        language: str | None = None,
        preheader: str | None = None,
        cta_label: str | None = None,
        source: str | None = None,
    ) -> dict:
        """
        Cria uma peça em rascunho.

        Args:
            block: "corpo" (o e-mail, exige subject) ou outro bloco do flow
                (flow_config.email_blocks), usado no corpo como {BLOCO:nome}.
            body: texto com variáveis {NOME}, {ETAPA}, {LINK_ETAPA},
                {PROGRESSO}, {DADO:chave} e, no corpo, {BLOCO:nome}.
            event_type / step_key / conditions: onde a peça vale (vazio = sempre).
            language: padrão, o idioma do flow.
            source: "manual" (padrão) ou "ai".
        """
        body_data: dict = {'block': block, 'body': body}
        optional = {
            'subject': subject, 'event_type': event_type, 'step_key': step_key, 'conditions': conditions,
            'language': language, 'preheader': preheader, 'cta_label': cta_label, 'source': source,
        }
        body_data.update({key: value for key, value in optional.items() if value is not None})
        return self._http.post(f'onboarding/flows/{slug}/email-pieces/', json=body_data)

    def update_email_piece(self, slug: str, piece_id: int, **fields) -> dict:
        """
        Edita a peça. Rascunho: altera no lugar. Aprovada ou arquivada: a API
        cria uma nova versão em rascunho e a devolve (o "id" muda); a aprovada
        segue valendo até a nova ser aprovada.
        """
        if not fields:
            raise ValueError('Informe ao menos um campo para atualizar.')
        return self._http.patch(f'onboarding/flows/{slug}/email-pieces/{piece_id}/', json=fields)

    def delete_email_piece(self, slug: str, piece_id: int) -> None:
        """Exclui um rascunho (peças aprovadas são arquivadas com archive_email_piece)."""
        self._http.delete(f'onboarding/flows/{slug}/email-pieces/{piece_id}/')

    def approve_email_piece(self, slug: str, piece_id: int) -> dict:
        """
        Aprova a peça e arquiva a aprovada anterior da mesma chave.

        Raises:
            ValidationError: a peça tem problemas (variável ou bloco
                desconhecido, condição fora de email_dimensions...); a lista
                completa está em ``exc.response.json()["problems"]``.
        """
        return self._http.post(f'onboarding/flows/{slug}/email-pieces/{piece_id}/approve/')

    def archive_email_piece(self, slug: str, piece_id: int) -> dict:
        """Tira a peça de uso."""
        return self._http.post(f'onboarding/flows/{slug}/email-pieces/{piece_id}/archive/')

    def preview_email(
        self,
        slug: str,
        event_type: str,
        step_key: str | None = None,
        user_id: str | None = None,
        name: str | None = None,
        metadata: dict | None = None,
        steps_completed: list[str] | None = None,
        language: str | None = None,
        include_drafts: bool = True,
    ) -> dict:
        """
        Monta o e-mail de um evento como sairia, sem enviar.

        Com user_id usa o progresso real do usuário; sem ele, um usuário de
        exemplo (name, metadata, steps_completed, language). Por padrão inclui
        rascunhos, para revisar antes de aprovar.

        Retorno: subject, preheader, body_text, body_html, language,
        missing_reason, pieces (id, block, version, status) e choices (por que
        cada peça foi escolhida).
        """
        body: dict = {'event_type': event_type, 'include_drafts': include_drafts}
        optional = {
            'step_key': step_key, 'external_user_id': user_id, 'name': name, 'metadata': metadata,
            'steps_completed': steps_completed, 'language': language,
        }
        body.update({key: value for key, value in optional.items() if value is not None})
        return self._http.post(f'onboarding/flows/{slug}/email-pieces/preview/', json=body)

    def get_email_coverage(self, slug: str, language: str | None = None) -> dict:
        """
        Cobertura das peças: por chave (bloco, evento, etapa, condições), a
        versão aprovada e o rascunho em aberto. events_without_generic_body
        lista regras ativas em que parte dos usuários ficaria sem e-mail.
        """
        params = {'language': language} if language else None
        return self._http.get(f'onboarding/flows/{slug}/email-pieces/coverage/', params=params)

    def set_email_subscription(self, slug: str, user_id: str, unsubscribed: bool) -> dict:
        """
        Cancela (True) ou reativa (False) os e-mails de onboarding de um
        usuário, para sincronizar a preferência que ele marcou no produto.
        Cancelar também descarta os e-mails na fila. Reativar só com o
        consentimento da pessoa.

        Retorno: external_user_id, email_unsubscribed, email_unsubscribed_at,
        email_unsubscribed_source.
        """
        return self._http.patch(
            f'onboarding/flows/{slug}/progress/{user_id}/email-subscription/',
            json={'unsubscribed': bool(unsubscribed)},
        )
