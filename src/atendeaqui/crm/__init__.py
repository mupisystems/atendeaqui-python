"""
Módulo de CRM do SDK AtendeAqui.

Acessado via client.crm:

    from atendeaqui import AtendeAquiClient

    client = AtendeAquiClient(api_token="...")
    empresa = client.crm.upsert_company(
        platform_id="1842", name="Construtora Alfa", status="cliente", mrr="349.90",
    )

Contrato: AtendeAqui `docs/api-engagement-usage.md`, seção 3.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from .models import Company

if TYPE_CHECKING:
    from .._http import HttpClient

# Distingue "mrr não informado" (não muda no CRM) de "mrr=None" (limpa o valor)
_UNSET = object()


class CrmModule:
    """
    Módulo de CRM — acesso via client.crm.

    Requer api_token (Bearer token).
    """

    def __init__(self, http: HttpClient):
        self._http = http

    def upsert_company(
        self,
        platform_id: str,
        name: str,
        status: str | None = None,
        mrr: str | Decimal | float | None = _UNSET,
    ) -> Company:
        """
        Cria ou atualiza uma empresa do CRM pelo platform_id.

        A plataforma é a fonte da verdade: os campos enviados sobrescrevem os
        do CRM; os omitidos não mudam. Chamar de novo não duplica a empresa.

        Args:
            platform_id: ID da empresa na plataforma de origem (sem '/').
            name: Nome da empresa. Único por organização no CRM.
            status: prospect, trial, cliente ou churned. Omitido: não muda
                (na criação, o CRM usa prospect).
            mrr: MRR atual, ex.: "349.90". Omitido: não muda. None: limpa.

        Raises:
            ValidationError: payload inválido (400) ou nome em uso por outra
                empresa (409).
        """
        body: dict = {'platform_id': str(platform_id), 'name': name}
        if status is not None:
            body['status'] = status
        if mrr is not _UNSET:
            body['mrr'] = None if mrr is None else str(mrr)

        data = self._http.post('crm/companies/', json=body)
        return Company.from_dict(data)
