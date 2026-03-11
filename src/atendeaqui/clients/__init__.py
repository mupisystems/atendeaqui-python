"""
Módulo de Clientes do SDK AtendeAqui.

Acessado via client.clients:

    from atendeaqui import AtendeAquiClient

    client = AtendeAquiClient(api_token="...")
    clientes = client.clients.list()
    novo = client.clients.create(full_name="Acme Corp", email="contato@acme.com")
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .models import Client, TeamMember

if TYPE_CHECKING:
    from .._http import HttpClient


class ClientsModule:
    """
    Módulo de Clientes — acesso via client.clients.

    Requer api_token (Bearer token).
    """

    def __init__(self, http: HttpClient):
        self._http = http

    # =========================================================================
    # CRUD DE CLIENTES
    # =========================================================================

    def list(self, page: int = 1, page_size: int = 50) -> list[Client]:
        """
        Lista todos os clientes da organização.

        Args:
            page: Número da página (padrão: 1).
            page_size: Itens por página (máximo: 50).
        """
        params = {'page': page, 'page_size': page_size}
        data = self._http.get('clients/', params=params)
        results = data.get('results', data) if isinstance(data, dict) else data
        return [Client.from_dict(r) for r in results]

    def get(self, client_id: str) -> Client:
        """
        Retorna detalhes completos de um cliente.

        Args:
            client_id: UUID do cliente.
        """
        data = self._http.get(f'clients/{client_id}/')
        return Client.from_dict(data)

    def create(
        self,
        full_name: str,
        email: str = '',
        phone: str = '',
        identification_number: str = '',
        type_identification: str = '',
        birthday: str | None = None,
        observations: str = '',
        preferred_language: str = 'pt-BR',
        client_id: str | None = None,
    ) -> Client:
        """
        Cria um novo cliente na organização.

        Args:
            full_name: Nome completo do cliente ou empresa.
            email: E-mail de contato.
            phone: Telefone.
            identification_number: CPF ou CNPJ.
            type_identification: Tipo do documento (CPF, CNPJ, etc.).
            birthday: Data de nascimento (YYYY-MM-DD).
            observations: Observações livres.
            preferred_language: Idioma preferido (pt-BR, en-US, etc.).
            client_id: Opcional. ID externo do cliente no seu sistema.
                Se não fornecido, um UUID é gerado automaticamente.
                Útil para manter o mesmo identificador entre sistemas.
        """
        body: dict = {'full_name': full_name}
        if client_id:
            body['client_id'] = client_id
        if email:
            body['email'] = email
        if phone:
            body['phone'] = phone
        if identification_number:
            body['identification_number'] = identification_number
        if type_identification:
            body['type_identification'] = type_identification
        if birthday:
            body['birthday'] = birthday
        if observations:
            body['observations'] = observations
        if preferred_language != 'pt-BR':
            body['preferred_language'] = preferred_language

        data = self._http.post('clients/', json=body)
        return Client.from_dict(data)

    def update(
        self,
        client_id: str,
        **fields,
    ) -> Client:
        """
        Atualiza um cliente existente (partial update).

        Args:
            client_id: UUID do cliente.
            **fields: Campos a atualizar (full_name, email, phone, etc.).
        """
        data = self._http.patch(f'clients/{client_id}/', json=fields)
        return Client.from_dict(data)

    # =========================================================================
    # EQUIPE DO CLIENTE
    # =========================================================================

    def get_team(self, client_id: str) -> list[TeamMember]:
        """
        Lista todos os membros da equipe de um cliente.

        Args:
            client_id: UUID do cliente.
        """
        data = self._http.get(f'clients/{client_id}/team/')
        results = data if isinstance(data, list) else data.get('results', [])
        return [TeamMember.from_dict(m) for m in results]

    def add_team_member(
        self,
        client_id: str,
        user_email: str | None = None,
        user_id: int | None = None,
        is_primary: bool = False,
        can_create_tickets: bool = True,
        can_view_all_tickets: bool = True,
        can_edit_client: bool = False,
        notes: str = '',
    ) -> TeamMember:
        """
        Adiciona um membro à equipe do cliente.

        Forneça user_email (cria o usuário se não existir) ou user_id.

        Args:
            client_id: UUID do cliente.
            user_email: E-mail do usuário (cria se não existir).
            user_id: ID de um usuário existente.
            is_primary: Marcar como contato principal.
            can_create_tickets: Permissão para criar tickets.
            can_view_all_tickets: Permissão para ver todos os tickets.
            can_edit_client: Permissão para editar dados do cliente.
            notes: Observações sobre o membro.
        """
        body: dict = {
            'is_primary': is_primary,
            'can_create_tickets': can_create_tickets,
            'can_view_all_tickets': can_view_all_tickets,
            'can_edit_client': can_edit_client,
        }
        if user_email:
            body['user_email'] = user_email
        if user_id is not None:
            body['user_id'] = user_id
        if notes:
            body['notes'] = notes

        data = self._http.post(f'clients/{client_id}/add-team-member/', json=body)
        return TeamMember.from_dict(data)

    def update_team_member(
        self,
        client_id: str,
        member_id: int,
        **fields,
    ) -> TeamMember:
        """
        Atualiza permissões de um membro da equipe.

        Args:
            client_id: UUID do cliente.
            member_id: ID do membro.
            **fields: Campos a atualizar (is_primary, can_create_tickets, etc.).
        """
        data = self._http.patch(f'clients/{client_id}/update-team-member/{member_id}/', json=fields)
        return TeamMember.from_dict(data)

    def remove_team_member(self, client_id: str, member_id: int) -> None:
        """
        Remove um membro da equipe (soft delete).

        Args:
            client_id: UUID do cliente.
            member_id: ID do membro.
        """
        self._http.delete(f'clients/{client_id}/remove-team-member/{member_id}/')
