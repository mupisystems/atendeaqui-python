"""Middleware que registra no Atende Aqui as telas acessadas."""
import logging

from .tracker import get_tracker

logger = logging.getLogger(__name__)


class EngagementMiddleware:
    """
    Anota cada tela acessada no tracker da aplicação.

    Só anota no UsageBuffer: o envio é em lote, fora da requisição. Deve vir
    depois do AuthenticationMiddleware, que preenche request.user.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Lido na inicialização: configuração errada falha ao subir a aplicação
        self.tracker = get_tracker()

    def __call__(self, request):
        response = self.get_response(request)
        # Erro no registro não pode virar erro na tela de quem está usando
        try:
            self.tracker.track_page_view(request, response)
        except Exception:
            logger.exception('atendeaqui: falha ao registrar a tela acessada')
        return response
