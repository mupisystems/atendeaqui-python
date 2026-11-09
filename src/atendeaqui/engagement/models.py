"""
Modelos de dados (dataclasses) para respostas da API de Engajamento de Uso.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CLIENT_NOT_FOUND = 'CLIENT_NOT_FOUND'


@dataclass
class UsageError:
    """Evento do lote que não foi gravado (vem em `errors` numa resposta 201)."""
    index: int
    event_id: str | None
    error: str
    code: str = ''

    @property
    def is_client_not_found(self) -> bool:
        """True quando o cliente (client_id) ainda não existe no AtendeAqui.

        Único erro que se resolve reenviando: cadastre o cliente
        (client.clients.create) e reenvie o evento com o MESMO event_id.
        Decide pelo `code`, nunca pelo texto do erro.
        """
        return self.code == CLIENT_NOT_FOUND

    @classmethod
    def from_dict(cls, data: dict) -> UsageError:
        return cls(
            index=data.get('index', -1),
            event_id=data.get('event_id'),
            error=data.get('error', ''),
            code=data.get('code', ''),
        )


@dataclass
class UsageResult:
    """Resultado de um lote: novos gravados, duplicados (não são erro) e erros."""
    accepted: int = 0
    duplicates: int = 0
    errors: list[UsageError] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> UsageResult:
        return cls(
            accepted=data.get('accepted', 0),
            duplicates=data.get('duplicates', 0),
            errors=[UsageError.from_dict(e) for e in data.get('errors', [])],
        )
