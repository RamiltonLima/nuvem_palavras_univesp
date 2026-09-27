"""Montagem dos dicionários de configuração ("options") do ECharts.

Separado dos painéis porque isto é dado, não interface: são dicts puros que dá
para inspecionar num REPL sem subir o Streamlit. O `st_echarts` só recebe o
dict pronto e o entrega ao ECharts no navegador.

É o único arquivo do projeto que atravessou a refatoração sem uma vírgula
mudada — ele já estava no lugar certo.
"""

from __future__ import annotations

# Paleta tableau10: tons médios, legíveis tanto no tema claro quanto no escuro.
PALETA = [
    "#4C78A8",
    "#F58518",
    "#54A24B",
    "#E45756",
    "#72B7B2",
    "#B279A2",
    "#EECA3B",
    "#FF9DA6",
    "#9D755D",
    "#79706E",
]

COR_BARRA = "#4C78A8"


def _toolbox(nome_arquivo: str) -> dict:
    """Botão nativo do ECharts que baixa o gráfico como PNG (client-side)."""
    return {
        "show": True,
        "feature": {
            "saveAsImage": {
                "show": True,
                "title": "Baixar PNG",
                "name": nome_arquivo,
                "pixelRatio": 2,
            }
        },
    }


def opcoes_nuvem(itens: list[tuple[str, int]]) -> dict:
    """Nuvem de palavras a partir de pares (palavra, ocorrências)."""
    dados = [
        {
            "name": palavra,
            "value": contagem,
            # A cor vai item a item, definida aqui em Python, em vez de uma
            # função JS aleatória: assim o desenho não muda de cor a cada rerun.
            "textStyle": {"color": PALETA[indice % len(PALETA)]},
        }
        for indice, (palavra, contagem) in enumerate(itens)
    ]

    return {
        "tooltip": {"show": True, "formatter": "{b}: <b>{c}</b>"},
        "toolbox": _toolbox("nuvem_de_palavras"),
        "series": [
            {
                "type": "wordCloud",
                "shape": "circle",
                "width": "94%",
                "height": "94%",
                "sizeRange": [14, 84],
                "rotationRange": [-45, 45],
                "rotationStep": 45,
                "gridSize": 8,
                # Sem isto o ECharts corta palavras na borda do quadro.
                "drawOutOfBound": False,
                "shrinkToFit": True,
                "emphasis": {"focus": "self"},
                "data": dados,
            }
        ],
    }


def opcoes_barras(itens: list[tuple[str, int]], titulo: str) -> dict:
    """Barras horizontais para as sequências mais frequentes.

    O ECharts desenha a primeira categoria do eixo Y embaixo, então a lista é
    invertida para que a sequência mais frequente apareça no topo.
    """
    rotulos = [termo for termo, _ in itens][::-1]
    valores = [contagem for _, contagem in itens][::-1]

    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "toolbox": _toolbox(titulo),
        "grid": {"left": "2%", "right": "8%", "top": "2%", "bottom": "6%", "containLabel": True},
        "xAxis": {"type": "value", "minInterval": 1},
        "yAxis": {"type": "category", "data": rotulos, "axisLabel": {"width": 220, "overflow": "truncate"}},
        "series": [
            {
                "type": "bar",
                "data": valores,
                "itemStyle": {"color": COR_BARRA, "borderRadius": [0, 4, 4, 0]},
                "label": {"show": True, "position": "right"},
            }
        ],
    }
