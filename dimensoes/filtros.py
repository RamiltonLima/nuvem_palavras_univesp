"""Os filtros, um por tipo de dimensão. Cada um só sabe dizer se aceita um valor.

Congelados (e portanto hasheáveis e comparáveis) de propósito: a tela compara o
filtro desta execução com o da anterior para decidir se precisa recontar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from core.stopwords import sem_acento


def _chave(texto: str) -> str:
    """Minúsculas e sem acento: a busca "sao paulo" acha "São Paulo"."""
    return sem_acento(texto.lower())


@dataclass(frozen=True)
class FiltroTexto:
    """Lista de valores (incluir ou excluir) e/ou busca por trecho.

    `contem` aceita vários termos separados por vírgula: basta um aparecer.
    """

    valores: frozenset[str] = frozenset()
    excluir: bool = False
    contem: str = ""
    _termos: tuple[str, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        termos = tuple(_chave(t.strip()) for t in self.contem.split(",") if t.strip())
        object.__setattr__(self, "_termos", termos)

    def aceita(self, valor: str | None) -> bool:
        valor = valor or ""
        if self.valores and (valor in self.valores) == self.excluir:
            return False
        if self._termos:
            chave = _chave(valor)
            return any(termo in chave for termo in self._termos)
        return True


@dataclass(frozen=True)
class FiltroNumero:
    """Intervalo fechado [minimo, maximo]."""

    minimo: float
    maximo: float
    incluir_vazios: bool = True

    def aceita(self, valor: float | None) -> bool:
        if valor is None:
            return self.incluir_vazios
        return self.minimo <= valor <= self.maximo


@dataclass(frozen=True)
class FiltroData:
    """Período fechado [inicio, fim], em dias."""

    inicio: date
    fim: date
    incluir_vazios: bool = True

    def aceita(self, valor: date | None) -> bool:
        if valor is None:
            return self.incluir_vazios
        return self.inicio <= valor <= self.fim


Filtro = FiltroTexto | FiltroNumero | FiltroData
