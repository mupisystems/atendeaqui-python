"""
Modelos de dados (dataclasses) para respostas da API de Engajamento de Uso.
"""
from __future__ import annotations

from dataclasses import dataclass, field

COMPANY_NOT_FOUND = 'empresa não encontrada'


@dataclass
class UsageError:
    """Evento do lote que não foi gravado (vem em `errors` numa resposta 201)."""
    index: int
    event_id: str | None
    error: str

    @property
    def is_company_not_found(self) -> bool:
        """True quando a empresa ainda não existe no CRM.

        Único erro que se resolve reenviando: cadastre a empresa
        (client.crm.upsert_company) e reenvie o evento com o MESMO event_id.
        """
        return self.error == COMPANY_NOT_FOUND

    @classmethod
    def from_dict(cls, data: dict) -> UsageError:
        return cls(
            index=data.get('index', -1),
            event_id=data.get('event_id'),
            error=data.get('error', ''),
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
