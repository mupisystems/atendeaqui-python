"""
SDK Python para a plataforma AtendeAqui.

Uso:

    from atendeaqui import AtendeAquiClient

    client = AtendeAquiClient(flow_key="uuid-do-flow")

    # Onboarding
    flow = client.onboarding.get_structure()
    progress = client.onboarding.start_flow(user_id="user-123")
    progress = client.onboarding.complete_step(user_id="user-123", step_key="welcome")
"""
from .client import AtendeAquiClient
from .exceptions import (
    AtendeAquiError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    StepNotFoundError,
    StepNotSkippableError,
    OriginNotAllowedError,
    RateLimitError,
    ServerError,
)
from .clients.models import Client, TeamMember
from .onboarding.models import (
    FlowStructure,
    FlowStep,
    UserProgress,
    WidgetToken,
    FlowAnalytics,
)
from ._version import __version__

__all__ = [
    'AtendeAquiClient',
    # Exceções
    'AtendeAquiError',
    'AuthenticationError',
    'NotFoundError',
    'ValidationError',
    'StepNotFoundError',
    'StepNotSkippableError',
    'OriginNotAllowedError',
    'RateLimitError',
    'ServerError',
    # Models - Clients
    'Client',
    'TeamMember',
    # Models - Onboarding
    'FlowStructure',
    'FlowStep',
    'UserProgress',
    'WidgetToken',
    'FlowAnalytics',
    # Version
    '__version__',
]
