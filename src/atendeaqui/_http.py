"""
Camada de transporte HTTP compartilhada do SDK.

Encapsula requests.Session com:
- Headers padrão (Content-Type, User-Agent)
- Timeout configurável
- Parsing de respostas de erro padronizadas
- Mapeamento de erros HTTP para exceções do SDK
"""
from __future__ import annotations

import requests

from ._version import __version__
from .exceptions import (
    AtendeAquiError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
    ERROR_CODE_MAP,
)

DEFAULT_TIMEOUT = 30


class HttpClient:
    """Cliente HTTP base para comunicação com a API."""

    def __init__(self, base_url: str, headers: dict, timeout: int = DEFAULT_TIMEOUT):
        self._session = requests.Session()
        self._base_url = base_url.rstrip('/')
        self._timeout = timeout
        self._session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': f'atendeaqui-python/{__version__}',
            **headers,
        })

    def _build_url(self, path: str) -> str:
        path = path.lstrip('/')
        return f'{self._base_url}/{path}'

    def _handle_error(self, response: requests.Response) -> None:
        """Lança exceção apropriada baseada na resposta de erro."""
        status_code = response.status_code

        try:
            data = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            data = {}

        # Formato padronizado: {"error": {"code": "...", "message": "..."}}
        error_data = data.get('error', {})
        code = error_data.get('code', '')
        message = error_data.get('message', '')

        # Fallback para formatos legados do DRF
        if not message:
            if 'detail' in data:
                message = str(data['detail'])
            elif isinstance(data, dict):
                messages = []
                for field_name, errors in data.items():
                    if isinstance(errors, list):
                        messages.extend(str(e) for e in errors)
                    else:
                        messages.append(str(errors))
                message = '; '.join(messages) if messages else response.text
            else:
                message = response.text or f'HTTP {status_code}'

        # Mapear código de erro para exceção específica
        if code and code in ERROR_CODE_MAP:
            exc_class = ERROR_CODE_MAP[code]
            raise exc_class(message, code=code, status_code=status_code, response=response)

        # Fallback por status code
        if status_code == 401 or status_code == 403:
            raise AuthenticationError(message, code=code or 'AUTH_REQUIRED', status_code=status_code, response=response)
        elif status_code == 404:
            raise NotFoundError(message, code=code or 'NOT_FOUND', status_code=status_code, response=response)
        elif status_code == 429:
            raise RateLimitError(message, code=code or 'RATE_LIMITED', status_code=status_code, response=response)
        elif status_code >= 500:
            raise ServerError(message, code=code or 'SERVER_ERROR', status_code=status_code, response=response)
        elif status_code >= 400:
            raise ValidationError(message, code=code or 'VALIDATION_ERROR', status_code=status_code, response=response)

        raise AtendeAquiError(message, code=code, status_code=status_code, response=response)

    def request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> dict:
        """Executa requisição HTTP e retorna dados JSON da resposta."""
        url = self._build_url(path)

        response = self._session.request(
            method=method,
            url=url,
            json=json,
            params=params,
            headers=headers,
            timeout=self._timeout,
        )

        if not response.ok:
            self._handle_error(response)

        if response.status_code == 204:
            return {}

        try:
            return response.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            return {}

    def get(self, path: str, params: dict | None = None, headers: dict | None = None) -> dict:
        return self.request('GET', path, params=params, headers=headers)

    def post(self, path: str, json: dict | None = None, headers: dict | None = None) -> dict:
        return self.request('POST', path, json=json, headers=headers)

    def patch(self, path: str, json: dict | None = None, headers: dict | None = None) -> dict:
        return self.request('PATCH', path, json=json, headers=headers)

    def put(self, path: str, json: dict | None = None, headers: dict | None = None) -> dict:
        return self.request('PUT', path, json=json, headers=headers)

    def delete(self, path: str, headers: dict | None = None) -> dict:
        return self.request('DELETE', path, headers=headers)
