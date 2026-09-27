"""Leitura e normalização da lista de stop words. Só funções puras.

`sem_acento` mora aqui, e não no vetorizador, porque ela existe *para* esta
comparação: normalizar só para comparar, nunca para exibir. A palavra que vai
para a nuvem é sempre a original.

Nada aqui lê arquivo. Onde a lista mora é decisão do app (ver `config.py`);
este módulo só sabe transformar texto bruto em termos comparáveis.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

# Aceita a lista escrita de qualquer jeito razoável: uma por linha, separadas
# por vírgula, ou por ponto e vírgula.
SEPARADOR = re.compile(r"[,;\n\r]+")


def sem_acento(palavra: str) -> str:
    """'Ação' -> 'acao'. Usado só para COMPARAR, nunca para exibir.

    O NFKD separa a letra do acento em dois caracteres; sobra descartar os que
    são "combinantes" (o acento solto).
    """
    decomposto = unicodedata.normalize("NFKD", palavra)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def ler(bruto: str) -> list[str]:
    """Quebra o texto do campo de stop words em termos, descartando o vazio."""
    return [termo.strip() for termo in SEPARADOR.split(bruto) if termo.strip()]


def normalizar(termos: Iterable[str]) -> frozenset[str]:
    """Minúsculas e sem acento, para o filtro tolerar 'nao' no lugar de 'não'.

    `frozenset` porque o único uso é `token in stopwords`, dentro de um laço que
    roda uma vez por palavra do texto: busca em conjunto é O(1).
    """
    return frozenset(
        sem_acento(termo.strip().lower()) for termo in termos if termo.strip()
    )
