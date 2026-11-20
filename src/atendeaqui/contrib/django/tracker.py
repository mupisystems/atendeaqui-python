"""
Regras de engajamento que valem para qualquer aplicação Django.

A aplicação estende EngagementTracker com as regras dela (quem é contabilizado,
se o engajamento está ativo, para onde vão os lotes) e indica a instância em
settings.ATENDEAQUI_ENGAGEMENT_TRACKER.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import Resolver404, resolve
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.module_loading import import_string

from ...engagement.buffer import UsageBuffer

logger = logging.getLogger(__name__)

# Requisição em andamento, guardada pelo EngagementMiddleware: é dela que
# track_activity tira quem fez a atividade quando o código (ex.: o save de um
# model) não tem o usuário em mãos.
_current_request: ContextVar = ContextVar('atendeaqui_current_request', default=None)


def current_user():
    """Usuário autenticado da requisição em andamento, ou None (fora de requisição ou anônimo)."""
    request = _current_request.get()
    user = getattr(request, 'user', None)
    return user if user is not None and user.is_authenticated else None


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
        identify(user): (client_id, user_id) ou (client_id, user_id, nome,
            e-mail) de quem é contabilizado, ou None. Nome e e-mail são o que
            o Atende Aqui mostra da pessoa: mande sempre que tiver.
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
        feature = match.view_name
        return self.buffer.add(
            type='page_view',
            **self.identity_fields(ids),
            feature=feature,
            feature_name=self.screen_name(feature),
        )

    def track_login(self, user) -> dict | None:
        """Anota o login e devolve o evento, ou None se o usuário não é contabilizado."""
        ids = self.identify(user)
        if not ids or not self.is_active():
            return None
        return self.buffer.add(type='login', **self.identity_fields(ids))

    def track_activity(self, activity: str, activity_name: str, user=None) -> dict | None:
        """
        Anota uma atividade (algo de valor que a pessoa fez, ex.: vaga criada).

        Sem `user`, usa o usuário da requisição em andamento (o middleware
        guarda a requisição), o que permite chamar de onde o usuário não
        chega, como o save de um model. Fora de requisição e sem `user`, não
        anota nada. `activity` é a chave estável (`^[a-z0-9_.:-]+$`) e
        `activity_name`, o nome exibido.
        """
        user = user or current_user()
        if user is None:
            return None
        ids = self.identify(user)
        if not ids or not self.is_active():
            return None
        return self.buffer.add(
            type='activity', **self.identity_fields(ids), activity=activity, activity_name=activity_name)

    # Regras genéricas ----------------------------------------------------

    @staticmethod
    def identity_fields(ids) -> dict:
        """Campos do evento a partir do identify: client_id, user_id e, se vierem, nome e e-mail."""
        client_id, user_id, *identity = ids
        fields = {'client_id': client_id, 'user_id': user_id}
        for key, value in zip(('user_name', 'user_email'), identity):
            if value:
                fields[key] = value
        return fields

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
        if self.is_htmx_fragment(request):
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

        if self.is_htmx_fragment(request):
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

    def is_htmx_fragment(self, request) -> bool:
        """
        True se é um fragmento HTMX (aba, filtro...), que conta na página de origem.

        Link ou formulário com hx-boost é navegação: conta como requisição comum,
        na página de destino (HX-Current-URL ainda é a página que ficou para trás).
        """
        return request.headers.get('HX-Request') == 'true' and request.headers.get('HX-Boosted') != 'true'

    def page_path(self, request) -> str | None:
        """
        Caminho da página de origem do HTMX, no formato do resolve(), ou None
        se o cabeçalho não for confiável ou a página for de fora da aplicação.
        """
        current = request.headers.get('HX-Current-URL') or ''
        if not current:
            return None
        # O cabeçalho vem do cliente: só vale se apontar para este mesmo host
        if not url_has_allowed_host_and_scheme(
            current, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
        ):
            return None
        # O navegador manda a URL codificada (%C3%A7) e com o prefixo da aplicação
        # (SCRIPT_NAME); o resolve() espera o texto e só o caminho de dentro (path_info)
        path = unquote(urlparse(current).path)
        script_prefix = request.path[:len(request.path) - len(request.path_info)]
        if not script_prefix:
            return path
        if path != script_prefix and not path.startswith(script_prefix + '/'):
            return None
        return path[len(script_prefix):] or '/'

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
