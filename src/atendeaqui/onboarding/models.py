"""
Modelos de dados (dataclasses) para respostas da API de Onboarding.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime string para datetime object."""
    if not value:
        return None
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


@dataclass
class FlowStep:
    """Representa um step individual de um flow de onboarding."""
    step_key: str
    title: str
    description: str
    order: int
    is_required: bool
    can_skip: bool
    step_type: str
    step_config: dict = field(default_factory=dict)
    content: str = ''
    content_html: str = ''

    @classmethod
    def from_dict(cls, data: dict) -> FlowStep:
        return cls(
            step_key=data.get('step_key', ''),
            title=data.get('title', ''),
            description=data.get('description', ''),
            order=data.get('order', 0),
            is_required=data.get('is_required', False),
            can_skip=data.get('can_skip', False),
            step_type=data.get('step_type', 'INFO'),
            step_config=data.get('step_config') or {},
            content=data.get('content', ''),
            content_html=data.get('content_html', ''),
        )


@dataclass
class FlowStructure:
    """Estrutura completa de um flow de onboarding."""
    name: str
    description: str
    flow_type: str
    default_language: str
    available_languages: list[str]
    step_count: int
    steps: list[FlowStep]
    flow_config: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> FlowStructure:
        steps_data = data.get('steps', [])
        return cls(
            name=data.get('name', ''),
            description=data.get('description', ''),
            flow_type=data.get('flow_type', 'LINEAR'),
            default_language=data.get('default_language', 'pt-BR'),
            available_languages=data.get('available_languages', []),
            step_count=data.get('step_count', 0),
            steps=[FlowStep.from_dict(s) for s in steps_data],
            flow_config=data.get('flow_config') or {},
        )


@dataclass
class UserProgress:
    """Progresso de um usuário em um flow de onboarding."""
    external_user_id: str
    external_user_name: str | None
    external_user_email: str | None
    flow_name: str
    flow_slug: str | None
    status: str
    current_step_key: str | None
    current_step_title: str | None
    completion_percentage: int
    steps_completed: list[str]
    steps_skipped: list[str]
    step_data: dict
    client_id: str | None
    started_at: datetime | None
    completed_at: datetime | None
    last_activity_at: datetime | None

    @classmethod
    def from_dict(cls, data: dict) -> UserProgress:
        return cls(
            external_user_id=data.get('external_user_id', ''),
            external_user_name=data.get('external_user_name'),
            external_user_email=data.get('external_user_email'),
            flow_name=data.get('flow_name', ''),
            flow_slug=data.get('flow_slug'),
            status=data.get('status', 'NOT_STARTED'),
            current_step_key=data.get('current_step_key'),
            current_step_title=data.get('current_step_title'),
            completion_percentage=data.get('completion_percentage', 0),
            steps_completed=data.get('steps_completed', []),
            steps_skipped=data.get('steps_skipped', []),
            step_data=data.get('step_data') or {},
            client_id=data.get('client_id'),
            started_at=_parse_datetime(data.get('started_at')),
            completed_at=_parse_datetime(data.get('completed_at')),
            last_activity_at=_parse_datetime(data.get('last_activity_at')),
        )

    @property
    def is_completed(self) -> bool:
        return self.status == 'COMPLETED'

    @property
    def is_in_progress(self) -> bool:
        return self.status == 'IN_PROGRESS'

    @property
    def is_abandoned(self) -> bool:
        return self.status == 'ABANDONED'


@dataclass
class WidgetToken:
    """Token JWT para uso em widgets frontend."""
    token: str
    expires_in: int

    @classmethod
    def from_dict(cls, data: dict) -> WidgetToken:
        return cls(
            token=data.get('token', ''),
            expires_in=data.get('expires_in', 0),
        )


@dataclass
class FlowAnalytics:
    """Métricas e analytics de um flow."""
    total_starts: int
    total_completions: int
    completion_rate: float
    in_progress: int
    abandoned: int
    average_completion_time: float | None
    step_drop_off: dict

    @classmethod
    def from_dict(cls, data: dict) -> FlowAnalytics:
        return cls(
            total_starts=data.get('total_starts', 0),
            total_completions=data.get('total_completions', 0),
            completion_rate=data.get('completion_rate', 0.0),
            in_progress=data.get('in_progress', 0),
            abandoned=data.get('abandoned', 0),
            average_completion_time=data.get('average_completion_time'),
            step_drop_off=data.get('step_drop_off') or {},
        )
