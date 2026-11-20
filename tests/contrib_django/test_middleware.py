"""Middleware, registro de login e configuração da integração Django."""
import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth.signals import user_logged_in
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.urls import resolve

from atendeaqui.contrib.django import get_tracker
from atendeaqui.contrib.django.middleware import EngagementMiddleware


def person(**overrides):
    data = {'pk': 77, 'is_authenticated': True, 'company_id': 1842}
    data.update(overrides)
    return SimpleNamespace(**data)


def visit(path='/vagas/'):
    """Passa uma requisição pelo middleware, como o Django faria."""
    request = RequestFactory().get(path)
    request.user = person()

    def view(req):
        req.resolver_match = resolve(path)
        return HttpResponse('ok')

    return EngagementMiddleware(view)(request)


class TestMiddleware:

    def test_screen_is_recorded(self, tracker):
        visit('/vagas/')

        [event] = tracker.written()
        assert event['feature'] == 'employers:job_list'

    def test_failure_does_not_break_the_page(self, tracker, caplog):
        with patch.object(tracker, 'track_page_view', side_effect=RuntimeError('bug')), \
                caplog.at_level(logging.ERROR, logger='atendeaqui.contrib.django.middleware'):
            response = visit('/vagas/')

        assert response.status_code == 200
        assert 'falha ao registrar a tela' in caplog.text


class TestLoginSignal:

    def login(self, user):
        # O django.contrib.auth também ouve o sinal e salva o last_login
        user.save = lambda **kwargs: None
        user_logged_in.send(sender=type(user), request=None, user=user)

    def test_login_is_recorded(self, tracker):
        self.login(person())

        [event] = tracker.written()
        assert event['type'] == 'login'

    def test_failure_does_not_break_the_login(self, tracker, caplog):
        with patch.object(tracker, 'track_login', side_effect=RuntimeError('bug')), \
                caplog.at_level(logging.ERROR, logger='atendeaqui.contrib.django.apps'):
            self.login(person())  # não levanta

        assert 'falha ao registrar o login' in caplog.text


class TestConfiguration:

    def test_tracker_comes_from_the_settings(self, tracker):
        assert get_tracker() is tracker

    def test_missing_setting_is_reported(self):
        with override_settings(ATENDEAQUI_ENGAGEMENT_TRACKER=None):
            with pytest.raises(ImproperlyConfigured):
                get_tracker()


class TestActivity:
    """track_activity: a atividade sai com o usuário da requisição em andamento."""

    def test_activity_inside_the_request_uses_its_user(self, tracker):
        request = RequestFactory().post('/vagas/')
        request.user = person(full_name='Ana Souza', email='ana@casulo.com.br')

        def view(req):
            # Como o save de um model: o código não tem o usuário em mãos
            tracker.track_activity('vaga_criada', 'Vaga criada')
            return HttpResponse('ok')

        EngagementMiddleware(view)(request)

        [event] = [event for event in tracker.written() if event['type'] == 'activity']
        assert event['activity'] == 'vaga_criada'
        assert event['activity_name'] == 'Vaga criada'
        assert event['client_id'] == '1842'
        assert event['user_id'] == '77'
        assert event['user_name'] == 'Ana Souza'

    def test_outside_a_request_without_user_nothing_is_recorded(self, tracker):
        assert tracker.track_activity('vaga_criada', 'Vaga criada') is None
        assert tracker.written() == []

    def test_explicit_user_works_outside_a_request(self, tracker):
        event = tracker.track_activity('vaga_criada', 'Vaga criada', user=person())

        assert event['type'] == 'activity'

    def test_user_the_app_does_not_count_records_nothing(self, tracker):
        assert tracker.track_activity('vaga_criada', 'Vaga criada', user=person(company_id=None)) is None

    def test_the_request_is_forgotten_after_the_response(self, tracker):
        visit('/vagas/')

        assert tracker.track_activity('vaga_criada', 'Vaga criada') is None
