"""Núcleo do app: o pipeline de texto, sem nenhuma dependência de tela.

A camada que não conhece ninguém. `plugins/` entrega bytes, `visual/` desenha o
resultado — este pacote fica no meio e importa só a biblioteca padrão.

Uso fora do Streamlit:

    from core import Vetorizador
    analise = Vetorizador.de_texto("Céu azul. Céu azul.").analisar(["de"])
    print(analise.top(5))
"""

from .analise import Analise
from .vetorizador import (
    CODIFICACOES,
    N_MAXIMO,
    N_MINIMO,
    SEPARADOR_SEGMENTO,
    TOKEN,
    Vetorizador,
    frequencias_por_grupo,
)

__all__ = [
    "Analise",
    "Vetorizador",
    "frequencias_por_grupo",
    "CODIFICACOES",
    "SEPARADOR_SEGMENTO",
    "TOKEN",
    "N_MINIMO",
    "N_MAXIMO",
]
