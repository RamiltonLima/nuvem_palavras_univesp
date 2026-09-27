"""Caminhos e limites da aplicação.

Módulo folha de propósito: ele não importa nada do projeto, e ninguém do
`core/` importa ele. Onde o `stopwords.txt` mora é decisão da aplicação, não do
pipeline — é justamente por isso que este arquivo existe separado.
"""

from __future__ import annotations

from pathlib import Path

# `Path(__file__).parent` em vez de caminho relativo para não depender do
# diretório de onde o streamlit foi chamado.
RAIZ = Path(__file__).parent

# Solto na raiz de propósito: é o arquivo que você abre no editor e edita à mão.
ARQUIVO_STOPWORDS = RAIZ / "stopwords.txt"

# ---------------------------------------------------------------------------
# Limites da tela. Os limites do pipeline (N_MINIMO, N_MAXIMO) moram no `core`,
# porque são regra de processamento; estes aqui são só o que o widget oferece.
# ---------------------------------------------------------------------------
MAX_PALAVRAS = 200
PADRAO_PALAVRAS = 30

MAX_SEQUENCIAS = 50
PADRAO_SEQUENCIAS = 15

TAMANHO_MINIMO_PADRAO = 3

# Acima disso, o filtro de uma dimensão de texto troca a lista de valores pela
# busca "contém": um multiselect com milhares de opções trava o navegador.
MAX_VALORES_MULTISELECT = 200

# Dial de uma linha: cada `n` a mais é um Counter inteiro guardado na memória.
# Em texto grande, os n-gramas de n>=4 têm quase uma entrada distinta por
# posição do texto — baixar isto para 4 ou 5 é o conserto barato se um dia o
# app engasgar com um arquivo pesado.
N_MAXIMO_UI = 10


def carregar_stopwords() -> str:
    """Devolve o conteúdo bruto do arquivo, ou vazio se ele não existir.

    Só leitura: nada neste projeto grava em `stopwords.txt`. No Streamlit
    Community Cloud o filesystem é efêmero E compartilhado entre os visitantes —
    um botão "salvar" ali sobrescreveria a lista de todo mundo e a mudança
    sumiria no próximo reboot do container. Para alterar a lista padrão, edite
    o arquivo e publique de novo.
    """
    if ARQUIVO_STOPWORDS.exists():
        return ARQUIVO_STOPWORDS.read_text(encoding="utf-8").strip()
    return ""
