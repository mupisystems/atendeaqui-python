"""Testes para o módulo de clientes."""
import json

import pytest
import responses

from atendeaqui import AtendeAquiClient, Client, TeamMember, NotFoundError

BASE_URL = 'https://test.atendeaqui.com.br'

CLIENT_DATA = {
    'client_id': 'abc-123-uuid',
    'full_name': 'Acme Corp',
    'email': 'contato@acme.com',
    'phone': '1133334444',
    'identification_number': '12.345.678/0001-90',
    'type_identification': 'CNPJ',
    'birthday': None,
    'observations': '',
    'is_active': True,
    'preferred_language': 'pt-BR',
    'profession': '',
    'created_at': '2026-01-15T10:00:00Z',
    'updated_at': '2026-01-15T10:00:00Z',
    'team_members': [
        {
            'id': 1,
            'username': 'joao',
            'email': 'joao@acme.com',
            'full_name': 'João Silva',
            'is_primary': True,
            'can_create_tickets': True,
            'can_view_all_tickets': True,
            'can_edit_client': True,
            'is_active': True,
        },
    ],
    'team_count': 1,
}

TEAM_MEMBER_DATA = {
    'id': 2,
    'username': 'maria',
    'email': 'maria@acme.com',
    'full_name': 'Maria Santos',
    'is_primary': False,
    'can_create_tickets': True,
    'can_view_all_tickets': False,
    'can_edit_client': False,
    'is_active': True,
}


@pytest.fixture
def admin_client():
    return AtendeAquiClient(api_token='test-token', _base_url=f'{BASE_URL}/api')


# =========================================================================
# CRUD de Clientes
# =========================================================================

class TestClientsList:
    @responses.activate
    def test_list_clients(self, admin_client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/clients/',
            json={'results': [CLIENT_DATA]},
            status=200,
        )

        clientes = admin_client.clients.list()

        assert len(clientes) == 1
        assert isinstance(clientes[0], Client)
        assert clientes[0].client_id == 'abc-123-uuid'
        assert clientes[0].full_name == 'Acme Corp'
        assert clientes[0].team_count == 1

    @responses.activate
    def test_list_with_pagination(self, admin_client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/clients/',
            json={'results': [CLIENT_DATA], 'count': 1, 'next': None},
            status=200,
        )

        admin_client.clients.list(page=2, page_size=10)
        assert 'page=2' in responses.calls[0].request.url
        assert 'page_size=10' in responses.calls[0].request.url


class TestClientsGet:
    @responses.activate
    def test_get_client(self, admin_client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/clients/abc-123-uuid/',
            json=CLIENT_DATA,
            status=200,
        )

        cliente = admin_client.clients.get('abc-123-uuid')

        assert isinstance(cliente, Client)
        assert cliente.email == 'contato@acme.com'
        assert len(cliente.team_members) == 1
        assert cliente.team_members[0].full_name == 'João Silva'
        assert cliente.team_members[0].is_primary is True

    @responses.activate
    def test_get_not_found(self, admin_client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/clients/nao-existe/',
            json={'detail': 'Not found.'},
            status=404,
        )

        with pytest.raises(NotFoundError):
            admin_client.clients.get('nao-existe')


class TestClientsCreate:
    @responses.activate
    def test_create_client(self, admin_client):
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/clients/',
            json=CLIENT_DATA,
            status=201,
        )

        cliente = admin_client.clients.create(
            full_name='Acme Corp',
            email='contato@acme.com',
            phone='1133334444',
            identification_number='12.345.678/0001-90',
            type_identification='CNPJ',
        )

        assert isinstance(cliente, Client)
        assert cliente.client_id == 'abc-123-uuid'

        body = json.loads(responses.calls[0].request.body)
        assert body['full_name'] == 'Acme Corp'
        assert body['email'] == 'contato@acme.com'

    @responses.activate
    def test_create_minimal(self, admin_client):
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/clients/',
            json={**CLIENT_DATA, 'email': '', 'phone': ''},
            status=201,
        )

        admin_client.clients.create(full_name='Empresa X')

        body = json.loads(responses.calls[0].request.body)
        assert body == {'full_name': 'Empresa X'}

    @responses.activate
    def test_create_with_custom_client_id(self, admin_client):
        custom_data = {**CLIENT_DATA, 'client_id': 'meu-sistema-123'}
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/clients/',
            json=custom_data,
            status=201,
        )

        cliente = admin_client.clients.create(
            full_name='Acme Corp',
            client_id='meu-sistema-123',
        )

        assert cliente.client_id == 'meu-sistema-123'
        body = json.loads(responses.calls[0].request.body)
        assert body['client_id'] == 'meu-sistema-123'
        assert body['full_name'] == 'Acme Corp'


class TestClientsUpdate:
    @responses.activate
    def test_update_client(self, admin_client):
        updated = {**CLIENT_DATA, 'full_name': 'Acme Corp Ltda'}
        responses.add(
            responses.PATCH,
            f'{BASE_URL}/api/clients/abc-123-uuid/',
            json=updated,
            status=200,
        )

        cliente = admin_client.clients.update('abc-123-uuid', full_name='Acme Corp Ltda')

        assert cliente.full_name == 'Acme Corp Ltda'
        body = json.loads(responses.calls[0].request.body)
        assert body == {'full_name': 'Acme Corp Ltda'}


# =========================================================================
# Equipe do Cliente
# =========================================================================

class TestClientsTeam:
    @responses.activate
    def test_get_team(self, admin_client):
        responses.add(
            responses.GET,
            f'{BASE_URL}/api/clients/abc-123-uuid/team/',
            json=[CLIENT_DATA['team_members'][0], TEAM_MEMBER_DATA],
            status=200,
        )

        team = admin_client.clients.get_team('abc-123-uuid')

        assert len(team) == 2
        assert isinstance(team[0], TeamMember)
        assert team[0].is_primary is True
        assert team[1].full_name == 'Maria Santos'

    @responses.activate
    def test_add_team_member_by_email(self, admin_client):
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/clients/abc-123-uuid/add-team-member/',
            json=TEAM_MEMBER_DATA,
            status=201,
        )

        member = admin_client.clients.add_team_member(
            client_id='abc-123-uuid',
            user_email='maria@acme.com',
            can_view_all_tickets=False,
        )

        assert isinstance(member, TeamMember)
        assert member.email == 'maria@acme.com'

        body = json.loads(responses.calls[0].request.body)
        assert body['user_email'] == 'maria@acme.com'
        assert body['can_view_all_tickets'] is False

    @responses.activate
    def test_add_team_member_by_id(self, admin_client):
        responses.add(
            responses.POST,
            f'{BASE_URL}/api/clients/abc-123-uuid/add-team-member/',
            json=TEAM_MEMBER_DATA,
            status=201,
        )

        admin_client.clients.add_team_member(
            client_id='abc-123-uuid',
            user_id=42,
        )

        body = json.loads(responses.calls[0].request.body)
        assert body['user_id'] == 42

    @responses.activate
    def test_update_team_member(self, admin_client):
        updated = {**TEAM_MEMBER_DATA, 'is_primary': True}
        responses.add(
            responses.PATCH,
            f'{BASE_URL}/api/clients/abc-123-uuid/update-team-member/2/',
            json=updated,
            status=200,
        )

        member = admin_client.clients.update_team_member(
            client_id='abc-123-uuid',
            member_id=2,
            is_primary=True,
        )

        assert member.is_primary is True

    @responses.activate
    def test_remove_team_member(self, admin_client):
        responses.add(
            responses.DELETE,
            f'{BASE_URL}/api/clients/abc-123-uuid/remove-team-member/2/',
            status=204,
        )

        admin_client.clients.remove_team_member(client_id='abc-123-uuid', member_id=2)
        assert responses.calls[0].request.method == 'DELETE'


# =========================================================================
# Models
# =========================================================================

class TestClientModel:
    def test_from_dict(self):
        cliente = Client.from_dict(CLIENT_DATA)

        assert cliente.client_id == 'abc-123-uuid'
        assert cliente.full_name == 'Acme Corp'
        assert cliente.is_active is True
        assert len(cliente.team_members) == 1
        assert cliente.team_count == 1

    def test_from_dict_defaults(self):
        cliente = Client.from_dict({})

        assert cliente.client_id == ''
        assert cliente.full_name == ''
        assert cliente.is_active is True
        assert cliente.preferred_language == 'pt-BR'
        assert cliente.team_members == []
        assert cliente.team_count == 0


class TestTeamMemberModel:
    def test_from_dict(self):
        member = TeamMember.from_dict(TEAM_MEMBER_DATA)

        assert member.id == 2
        assert member.full_name == 'Maria Santos'
        assert member.email == 'maria@acme.com'
        assert member.is_primary is False
        assert member.can_create_tickets is True
        assert member.can_view_all_tickets is False

    def test_from_dict_defaults(self):
        member = TeamMember.from_dict({})

        assert member.id == 0
        assert member.is_primary is False
        assert member.can_create_tickets is True
