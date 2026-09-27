"""Counter -> DataFrame, no formato que vai para a tela e para o CSV.

Mora aqui, e não no `core`, porque um DataFrame é formato de apresentação: as
colunas "#" e "% do total" existem para quem lê a tabela, não para o pipeline.
É também o único ponto do projeto que precisa do pandas.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence

import pandas as pd


def montar(contagens: Counter[str], quantidade: int, rotulo: str) -> pd.DataFrame:
    """As `quantidade` entradas mais frequentes, com posição e percentual.

    O `or 1` no total evita divisão por zero com um Counter vazio — a tela já
    trata esse caso antes, mas a função não depende disso para não quebrar.
    """
    itens = contagens.most_common(quantidade)
    total = sum(contagens.values()) or 1
    return pd.DataFrame(
        {
            "#": range(1, len(itens) + 1),
            rotulo: [termo for termo, _ in itens],
            "ocorrências": [contagem for _, contagem in itens],
            "% do total": [round(100 * contagem / total, 2) for _, contagem in itens],
        }
    )


def bruto(
    grupos: Iterable[tuple[tuple[str, ...], Counter[str]]], dimensoes: Sequence[str]
) -> pd.DataFrame:
    """Uma linha por (valores das dimensões, palavra), com TODAS as palavras.

    Formato "longo", o que planilha e tabela dinâmica leem melhor. Sem
    dimensões, as chaves são `()` e sobram só as colunas palavra e ocorrências.
    """
    linhas = [
        (*chave, palavra, contagem)
        for chave, contagens in grupos
        for palavra, contagem in contagens.most_common()
    ]
    return pd.DataFrame(linhas, columns=[*dimensoes, "palavra", "ocorrências"])
