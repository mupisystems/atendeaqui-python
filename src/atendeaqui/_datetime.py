"""Datas para a API: ISO 8601 sempre com fuso."""
from __future__ import annotations

from datetime import datetime


def format_occurred_at(occurred_at: datetime | str | None) -> str | None:
    """
    ``occurred_at`` como ISO 8601 para a API.

    datetime sem fuso é recusado: a API o leria no fuso do servidor, e o
    evento ficaria registrado horas antes ou depois do que aconteceu.
    """
    if occurred_at is None or isinstance(occurred_at, str):
        return occurred_at
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise ValueError(
            'occurred_at precisa ter fuso horário (ex.: datetime.now(timezone.utc) '
            'ou django.utils.timezone.now()).'
        )
    return occurred_at.isoformat()
