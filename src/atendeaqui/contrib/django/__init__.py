"""
Integração com Django: registra no Atende Aqui as telas acessadas e os logins.

Instalação: pip install "atendeaqui[django]". Passo a passo no README,
seção "Integrar uma aplicação Django".
"""
from .tracker import EngagementTracker, get_tracker

__all__ = ['EngagementTracker', 'get_tracker']
