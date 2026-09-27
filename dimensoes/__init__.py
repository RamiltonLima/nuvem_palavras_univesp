"""Dimensões: os campos que acompanham cada documento e servem de filtro.

Camada entre a entrada e o processamento. Os plugins entregam os valores crus
de cada campo; aqui se detecta o tipo (número, data, texto), se aplicam os
filtros e se devolve ao `core` o que ele sempre recebeu — `bytes`.

Como o `core`, este pacote não importa streamlit nem pandas. Uso fora da tela:

    from dimensoes import Colecao, FiltroTexto, TipoDimensao
    colecao = Colecao([b"texto um", b"texto dois"], {"autor": ["Ana", "Bia"]})
    indices = colecao.filtrar({"autor": (TipoDimensao.TEXTO, FiltroTexto(frozenset({"Ana"})))})
    colecao.juntar(indices)  # b"texto um"
"""

from .colecao import Colecao, Dimensao
from .filtros import Filtro, FiltroData, FiltroNumero, FiltroTexto
from .tipos import Deteccao, TipoDimensao, detectar

__all__ = [
    "Colecao",
    "Dimensao",
    "Deteccao",
    "TipoDimensao",
    "detectar",
    "Filtro",
    "FiltroTexto",
    "FiltroNumero",
    "FiltroData",
]
