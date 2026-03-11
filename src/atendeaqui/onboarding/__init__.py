"""
Módulo de Onboarding do SDK AtendeAqui.

Acessado via client.onboarding:

    from atendeaqui import AtendeAquiClient

    client = AtendeAquiClient(api_token="...")
    client.onboarding.start_flow(flow_key="uuid-do-flow", user_id="user-123")
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .models import FlowStructure, UserProgress, WidgetToken, FlowAnalytics

if TYPE_CHECKING:
    from .._http import HttpClient


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

        Raises:
            StepNotFoundError: Se o step_key não existe no flow.
        """
        fk = self._resolve_flow_key(flow_key)
        body: dict = {'step_key': step_key}
        if step_data:
            body['step_data'] = step_data

        data = self._http.post(
            f'onboarding/{fk}/progress/{user_id}/complete-step/',
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
            steps: Lista de dicts com step_key e step_data opcional.
                Ex: [{"step_key": "welcome"}, {"step_key": "config", "step_data": {...}}]
            flow_key: UUID público do flow. Usa o default do client se omitido.

        Raises:
            ValidationError: Se algum step_key não existe.
        """
        fk = self._resolve_flow_key(flow_key)
        data = self._http.post(
            f'onboarding/{fk}/progress/{user_id}/complete-steps/',
            json={'steps': steps},
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def skip_step(
        self,
        user_id: str,
        step_key: str,
        flow_key: str | None = None,
    ) -> UserProgress:
        """
        Pula um step opcional.

        Args:
            user_id: Identificador único do usuário no sistema externo.
            step_key: Chave do step a pular.
            flow_key: UUID público do flow. Usa o default do client se omitido.

        Raises:
            StepNotSkippableError: Se o step é obrigatório.
        """
        fk = self._resolve_flow_key(flow_key)
        data = self._http.post(
            f'onboarding/{fk}/progress/{user_id}/skip-step/',
            json={'step_key': step_key},
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def complete_flow(self, user_id: str, flow_key: str | None = None) -> UserProgress:
        """Marca o flow como completo manualmente."""
        fk = self._resolve_flow_key(flow_key)
        data = self._http.post(
            f'onboarding/{fk}/progress/{user_id}/complete/',
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def restart_flow(self, user_id: str, flow_key: str | None = None) -> UserProgress:
        """Reinicia o progresso do usuário do zero."""
        fk = self._resolve_flow_key(flow_key)
        data = self._http.post(
            f'onboarding/{fk}/progress/{user_id}/restart/',
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def abandon_flow(self, user_id: str, flow_key: str | None = None) -> UserProgress:
        """Marca o flow como abandonado."""
        fk = self._resolve_flow_key(flow_key)
        data = self._http.post(
            f'onboarding/{fk}/progress/{user_id}/abandon/',
            headers=self._flow_headers(fk),
        )
        return UserProgress.from_dict(data)

    def update_metadata(
        self,
        user_id: str,
        metadata: dict,
        flow_key: str | None = None,
    ) -> UserProgress:
        """
        Atualiza os metadados do usuário (merge com dados existentes).

        Args:
            user_id: Identificador único do usuário no sistema externo.
            metadata: Dicionário com dados a adicionar/atualizar.
            flow_key: UUID público do flow. Usa o default do client se omitido.
        """
        fk = self._resolve_flow_key(flow_key)
        data = self._http.patch(
            f'onboarding/{fk}/progress/{user_id}/metadata/',
            json={'metadata': metadata},
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

    def get_analytics(self, slug: str) -> FlowAnalytics:
        """Retorna analytics e métricas de um flow (requer api_token)."""
        data = self._http.get(f'onboarding/flows/{slug}/analytics/')
        return FlowAnalytics.from_dict(data)

    def list_progress(self, slug: str, page: int = 1, page_size: int = 50) -> list[dict]:
        """Lista progresso de todos os usuários em um flow (requer api_token)."""
        params = {'page': page, 'page_size': page_size}
        data = self._http.get(f'onboarding/flows/{slug}/progress/', params=params)
        return data.get('results', data) if isinstance(data, dict) else data
