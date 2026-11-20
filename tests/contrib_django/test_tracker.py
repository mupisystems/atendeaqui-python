"""Regras genéricas de tela e login do EngagementTracker."""
import logging
from types import SimpleNamespace

import pytest
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory
from django.urls import Resolver404, resolve


def person(**overrides):
    """Usuário que a aplicação fictícia contabiliza (tem empresa)."""
    data = {'pk': 77, 'is_authenticated': True, 'company_id': 1842}
    data.update(overrides)
    return SimpleNamespace(**data)


def visit(tracker, path='/vagas/', method='get', response=None, user=None, **headers):
    """Simula o acesso a `path` e devolve o evento anotado (ou None)."""
    request = getattr(RequestFactory(), method)(path, **headers)
    request.user = user or person()
    try:
        request.resolver_match = resolve(path)
    except Resolver404:
        request.resolver_match = None
    return tracker.track_page_view(request, response or HttpResponse('ok'))


class TestPageView:

    def test_screen_is_recorded(self, tracker):
        event = visit(tracker, '/vagas/')

        assert event['type'] == 'page_view'
        assert event['client_id'] == '1842'
        assert event['user_id'] == '77'
        assert event['feature'] == 'employers:job_list'
        assert event['feature_name'] == 'Processos'
        assert tracker.written() == [event]

    def test_event_has_only_contract_fields(self, tracker):
        # O Atende Aqui descarta campos fora do contrato (ex.: o caminho da rota)
        event = visit(tracker, '/vagas/123/remuneracao/')

        assert set(event) == {
            'type', 'client_id', 'user_id', 'feature', 'feature_name', 'event_id', 'occurred_at'}

    def test_screen_without_name_uses_the_generated_name(self, tracker):
        assert visit(tracker, '/')['feature_name'] == 'Dashboard'

    def test_screen_without_name_is_warned_once(self, tracker, caplog):
        with caplog.at_level(logging.WARNING, logger='atendeaqui.contrib.django.tracker'):
            visit(tracker, '/')
            visit(tracker, '/')

        assert caplog.text.count('employers:dashboard') == 1

    def test_anonymous_is_ignored(self, tracker):
        assert visit(tracker, user=SimpleNamespace(is_authenticated=False)) is None

    def test_user_the_app_does_not_count_is_ignored(self, tracker):
        assert visit(tracker, user=person(company_id=None)) is None

    def test_inactive_records_nothing(self, tracker):
        tracker.active = False

        assert visit(tracker) is None
        assert tracker.written() == []

    @pytest.mark.parametrize('path', ['/static/app.css', '/media/foto.png', '/__debug__/'])
    def test_files_and_tools_are_ignored(self, tracker, path):
        assert visit(tracker, path) is None

    def test_admin_is_not_a_screen(self, tracker):
        assert visit(tracker, '/admin/') is None

    def test_route_without_name_is_ignored(self, tracker):
        assert visit(tracker, '/sem-nome/') is None

    def test_error_page_is_not_a_screen(self, tracker):
        assert visit(tracker, response=HttpResponse(status=404)) is None

    def test_json_is_not_a_screen(self, tracker):
        assert visit(tracker, response=JsonResponse({})) is None

    def test_redirect_is_not_a_screen(self, tracker):
        assert visit(tracker, response=HttpResponse(status=302)) is None

    def test_form_post_is_not_a_screen(self, tracker):
        assert visit(tracker, method='post') is None


class TestHtmx:

    def htmx(self, tracker, path, current_url, response=None):
        return visit(tracker, path, method='post', response=response,
                     HTTP_HX_REQUEST='true', HTTP_HX_CURRENT_URL=current_url)

    def test_counts_on_the_current_page(self, tracker):
        event = self.htmx(tracker, '/sem-nome/', 'http://testserver/vagas/')

        assert event['feature'] == 'employers:job_list'

    def test_uses_the_path_of_the_current_page(self, tracker):
        event = self.htmx(tracker, '/sem-nome/', 'http://testserver/vagas/123/remuneracao/')

        assert event['feature'] == 'employers:job_salary'

    def test_boosted_link_counts_on_the_destination_page(self, tracker):
        """hx-boost é navegação: HX-Current-URL é a página que o usuário está deixando."""
        event = visit(tracker, '/vagas/123/remuneracao/', HTTP_HX_REQUEST='true',
                      HTTP_HX_BOOSTED='true', HTTP_HX_CURRENT_URL='http://testserver/vagas/')

        assert event['feature'] == 'employers:job_salary'

    def test_app_under_a_sub_path(self, tracker):
        """Com SCRIPT_NAME, a URL do navegador tem o prefixo, que o resolve() não conhece."""
        event = visit(tracker, '/sem-nome/', method='post', SCRIPT_NAME='/app',
                      HTTP_HX_REQUEST='true', HTTP_HX_CURRENT_URL='http://testserver/app/vagas/')

        assert event['feature'] == 'employers:job_list'

    def test_current_url_with_encoded_characters(self, tracker):
        """O navegador manda a URL codificada (%C3%A7), a rota está em texto."""
        event = self.htmx(tracker, '/sem-nome/', 'http://testserver/vagas/1/promo%C3%A7%C3%A3o/')

        assert event['feature'] == 'employers:job_promotion'

    def test_current_url_from_another_site_is_ignored(self, tracker):
        assert self.htmx(tracker, '/sem-nome/', 'http://outro-site.com/vagas/') is None

    def test_polling_is_ignored(self, tracker):
        assert self.htmx(tracker, '/vagas/1/score/', 'http://testserver/vagas/') is None

    def test_error_is_not_activity(self, tracker):
        response = HttpResponse(status=400)

        assert self.htmx(tracker, '/sem-nome/', 'http://testserver/vagas/', response) is None


class TestLogin:

    def test_login_is_recorded(self, tracker):
        event = tracker.track_login(person())

        assert event['type'] == 'login'
        assert event['client_id'] == '1842'
        assert event['user_id'] == '77'
        assert 'feature' not in event

    def test_user_the_app_does_not_count_is_ignored(self, tracker):
        assert tracker.track_login(person(company_id=None)) is None

    def test_name_and_email_from_identify_go_in_the_event(self, tracker):
        event = tracker.track_login(person(full_name='Ana Souza', email='ana@casulo.com.br'))

        assert (event['user_name'], event['user_email']) == ('Ana Souza', 'ana@casulo.com.br')

    def test_missing_name_or_email_are_left_out(self, tracker):
        event = tracker.track_login(person(full_name='', email=None))

        assert 'user_name' not in event
        assert 'user_email' not in event

    def test_inactive_records_nothing(self, tracker):
        tracker.active = False

        assert tracker.track_login(person()) is None
