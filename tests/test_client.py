"""Testes para AtendeAquiClient e módulo de onboarding."""
import json

import pytest
import responses

from atendeaqui import (
    AtendeAquiClient,
    FlowStructure,
    UserProgress,
    WidgetToken,
    FlowAnalytics,
    NotFoundError,
    ValidationError,
    StepNotFoundError,
    AuthenticationError,
    ServerError,
)
from atendeaqui.client import PRODUCTION_URL, SANDBOX_URL

BASE_URL = 'https://test.atendeaqui.com.br'
FLOW_KEY = 'f47ac10b-58cc-4372-a567-0e02b2c3d479'
FLOW_KEY_2 = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'


# =========================================================================
# Dados de exemplo
# =========================================================================

FLOW_STRUCTURE_DATA = {
    'name': 'Onboarding Teste',
    'description': 'Flow de teste',
    'flow_type': 'LINEAR',
    'default_language': 'pt-BR',
    'available_languages': ['pt-BR', 'en-US'],
    'step_count': 2,
    'flow_config': {'redirect_url': '/dashboard'},
    'steps': [
        {
            'step_key': 'welcome',
            'title': 'Bem-vindo',
            'description': 'Primeiro passo',
            'order': 1,
            'is_required': True,
            'can_skip': False,
            'step_type': 'INFO',
            'step_config': {},
            'content': '# Bem-vindo',
            'content_html': '<h1>Bem-vindo</h1>',
        },
        {
            'step_key': 'config',
            'title': 'Configuração',
            'description': 'Configure',
            'order': 2,
            'is_required': True,
            'can_skip': False,
            'step_type': 'FORM',
            'step_config': {'fields': []},
            'content': '',
            'content_html': '',
        },
    ],
}

PROGRESS_DATA = {
    'external_user_id': 'user-123',
    'external_user_name': 'João Teste',
    'external_user_email': 'user@test.com',
    'flow_name': 'Onboarding Teste',
    'flow_slug': 'onboarding-teste',
    'status': 'IN_PROGRESS',
    'current_step_key': 'welcome',
    'current_step_title': 'Bem-vindo',
    'completion_percentage': 0,
    'steps_completed': [],
    'steps_skipped': [],
    'step_data': {},
    'client_id': None,
    'started_at': '2026-01-15T10:00:00Z',
    'completed_at': None,
    'last_activity_at': '2026-01-15T10:00:00Z',
}


# =========================================================================
# Inicialização
# =========================================================================

class TestClientInit:
    def test_with_flow_key(self):
        client = AtendeAquiClient(flow_key=FLOW_KEY, _base_url=f'{BASE_URL}/api')
        assert client.onboarding._default_flow_key == FLOW_KEY

    def test_with_api_token_and_flow_key(self):
        client = AtendeAquiClient(api_token='token', flow_key=FLOW_KEY, _base_url=f'{BASE_URL}/api')
        assert client.onboarding._default_flow_key == FLOW_KEY

    def test_with_api_token_only(self):
        client = AtendeAquiClient(api_token='token', _base_url=f'{BASE_URL}/api')
        assert client.onboarding._default_flow_key is None

    def test_no_credentials_raises(self):
        with pytest.raises(ValueError, match='api_token.*flow_key'):
            AtendeAquiClient()

    def test_default_production_url(self):
        client = AtendeAquiClient(flow_key=FLOW_KEY)
        assert client._http._base_url == PRODUCTION_URL

    def test_sandbox_url(self):
        client = AtendeAquiClient(flow_key=FLOW_KEY, sandbox=True)
        assert client._http._base_url == SANDBOX_URL

    def test_base_url_override_takes_precedence(self):
        client = AtendeAquiClient(flow_key=FLOW_KEY, sandbox=True, _base_url='https://custom.test/api')
        assert client._http._base_url == 'https://custom.test/api'

    def test_module_accessible(self):
        client = AtendeAquiClient(flow_key=FLOW_KEY, _base_url=f'{BASE_URL}/api')
        assert hasattr(client, 'onboarding')
        assert hasattr(client, 'clients')

    @responses.activate
    def test_flow_key_sends_header_per_request(self):
        """flow_key é enviado como header per-request, não na sessão."""
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/structure/',
            json=FLOW_STRUCTURE_DATA,
            status=200,
        )

        client = AtendeAquiClient(flow_key=FLOW_KEY, _base_url=f'{BASE_URL}/api')
        client.onboarding.get_structure()

        assert responses.calls[0].request.headers['X-Onboarding-Key'] == FLOW_KEY

    @responses.activate
    def test_api_token_sends_bearer_header(self):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/flows/',
            json={'results': []},
            status=200,
        )

        client = AtendeAquiClient(api_token='my-token', _base_url=f'{BASE_URL}/api')
        client.onboarding.list_flows()

        assert responses.calls[0].request.headers['Authorization'] == 'Bearer my-token'

    @responses.activate
    def test_both_headers_sent(self):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/structure/',
            json=FLOW_STRUCTURE_DATA,
            status=200,
        )

        client = AtendeAquiClient(api_token='my-token', flow_key=FLOW_KEY, _base_url=f'{BASE_URL}/api')
        client.onboarding.get_structure()

        assert responses.calls[0].request.headers['X-Onboarding-Key'] == FLOW_KEY
        assert responses.calls[0].request.headers['Authorization'] == 'Bearer my-token'


# =========================================================================
# Onboarding - flow_key override por método
# =========================================================================

class TestFlowKeyOverride:
    @responses.activate
    def test_method_flow_key_overrides_default(self, client):
        """flow_key passado no método sobrescreve o default do client."""
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY_2}/structure/',
            json=FLOW_STRUCTURE_DATA,
            status=200,
        )

        client.onboarding.get_structure(flow_key=FLOW_KEY_2)

        assert responses.calls[0].request.headers['X-Onboarding-Key'] == FLOW_KEY_2

    @responses.activate
    def test_admin_client_can_use_any_flow(self, admin_only_client):
        """Cliente sem default_flow_key pode operar passando flow_key por método."""
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/start/',
            json=PROGRESS_DATA,
            status=201,
        )

        progress = admin_only_client.onboarding.start_flow(
            user_id='user-123',
            flow_key=FLOW_KEY,
        )
        assert isinstance(progress, UserProgress)


# =========================================================================
# Onboarding - API Pública
# =========================================================================

class TestOnboardingGetStructure:
    @responses.activate
    def test_get_structure(self, client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/structure/',
            json=FLOW_STRUCTURE_DATA,
            status=200,
        )

        flow = client.onboarding.get_structure()

        assert isinstance(flow, FlowStructure)
        assert flow.name == 'Onboarding Teste'
        assert flow.step_count == 2
        assert len(flow.steps) == 2
        assert flow.steps[0].step_key == 'welcome'

    @responses.activate
    def test_get_structure_with_language(self, client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/structure/',
            json=FLOW_STRUCTURE_DATA,
            status=200,
        )

        client.onboarding.get_structure(language='en-US')
        assert 'language=en-US' in responses.calls[0].request.url

    @responses.activate
    def test_get_structure_not_found(self, client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/structure/',
            json={'error': {'code': 'FLOW_NOT_FOUND', 'message': 'Flow não encontrado'}},
            status=404,
        )

        with pytest.raises(NotFoundError) as exc_info:
            client.onboarding.get_structure()
        assert exc_info.value.code == 'FLOW_NOT_FOUND'


class TestOnboardingRequiresFlowKey:
    def test_get_structure_without_flow_key(self, admin_only_client):
        with pytest.raises(ValueError, match='flow_key'):
            admin_only_client.onboarding.get_structure()

    def test_start_flow_without_flow_key(self, admin_only_client):
        with pytest.raises(ValueError, match='flow_key'):
            admin_only_client.onboarding.start_flow(user_id='user-123')

    def test_get_progress_without_flow_key(self, admin_only_client):
        with pytest.raises(ValueError, match='flow_key'):
            admin_only_client.onboarding.get_progress(user_id='user-123')


class TestOnboardingStartFlow:
    @responses.activate
    def test_start_flow(self, client):
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/start/',
            json=PROGRESS_DATA,
            status=201,
        )

        progress = client.onboarding.start_flow(
            user_id='user-123',
            name='João Teste',
            email='user@test.com',
            metadata={'company': 'Acme'},
        )

        assert isinstance(progress, UserProgress)
        assert progress.external_user_id == 'user-123'
        assert progress.external_user_name == 'João Teste'
        assert progress.status == 'IN_PROGRESS'

        body = json.loads(responses.calls[0].request.body)
        assert body['external_user_id'] == 'user-123'
        assert body['name'] == 'João Teste'
        assert body['metadata'] == {'company': 'Acme'}

    @responses.activate
    def test_start_flow_existing_user(self, client):
        data = {**PROGRESS_DATA, 'steps_completed': ['welcome'], 'completion_percentage': 50}
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/start/',
            json=data,
            status=200,
        )

        progress = client.onboarding.start_flow(user_id='user-123')
        assert progress.completion_percentage == 50


class TestOnboardingGetProgress:
    @responses.activate
    def test_get_progress(self, client):
        data = {
            **PROGRESS_DATA,
            'steps_completed': ['welcome'],
            'step_data': {'welcome': {'accepted': True}},
            'completion_percentage': 50,
        }
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/progress/user-123/',
            json=data,
            status=200,
        )

        progress = client.onboarding.get_progress(user_id='user-123')

        assert progress.completion_percentage == 50
        assert 'welcome' in progress.steps_completed
        assert progress.step_data['welcome']['accepted'] is True
        assert progress.flow_slug == 'onboarding-teste'

    @responses.activate
    def test_get_progress_not_found(self, client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/progress/unknown/',
            json={'error': {'code': 'PROGRESS_NOT_FOUND', 'message': 'Não encontrado'}},
            status=404,
        )

        with pytest.raises(NotFoundError):
            client.onboarding.get_progress(user_id='unknown')


class TestOnboardingCompleteStep:
    @responses.activate
    def test_complete_step(self, client):
        data = {
            **PROGRESS_DATA,
            'steps_completed': ['welcome'],
            'current_step_key': 'config',
            'step_data': {'welcome': {'tempo': 30}},
            'completion_percentage': 50,
        }
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/progress/user-123/complete-step/',
            json=data,
            status=200,
        )

        progress = client.onboarding.complete_step(
            user_id='user-123',
            step_key='welcome',
            step_data={'tempo': 30},
        )

        assert 'welcome' in progress.steps_completed

    @responses.activate
    def test_complete_step_not_found(self, client):
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/progress/user-123/complete-step/',
            json={'error': {'code': 'STEP_NOT_FOUND', 'message': 'Step não existe'}},
            status=400,
        )

        with pytest.raises(StepNotFoundError):
            client.onboarding.complete_step(user_id='user-123', step_key='invalid')


class TestOnboardingBatchComplete:
    @responses.activate
    def test_complete_steps_batch(self, client):
        data = {
            **PROGRESS_DATA,
            'steps_completed': ['welcome', 'config'],
            'status': 'COMPLETED',
            'completion_percentage': 100,
        }
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/progress/user-123/complete-steps/',
            json=data,
            status=200,
        )

        progress = client.onboarding.complete_steps(
            user_id='user-123',
            steps=[{'step_key': 'welcome'}, {'step_key': 'config'}],
        )

        assert progress.is_completed
        assert len(progress.steps_completed) == 2


class TestOnboardingSkipStep:
    @responses.activate
    def test_skip_step(self, client):
        data = {**PROGRESS_DATA, 'steps_skipped': ['optional']}
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/progress/user-123/skip-step/',
            json=data,
            status=200,
        )

        progress = client.onboarding.skip_step(user_id='user-123', step_key='optional')
        assert 'optional' in progress.steps_skipped


class TestOnboardingFlowActions:
    @responses.activate
    def test_complete_flow(self, client):
        data = {**PROGRESS_DATA, 'status': 'COMPLETED', 'completed_at': '2026-01-15T10:30:00Z'}
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/progress/user-123/complete/',
            json=data,
            status=200,
        )

        progress = client.onboarding.complete_flow(user_id='user-123')
        assert progress.is_completed

    @responses.activate
    def test_restart_flow(self, client):
        data = {**PROGRESS_DATA, 'status': 'IN_PROGRESS', 'steps_completed': []}
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/progress/user-123/restart/',
            json=data,
            status=200,
        )

        progress = client.onboarding.restart_flow(user_id='user-123')
        assert progress.is_in_progress

    @responses.activate
    def test_abandon_flow(self, client):
        data = {**PROGRESS_DATA, 'status': 'ABANDONED'}
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/progress/user-123/abandon/',
            json=data,
            status=200,
        )

        progress = client.onboarding.abandon_flow(user_id='user-123')
        assert progress.is_abandoned


class TestOnboardingUpdateMetadata:
    @responses.activate
    def test_update_metadata(self, client):
        responses.add(
            responses.PATCH,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/progress/user-123/metadata/',
            json=PROGRESS_DATA,
            status=200,
        )

        progress = client.onboarding.update_metadata(
            user_id='user-123',
            metadata={'company': 'Acme'},
        )

        assert isinstance(progress, UserProgress)
        body = json.loads(responses.calls[0].request.body)
        assert body['metadata'] == {'company': 'Acme'}


class TestOnboardingWidgetToken:
    @responses.activate
    def test_get_widget_token(self, client):
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/onboarding/auth/token/',
            json={'token': 'jwt-abc', 'expires_in': 600},
            status=200,
        )

        token = client.onboarding.get_widget_token(user_id='user-123')

        assert isinstance(token, WidgetToken)
        assert token.token == 'jwt-abc'
        assert token.expires_in == 600


# =========================================================================
# Onboarding - API Admin
# =========================================================================

class TestOnboardingAdmin:
    @responses.activate
    def test_list_flows(self, admin_client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/flows/',
            json={'results': [{'slug': 'flow-1'}, {'slug': 'flow-2'}]},
            status=200,
        )

        flows = admin_client.onboarding.list_flows()
        assert len(flows) == 2

    @responses.activate
    def test_list_flows_admin_only(self, admin_only_client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/flows/',
            json={'results': [{'slug': 'flow-1'}]},
            status=200,
        )

        flows = admin_only_client.onboarding.list_flows()
        assert len(flows) == 1

    @responses.activate
    def test_get_analytics(self, admin_client):
        data = {
            'total_starts': 100,
            'total_completions': 75,
            'completion_rate': 75.0,
            'in_progress': 10,
            'abandoned': 15,
            'average_completion_time': 120.5,
            'step_drop_off': {},
        }
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/flows/flow-teste/analytics/',
            json=data,
            status=200,
        )

        analytics = admin_client.onboarding.get_analytics(slug='flow-teste')

        assert isinstance(analytics, FlowAnalytics)
        assert analytics.total_starts == 100

    @responses.activate
    def test_admin_auth_header(self, admin_client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/flows/',
            json={'results': []},
            status=200,
        )

        admin_client.onboarding.list_flows()

        assert 'Bearer test-bearer-token-123' in responses.calls[0].request.headers['Authorization']


# =========================================================================
# Erros
# =========================================================================

class TestErrorHandling:
    @responses.activate
    def test_server_error(self, client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/structure/',
            json={'error': {'code': 'SERVER_ERROR', 'message': 'Internal error'}},
            status=500,
        )

        with pytest.raises(ServerError):
            client.onboarding.get_structure()

    @responses.activate
    def test_auth_error(self, client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/structure/',
            json={'error': {'code': 'AUTH_REQUIRED', 'message': 'Auth necessária'}},
            status=401,
        )

        with pytest.raises(AuthenticationError):
            client.onboarding.get_structure()

    @responses.activate
    def test_legacy_error_format(self, client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/onboarding/{FLOW_KEY}/progress/unknown/',
            json={'detail': 'Not found.'},
            status=404,
        )

        with pytest.raises(NotFoundError) as exc_info:
            client.onboarding.get_progress(user_id='unknown')
        assert 'Not found' in exc_info.value.message
