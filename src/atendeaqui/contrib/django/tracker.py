"""
Regras de engajamento que valem para qualquer aplicação Django.

A aplicação estende EngagementTracker com as regras dela (quem é contabilizado,
se o engajamento está ativo, para onde vão os lotes) e indica a instância em
settings.ATENDEAQUI_ENGAGEMENT_TRACKER.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import Resolver404, resolve
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.module_loading import import_string

from ...engagement.buffer import UsageBuffer

logger = logging.getLogger(__name__)


def get_tracker() -> EngagementTracker:
    """A instância indicada em settings.ATENDEAQUI_ENGAGEMENT_TRACKER."""
    path = getattr(settings, 'ATENDEAQUI_ENGAGEMENT_TRACKER', None)
    if not path:
        raise ImproperlyConfigured(
            'Defina ATENDEAQUI_ENGAGEMENT_TRACKER com o caminho da instância do '
            'EngagementTracker da aplicação (ex.: "app.engagement.tracker").'
        )
    return import_string(path)


class EngagementTracker:
    """
    Identifica telas acessadas e logins e os anota num UsageBuffer.

    A aplicação implementa:
        identify(user): (company_platform_id, user_id) de quem é contabilizado,
            ou None.
        send(events): para onde vai cada lote (ex.: uma task Celery que chama
            client.engagement.track_batch).
        is_active(): opcional; False desliga o registro (padrão: True).

    E pode ajustar os atributos de classe: screen_names, ignored_prefixes,
    ignored_namespaces e ignored_features. Para manter os padrões ao
    acrescentar itens, some aos da classe base, ex.:
    ignored_prefixes = EngagementTracker.ignored_prefixes + ('/api/',).

    Args:
        **buffer_options: repassados ao UsageBuffer (batch_size, interval,
            max_size, background).
    """

    # Nome exibido de cada tela, pela chave namespace:url_name
    screen_names: dict[str, str] = {}
    # Caminhos que não são telas: arquivos e ferramentas internas
    ignored_prefixes: tuple[str, ...] = ('/static/', '/media/', '/__debug__/')
    # Namespaces de rota que não são telas da aplicação
    ignored_namespaces: frozenset[str] = frozenset({'admin', 'djdt'})
    # Rotas chamadas automaticamente pela página (polling): não são atividade de ninguém
    ignored_features: frozenset[str] = frozenset()
    # Limite do campo feature no Atende Aqui
    max_feature_length = 100

    def __init__(self, **buffer_options):
        self.buffer = UsageBuffer(send=self.send, **buffer_options)
        # Telas sem nome já avisadas no log, para não repetir a cada acesso
        self._unnamed_screens: set[str] = set()

    # Regras da aplicação ------------------------------------------------

    def identify(self, user) -> tuple | None:
        raise NotImplementedError('Implemente identify(user) no tracker da aplicação.')

    def send(self, events: list[dict]) -> None:
        raise NotImplementedError('Implemente send(events) no tracker da aplicação.')

    def is_active(self) -> bool:
        return True

    # Registro --------------------------------------------------------------

    def track_page_view(self, request, response) -> dict | None:
        """Anota a tela acessada e devolve o evento, ou None se não for o caso."""
        if request.path.startswith(self.ignored_prefixes):
            return None
        if not self.is_screen_response(request, response):
            return None
        ids = self.identify_request(request)
        if not ids or not self.is_active():
            return None
        match = self.screen_match(request)
        if not match or len(match.view_name) > self.max_feature_length:
            return None
        company_platform_id, user_id = ids
        feature = match.view_name
        return self.buffer.add(
            type='page_view',
            company_platform_id=company_platform_id,
            user_id=user_id,
            feature=feature,
            feature_name=self.screen_name(feature),
            feature_path=self.screen_path(match),
        )

    def track_login(self, user) -> dict | None:
        """Anota o login e devolve o evento, ou None se o usuário não é contabilizado."""
        ids = self.identify(user)
        if not ids or not self.is_active():
            return None
        company_platform_id, user_id = ids
        return self.buffer.add(type='login', company_platform_id=company_platform_id, user_id=user_id)

    # Regras genéricas ----------------------------------------------------

    def identify_request(self, request) -> tuple | None:
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return None
        return self.identify(user)

    def is_screen_response(self, request, response) -> bool:
        """
        True se a resposta é uma tela acessada (ou atividade na tela, no HTMX).

        Requisição comum: só GET com resposta HTML e status 200. POST de
        formulário, redirect e JSON (notificações, autocomplete) ficam de fora.
        """
        if request.headers.get('HX-Request') == 'true':
            return response.status_code < 400
        return (
            request.method == 'GET'
            and response.status_code == 200
            and response.get('Content-Type', '').startswith('text/html')
        )

    def screen_match(self, request):
        """
        Rota da tela (ResolverMatch), ou None se não for uma tela.

        No HTMX, a tela é a página de origem (cabeçalho HX-Current-URL), e não
        o fragmento buscado: clicar numa aba conta na tela atual.
        """
        called = request.resolver_match
        if called and called.view_name in self.ignored_features:
            return None

        if request.headers.get('HX-Request') == 'true':
            path = self.page_path(request)
            if not path:
                return None
            try:
                match = resolve(path, urlconf=getattr(request, 'urlconf', None))
            except Resolver404:
                return None
        else:
            match = called
        if not match or not match.url_name:
            return None
        if match.namespaces and match.namespaces[0] in self.ignored_namespaces:
            return None
        return match

    def page_path(self, request) -> str | None:
        """Caminho da página de origem do HTMX, ou None se o cabeçalho não for confiável."""
        current = request.headers.get('HX-Current-URL') or ''
        if not current:
            return None
        # O cabeçalho vem do cliente: só vale se apontar para este mesmo host
        if not url_has_allowed_host_and_scheme(
            current, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
        ):
            return None
        return urlparse(current).path

    def screen_path(self, match) -> str:
        """
        Caminho da tela sem os ids: '/vagas/<job_id>/remuneracao/'.

        Vem do padrão da rota, e não do endereço acessado: é o mesmo em todo
        acesso e não expõe o id da vaga ou do candidato.
        """
        return '/' + re.sub(r'<\w+:(\w+)>', r'<\1>', match.route)

    def screen_name(self, feature: str) -> str:
        """
        Nome legível da tela: o de screen_names, ou um gerado a partir do
        url_name ('employers:job_list' → 'Job list').

        Tela sem nome cadastrado gera um aviso no log, uma única vez.
        """
        if feature in self.screen_names:
            return self.screen_names[feature]
        if feature not in self._unnamed_screens:
            self._unnamed_screens.add(feature)
            logger.warning('atendeaqui: tela sem nome cadastrado: %s', feature)
        url_name = feature.rsplit(':', 1)[-1]
        return url_name.replace('_', ' ').replace('-', ' ').capitalize()
