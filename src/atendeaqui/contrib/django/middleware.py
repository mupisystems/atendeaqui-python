"""Middleware que registra no Atende Aqui as telas acessadas."""
import logging

from .tracker import _current_request, get_tracker

logger = logging.getLogger(__name__)


class EngagementMiddleware:
    """
    Anota cada tela acessada no tracker da aplicação e guarda a requisição em
    andamento, para as atividades registradas durante ela (track_activity).

    Só anota no UsageBuffer: o envio é em lote, fora da requisição. Deve vir
    depois do AuthenticationMiddleware, que preenche request.user.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Lido na inicialização: configuração errada falha ao subir a aplicação
        self.tracker = get_tracker()

    def __call__(self, request):
        # Guarda a requisição para track_activity saber quem fez a atividade
        token = _current_request.set(request)
        try:
            response = self.get_response(request)
        finally:
            _current_request.reset(token)
        # Erro no registro não pode virar erro na tela de quem está usando
        try:
            self.tracker.track_page_view(request, response)
        except Exception:
            logger.exception('atendeaqui: falha ao registrar a tela acessada')
        return response
