"""Nuvem de Palavras — MVP.

Este arquivo só orquestra. Ele é o único que conhece as quatro camadas, e o que
faz é ligar uma na outra:

    plugins ──► Corpus ──► dimensoes (filtra) ──► bytes ──► core ──► Analise ──► visual

Nenhuma regra de negócio mora aqui: quem sabe ler a fonte é o plugin, quem sabe
filtrar por dimensão é `dimensoes`, quem sabe contar palavras é o `core`, quem
sabe desenhar é o `visual`.

O clique em "Processar" lê a fonte UMA vez e guarda a coleção de documentos. A
contagem é refeita só quando os filtros da aba Palavras mudam; os sliders
apenas refatiam o resultado já em memória.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

import config
from core import N_MINIMO, Analise, Vetorizador, frequencias_por_grupo
from core import stopwords as sw
from dimensoes import Colecao
from plugins import registro
from plugins.base import ErroDeFonte
from visual import filtros, paineis, tabelas

if TYPE_CHECKING:
    import pandas as pd

st.set_page_config(page_title="Nuvem de Palavras", page_icon="☁️", layout="wide")

Parametros = tuple[tuple[str, ...], int, int]  # stop words, tamanho mínimo, n máximo


@st.cache_data(show_spinner="Processando o texto…", max_entries=3, ttl=3600)
def analisar_em_cache(
    dados: bytes, stopwords: tuple[str, ...], tamanho_minimo: int, n_maximo: int
) -> Analise:
    """Wrapper fino sobre o núcleo, só para ganhar o cache do Streamlit.

    Ele mora AQUI, e não dentro de `core/`, porque é o decorador que amarraria o
    núcleo ao Streamlit — e o núcleo é justamente a camada que não pode conhecer
    a tela.

    Todos os argumentos são hasheáveis (bytes, tupla, int), que é o que o cache
    exige. `max_entries` e `ttl` existem por causa do deploy: o cache é
    compartilhado por todas as sessões e no Community Cloud a memória é pouca —
    sem teto, cada texto novo enviado por qualquer visitante ficaria guardado.
    """
    return Vetorizador(dados).analisar(stopwords, tamanho_minimo, n_maximo)


def atualizar_analise(colecao: Colecao, indices: tuple[int, ...]) -> None:
    """Recalcula a análise só se o processamento ou os filtros mudaram.

    A comparação com a chave anterior é o que deixa os sliders baratos: mexer
    neles não junta os documentos de novo nem consulta o cache.
    """
    chave = (st.session_state.geracao, indices)
    if st.session_state.analise_chave == chave:
        return
    st.session_state.analise = analisar_em_cache(
        colecao.juntar(indices), *st.session_state.parametros
    )
    st.session_state.analise_chave = chave


def frequencias_brutas(
    colecao: Colecao, indices: tuple[int, ...], parametros: Parametros
) -> pd.DataFrame:
    """Contagem de todas as palavras por combinação de valores das dimensões."""
    stopwords, tamanho_minimo, _ = parametros
    grupos = frequencias_por_grupo(colecao.agrupar(indices), stopwords, tamanho_minimo)
    return tabelas.bruto(sorted(grupos.items()), colecao.nomes)


# `setdefault` roda antes dos widgets: o campo de stop words nasce preenchido e,
# a partir daí, é o próprio widget que mantém a chave no session_state.
st.session_state.setdefault("stopwords_txt", config.carregar_stopwords())
st.session_state.setdefault("colecao", None)
st.session_state.setdefault("parametros", None)
st.session_state.setdefault("geracao", 0)
st.session_state.setdefault("analise", None)
st.session_state.setdefault("analise_chave", None)
st.session_state.setdefault("corpus_nome", "")
st.session_state.setdefault("corpus_codificacao", None)


st.title("☁️ Nuvem de Palavras")

aba_preferencias, aba_palavras = st.tabs(["⚙️ Preferências", "☁️ Palavras"])


with aba_preferencias:
    coluna_fonte, coluna_limpeza = st.columns(2, gap="large")

    with coluna_fonte:
        st.subheader("1. Fontes")
        fonte, pedido = paineis.painel_fontes(registro.fontes())

        st.subheader("3. Parâmetros")
        tamanho_minimo = st.number_input(
            "Tamanho mínimo da palavra",
            min_value=1,
            max_value=10,
            value=config.TAMANHO_MINIMO_PADRAO,
            help="Descarta tokens mais curtos que isso, antes das stop words.",
        )

        processar = st.button(
            "Processar", type="primary", width="stretch", disabled=pedido is None
        )
        if pedido is None:
            st.caption("Preencha o formulário da fonte para habilitar o processamento.")

    with coluna_limpeza:
        st.subheader("2. Stop words")
        texto_stopwords = paineis.painel_stopwords()

    if processar and pedido is not None:
        try:
            corpus = fonte.obter_corpus(pedido)
        except ErroDeFonte as erro:
            # Só ErroDeFonte é tratado: é a falha que o plugin PREVIU e traduziu
            # para o usuário. Qualquer outra exceção é bug, e bug tem que
            # aparecer inteiro em vez de virar uma mensagem simpática.
            st.error(str(erro))
        else:
            st.session_state.colecao = Colecao(corpus.documentos, corpus.dimensoes)
            st.session_state.parametros = (
                tuple(sw.ler(texto_stopwords)),
                int(tamanho_minimo),
                config.N_MAXIMO_UI,
            )
            st.session_state.corpus_nome = corpus.nome
            st.session_state.corpus_codificacao = corpus.codificacao
            # Geração nova: invalida a análise anterior e troca o prefixo das
            # keys dos filtros, que assim renascem vazios para o corpus novo.
            st.session_state.geracao += 1

    # O resumo depende da análise, que agora é calculada na aba Palavras — mais
    # abaixo no script, depois dos filtros. O contêiner reserva o lugar aqui e
    # é preenchido no fim.
    resumo = st.container()


registros: tuple[int, int] | None = None

with aba_palavras:
    colecao: Colecao | None = st.session_state.colecao

    if colecao is None:
        st.info(
            "Vá até **⚙️ Preferências**, escolha uma fonte, ajuste as stop words "
            "se quiser e clique em **Processar**."
        )
    else:
        indices = colecao.todos()
        if colecao.tem_dimensoes:
            ativos = filtros.painel_filtros(colecao, f"filtro{st.session_state.geracao}")
            indices = colecao.filtrar(ativos)
            registros = (len(indices), len(colecao))

        atualizar_analise(colecao, indices)
        analise = st.session_state.analise

        if not indices:
            st.warning("Nenhum registro atende aos filtros. Afrouxe algum deles.")
        elif analise.vazia:
            st.warning(
                "Nenhuma palavra sobrou depois do filtro. Reduza o tamanho mínimo ou "
                "remova stop words da lista."
            )
        else:
            paineis.painel_nuvem(analise)
            st.divider()
            paineis.painel_sequencias(analise, N_MINIMO, config.N_MAXIMO_UI)
            st.divider()
            parametros = st.session_state.parametros
            paineis.painel_bruto(
                lambda: frequencias_brutas(colecao, indices, parametros),
                (st.session_state.geracao, hash(indices)),
                colecao.tem_dimensoes,
            )


with resumo:
    paineis.painel_resumo(
        st.session_state.analise,
        st.session_state.corpus_nome,
        st.session_state.corpus_codificacao,
        registros,
    )
