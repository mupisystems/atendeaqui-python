"""
Cliente principal do SDK AtendeAqui.

Uso:

    from atendeaqui import AtendeAquiClient

    # API pública + admin
    client = AtendeAquiClient(api_token="seu-bearer-token")
    client.onboarding.start_flow(flow_key="uuid-do-flow", user_id="user-123")
    client.clients.list()

    # Somente onboarding (sem api_token)
    client = AtendeAquiClient(flow_key="uuid-do-flow")
    client.onboarding.start_flow(user_id="user-123")
"""
from __future__ import annotations

from ._http import HttpClient
from .clients import ClientsModule
from .onboarding import OnboardingModule

PRODUCTION_URL = 'https://api.atendeaqui.com.br/v1'
SANDBOX_URL = 'https://api.homolog.atendeaqui.com.br/v1'


class AtendeAquiClient:
    """
    Cliente unificado para a plataforma AtendeAqui.

    Expõe módulos como atributos:
    - client.clients — API de Clientes (requer api_token)
    - client.onboarding — API de Onboarding

    Args:
        api_token: Bearer token para endpoints administrativos (enviado
                   no header Authorization). Necessário para list_flows,
                   get_analytics, clients, etc.
        flow_key: UUID público de um flow de onboarding padrão.
                  Se fornecido, será usado como default nos métodos
                  de onboarding (pode ser sobrescrito por chamada).
        sandbox: Se True, usa o ambiente de homologação
                 (api.homolog.atendeaqui.com.br/v1). Padrão: False (produção).
        timeout: Timeout em segundos para requisições HTTP. Padrão: 30.

    Pelo menos um de ``api_token`` ou ``flow_key`` deve ser fornecido.
    """

    def __init__(
        self,
        api_token: str | None = None,
        flow_key: str | None = None,
        sandbox: bool = False,
        timeout: int = 30,
        *,
        _base_url: str | None = None,
    ):
        if not api_token and not flow_key:
            raise ValueError(
                'Forneça api_token (para API admin) e/ou flow_key (para onboarding).'
            )

        # Montar headers de autenticação
        headers: dict = {}
        if api_token:
            headers['Authorization'] = f'Bearer {api_token}'

        self._http = HttpClient(
            base_url=_base_url or (SANDBOX_URL if sandbox else PRODUCTION_URL),
            headers=headers,
            timeout=timeout,
        )

        # Inicializar módulos
        self._clients = ClientsModule(self._http)
        self._onboarding = OnboardingModule(self._http, default_flow_key=flow_key)

    @property
    def clients(self) -> ClientsModule:
        """Módulo de Clientes — CRUD de clientes e equipe (requer api_token)."""
        return self._clients

    @property
    def onboarding(self) -> OnboardingModule:
        """Módulo de Onboarding — gerenciar flows, progresso e analytics."""
        return self._onboarding

    # Futuros módulos:
    #
    # @property
    # def tickets(self) -> TicketsModule:
    #     return self._tickets
