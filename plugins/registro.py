"""Descobre os plugins olhando as subpastas de `plugins/`.

Automático de propósito: criar a pasta `plugins/pdf/` com um `FONTE` dentro já
faz a opção aparecer na tela, sem editar nenhuma lista central — e sem esquecer
de editar.

Regra única: **plugin é subpasta**. É por isso que o filtro abaixo usa
`info.ispkg` — assim `base.py` e este próprio `registro.py`, que são módulos
soltos aqui dentro, ficam de fora sem precisar de lista de exceções.
"""

from __future__ import annotations

import importlib
import pkgutil
from functools import cache
from pathlib import Path

from .base import FonteTexto

_PASTA = Path(__file__).parent


@cache
def _classes() -> tuple[type[FonteTexto], ...]:
    """Varre o disco UMA vez por processo — é isso que o `@cache` garante.

    O Streamlit re-executa o script inteiro a cada interação; sem o cache, cada
    clique de slider daria uma listagem de diretório e um `getattr` por plugin.
    """
    encontradas: list[type[FonteTexto]] = []

    for info in pkgutil.iter_modules([str(_PASTA)]):
        if not info.ispkg or info.name.startswith("_"):
            continue

        modulo = importlib.import_module(f"{__package__}.{info.name}")
        fonte = getattr(modulo, "FONTE", None)

        # Falha barulhenta: uma pasta dentro de plugins/ sem FONTE é
        # esquecimento, não intenção. Melhor quebrar agora, com a instrução do
        # conserto junto, do que o plugin sumir da tela sem explicação.
        if fonte is None:
            raise RuntimeError(
                f"plugins/{info.name}/__init__.py não expõe FONTE. "
                f"Acrescente: from .fonte import MinhaFonte as FONTE"
            )
        if not (isinstance(fonte, type) and issubclass(fonte, FonteTexto)):
            raise TypeError(
                f"plugins/{info.name}: FONTE precisa ser a CLASSE (não uma "
                f"instância) e herdar de FonteTexto."
            )
        encontradas.append(fonte)

    # A ordem do `iter_modules` depende do sistema de arquivos. Ordenar pelo
    # nome impede que o seletor troque de ordem entre uma máquina e outra.
    return tuple(sorted(encontradas, key=lambda classe: classe.nome.lower()))


def fontes() -> list[FonteTexto]:
    """Instâncias NOVAS a cada chamada — os plugins são sem estado de propósito.

    Guardar a instância numa variável de módulo compartilharia o mesmo objeto
    entre todas as sessões do Streamlit (um processo serve vários visitantes).
    Criar três objetos vazios por re-execução não custa nada e apaga essa classe
    de bug inteira.
    """
    return [classe() for classe in _classes()]


def por_id(id_fonte: str) -> FonteTexto:
    """A fonte com esse id — usada para reconstruir a escolha guardada no seletor."""
    for classe in _classes():
        if classe.id == id_fonte:
            return classe()
    raise KeyError(f"Nenhuma fonte com id {id_fonte!r}.")
