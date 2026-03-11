"""Testes para os modelos de dados (dataclasses)."""
from datetime import datetime

from atendeaqui.onboarding.models import (
    FlowStep,
    FlowStructure,
    UserProgress,
    WidgetToken,
    FlowAnalytics,
    _parse_datetime,
)


class TestParseDateTime:
    def test_none(self):
        assert _parse_datetime(None) is None

    def test_empty_string(self):
        assert _parse_datetime('') is None

    def test_iso_with_timezone(self):
        result = _parse_datetime('2026-01-15T10:00:00+00:00')
        assert isinstance(result, datetime)

    def test_iso_without_timezone(self):
        result = _parse_datetime('2026-01-15T10:00:00')
        assert isinstance(result, datetime)


class TestFlowStep:
    def test_from_dict(self):
        step = FlowStep.from_dict({
            'step_key': 'welcome',
            'title': 'Bem-vindo',
            'description': 'Desc',
            'order': 1,
            'is_required': True,
            'can_skip': False,
            'step_type': 'INFO',
        })
        assert step.step_key == 'welcome'
        assert step.is_required is True

    def test_from_dict_defaults(self):
        step = FlowStep.from_dict({})
        assert step.step_key == ''
        assert step.step_type == 'INFO'


class TestFlowStructure:
    def test_from_dict(self):
        flow = FlowStructure.from_dict({
            'name': 'Test',
            'description': '',
            'flow_type': 'LINEAR',
            'default_language': 'en-US',
            'available_languages': ['en-US'],
            'step_count': 1,
            'steps': [{'step_key': 's1', 'title': 'S1', 'description': '',
                        'order': 1, 'is_required': True, 'can_skip': False, 'step_type': 'INFO'}],
        })
        assert flow.name == 'Test'
        assert len(flow.steps) == 1


class TestUserProgress:
    def test_from_dict(self):
        progress = UserProgress.from_dict({
            'external_user_id': 'u1',
            'external_user_name': 'João',
            'status': 'IN_PROGRESS',
            'completion_percentage': 50,
            'steps_completed': ['s1'],
            'steps_skipped': [],
            'step_data': {'s1': {'k': 'v'}},
            'flow_name': 'F',
            'flow_slug': 'f-1',
            'started_at': '2026-01-15T10:00:00+00:00',
        })
        assert progress.is_in_progress
        assert progress.external_user_name == 'João'
        assert progress.step_data['s1']['k'] == 'v'
        assert progress.started_at is not None

    def test_status_properties(self):
        base = {'external_user_id': 'u', 'flow_name': '', 'completion_percentage': 0,
                'steps_completed': [], 'steps_skipped': [], 'step_data': {}}

        assert UserProgress.from_dict({**base, 'status': 'COMPLETED'}).is_completed
        assert UserProgress.from_dict({**base, 'status': 'ABANDONED'}).is_abandoned


class TestWidgetToken:
    def test_from_dict(self):
        token = WidgetToken.from_dict({'token': 'jwt', 'expires_in': 300})
        assert token.token == 'jwt'


class TestFlowAnalytics:
    def test_from_dict(self):
        analytics = FlowAnalytics.from_dict({
            'total_starts': 100, 'total_completions': 50,
            'completion_rate': 50.0, 'in_progress': 25, 'abandoned': 25,
            'average_completion_time': 180.0, 'step_drop_off': {},
        })
        assert analytics.total_starts == 100
