"""
Modelos de dados (dataclasses) para respostas da API de Clientes.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TeamMember:
    """Membro da equipe de um cliente."""
    id: int
    username: str
    email: str
    full_name: str
    is_primary: bool
    can_create_tickets: bool
    can_view_all_tickets: bool
    can_edit_client: bool
    is_active: bool

    @classmethod
    def from_dict(cls, data: dict) -> TeamMember:
        return cls(
            id=data.get('id', 0),
            username=data.get('username', ''),
            email=data.get('email', ''),
            full_name=data.get('full_name', ''),
            is_primary=data.get('is_primary', False),
            can_create_tickets=data.get('can_create_tickets', True),
            can_view_all_tickets=data.get('can_view_all_tickets', True),
            can_edit_client=data.get('can_edit_client', False),
            is_active=data.get('is_active', True),
        )


@dataclass
class Client:
    """Representa um cliente (ClientMembership) na organização."""
    client_id: str
    full_name: str
    email: str
    phone: str
    identification_number: str
    type_identification: str
    birthday: str | None
    observations: str
    is_active: bool
    preferred_language: str
    profession: str
    created_at: str | None
    updated_at: str | None
    team_members: list[TeamMember] = field(default_factory=list)
    team_count: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> Client:
        members_data = data.get('team_members', [])
        return cls(
            client_id=data.get('client_id', ''),
            full_name=data.get('full_name', ''),
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            identification_number=data.get('identification_number', ''),
            type_identification=data.get('type_identification', ''),
            birthday=data.get('birthday'),
            observations=data.get('observations', ''),
            is_active=data.get('is_active', True),
            preferred_language=data.get('preferred_language', 'pt-BR'),
            profession=data.get('profession', ''),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            team_members=[TeamMember.from_dict(m) for m in members_data],
            team_count=data.get('team_count', len(members_data)),
        )
