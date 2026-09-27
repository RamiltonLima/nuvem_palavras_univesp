"""Detecção, por amostragem, do tipo de uma dimensão: número, data ou texto.

Tudo aqui é função pura sobre listas de `str`. O plugin entrega os valores
crus, como vieram do arquivo; é esta camada que decide o que eles são — e é o
tipo que define qual filtro a tela oferece.
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

# Quantos valores não vazios olhar. Uma amostra, e não a coluna inteira, porque
# a detecção roda para cada dimensão ao processar e o custo tem que ser fixo.
AMOSTRA = 500

# Fração mínima da amostra que precisa ser lida como aquele tipo. Não é 100%
# para tolerar um "n/d" ou um "-" perdido no meio de uma coluna de números.
LIMIAR = 0.95

# Ordem importa no empate: dd/mm vem antes de mm/dd porque o público é brasileiro.
# "iso" é tratado à parte por `datetime.fromisoformat`, que aceita as variações
# de hora, fração de segundo e fuso de uma vez só.
FORMATOS_DATA = (
    "iso",
    "%d/%m/%Y",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
    "%m/%d/%Y",
)

_LEGIVEL_DATA = {
    "iso": "aaaa-mm-dd",
    "%d/%m/%Y": "dd/mm/aaaa",
    "%d/%m/%Y %H:%M": "dd/mm/aaaa hh:mm",
    "%d/%m/%Y %H:%M:%S": "dd/mm/aaaa hh:mm:ss",
    "%d-%m-%Y": "dd-mm-aaaa",
    "%d.%m.%Y": "dd.mm.aaaa",
    "%Y/%m/%d": "aaaa/mm/dd",
    "%m/%d/%Y": "mm/dd/aaaa",
}

# "1.234,56" (ponto de milhar, vírgula decimal) e "1,234.56" (o contrário).
# Números sem separador nenhum ("42", "3") casam com os dois.
NUMERO_BR = re.compile(r"[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?")
NUMERO_EN = re.compile(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")


class TipoDimensao(Enum):
    TEXTO = "texto"
    NUMERO = "número"
    DATA = "data"


@dataclass(frozen=True)
class Deteccao:
    """O tipo de uma coluna e o que é preciso saber para convertê-la."""

    tipo: TipoDimensao
    formato: str = ""  # data: formato strptime ou "iso"; número: "br" ou "en"
    inteiro: bool = False

    @property
    def descricao(self) -> str:
        """Para a tela: "data (dd/mm/aaaa)", "número inteiro", "texto"."""
        if self.tipo is TipoDimensao.DATA:
            return f"data ({_LEGIVEL_DATA.get(self.formato, self.formato)})"
        if self.tipo is TipoDimensao.NUMERO:
            return "número inteiro" if self.inteiro else "número decimal"
        return "texto"


def amostrar(valores: Iterable[str]) -> list[str]:
    """Até `AMOSTRA` valores não vazios, sorteados com semente fixa.

    Semente fixa para o mesmo arquivo dar sempre o mesmo tipo; sorteio, e não
    as primeiras linhas, porque arquivos costumam vir ordenados — e as primeiras
    500 linhas de uma coluna podem estar todas vazias.
    """
    preenchidos = [valor.strip() for valor in valores if valor.strip()]
    if len(preenchidos) <= AMOSTRA:
        return preenchidos
    return random.Random(0).sample(preenchidos, AMOSTRA)


def detectar(
    valores: Sequence[str], forcar: TipoDimensao | None = None
) -> Deteccao:
    """O tipo que a amostra sustenta, testando data, depois número, depois texto.

    Com `forcar`, o usuário já escolheu o tipo na tela: devolve o melhor formato
    daquele tipo mesmo que ele não atinja o limiar — o que não for lido vira vazio.
    """
    amostra = amostrar(valores)
    if forcar is TipoDimensao.TEXTO or (not amostra and forcar is None):
        return Deteccao(TipoDimensao.TEXTO)

    minimo = LIMIAR * len(amostra) if forcar is None else 0

    if forcar in (None, TipoDimensao.DATA):
        formato, acertos = _melhor_formato_data(amostra)
        if acertos >= minimo and (acertos or forcar):
            return Deteccao(TipoDimensao.DATA, formato)

    if forcar in (None, TipoDimensao.NUMERO):
        formato = _formato_numero(amostra)
        numeros = [_ler_numero(valor, formato) for valor in amostra]
        lidos = [numero for numero in numeros if numero is not None]
        if len(lidos) >= minimo and (lidos or forcar):
            inteiro = all(numero.is_integer() for numero in lidos)
            return Deteccao(TipoDimensao.NUMERO, formato, inteiro)

    return Deteccao(TipoDimensao.TEXTO)


def converter(
    valores: Iterable[str], deteccao: Deteccao
) -> tuple[str | float | date | None, ...]:
    """A coluna inteira no tipo detectado. Vazio ou ilegível vira `None`.

    Texto é a exceção: vazio continua `""`, porque para um filtro de texto
    "(vazio)" é um valor como outro qualquer, que dá para marcar ou desmarcar.
    """
    if deteccao.tipo is TipoDimensao.DATA:
        return tuple(_ler_data(valor.strip(), deteccao.formato) for valor in valores)
    if deteccao.tipo is TipoDimensao.NUMERO:
        return tuple(_ler_numero(valor.strip(), deteccao.formato) for valor in valores)
    return tuple(valor.strip() for valor in valores)


# ------------------------------------------------------------------- leitores
def _ler_data(texto: str, formato: str) -> date | None:
    if not texto:
        return None
    try:
        if formato == "iso":
            # Exigir o hífen impede que um número como "20240312" (que o
            # fromisoformat aceita) transforme uma coluna numérica em data.
            if "-" not in texto:
                return None
            return datetime.fromisoformat(texto).date()
        return datetime.strptime(texto, formato).date()
    except ValueError:
        return None


def _melhor_formato_data(amostra: Sequence[str]) -> tuple[str, int]:
    """O formato que lê mais valores da amostra, e quantos ele leu."""
    acertos = {
        formato: sum(_ler_data(valor, formato) is not None for valor in amostra)
        for formato in FORMATOS_DATA
    }
    # `max` devolve o primeiro em caso de empate — daí a ordem de FORMATOS_DATA.
    melhor = max(acertos, key=acertos.__getitem__)
    return melhor, acertos[melhor]


def _formato_numero(amostra: Sequence[str]) -> str:
    """"br" ou "en": o padrão que casa com mais valores; no empate, "br".

    O empate é o caso ambíguo — "1.234" é mil duzentos e trinta e quatro aqui e
    um vírgula dois três quatro lá fora. O app é brasileiro, então vence o nosso.
    """
    br = sum(bool(NUMERO_BR.fullmatch(valor)) for valor in amostra)
    en = sum(bool(NUMERO_EN.fullmatch(valor)) for valor in amostra)
    return "en" if en > br else "br"


def _ler_numero(texto: str, formato: str) -> float | None:
    if formato == "br":
        if not NUMERO_BR.fullmatch(texto):
            return None
        return float(texto.replace(".", "").replace(",", "."))
    if not NUMERO_EN.fullmatch(texto):
        return None
    return float(texto.replace(",", ""))
