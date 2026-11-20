"""App Django da integração: liga o registro de login."""
import logging

from django.apps import AppConfig
from django.contrib.auth.signals import user_logged_in

logger = logging.getLogger(__name__)


def track_login(sender, request, user, **kwargs):
    """Anota o login no tracker da aplicação. Erro aqui não pode impedir o login."""
    from .tracker import get_tracker

    try:
        get_tracker().track_login(user)
    except Exception:
        logger.exception('atendeaqui: falha ao registrar o login do usuário %s', getattr(user, 'pk', None))


class AtendeAquiEngagementConfig(AppConfig):
    name = 'atendeaqui.contrib.django'
    label = 'atendeaqui_engagement'
    verbose_name = 'Atende Aqui: engajamento'

    def ready(self):
        user_logged_in.connect(track_login, dispatch_uid='atendeaqui_engagement_login')
