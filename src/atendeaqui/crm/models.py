"""
Modelos de dados (dataclasses) para respostas da API de CRM.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Company:
    """Empresa do CRM (crm.Company), identificada pelo platform_id da plataforma de origem."""
    platform_id: str
    name: str
    status: str
    mrr: str | None
    segment: str | None
    porte: str | None
    conversion_date: str | None
    monthly_volume: int | None
    website: str | None

    @classmethod
    def from_dict(cls, data: dict) -> Company:
        return cls(
            platform_id=data.get('platform_id', ''),
            name=data.get('name', ''),
            status=data.get('status', ''),
            mrr=data.get('mrr'),
            segment=data.get('segment'),
            porte=data.get('porte'),
            conversion_date=data.get('conversion_date'),
            monthly_volume=data.get('monthly_volume'),
            website=data.get('website'),
        )
