"""O painel de filtros por dimensão, na aba Palavras.

Cada dimensão ganha o filtro que combina com o tipo dela: lista de valores e
busca para texto, intervalo para número, período para data. O tipo começa no
que a amostragem detectou, mas o usuário pode trocar.

Devolve só os filtros ATIVOS — um filtro no estado inicial (tudo marcado,
intervalo cheio) não é devolvido, para a coleção não percorrer uma coluna à toa.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

import config
from dimensoes import (
    Colecao,
    Dimensao,
    Filtro,
    FiltroData,
    FiltroNumero,
    FiltroTexto,
    TipoDimensao,
)

POR_LINHA = 3

FiltrosAtivos = dict[str, tuple[TipoDimensao, Filtro]]


def painel_filtros(colecao: Colecao, prefixo: str) -> FiltrosAtivos:
    """Desenha um bloco por dimensão e devolve {nome: (tipo, filtro)} dos ativos.

    `prefixo` entra em todas as keys: o app troca o prefixo a cada Processar, e
    é isso que zera os filtros quando chega um arquivo novo.
    """
    ativos: FiltrosAtivos = {}
    with st.expander("🔎 Filtros por dimensão", expanded=True):
        st.button(
            "Limpar filtros",
            on_click=_limpar,
            args=(prefixo,),
            key=f"{prefixo}_limpar",
        )
        dimensoes = list(colecao.dimensoes.values())
        for inicio in range(0, len(dimensoes), POR_LINHA):
            colunas = st.columns(POR_LINHA, gap="medium")
            for coluna, (i, dimensao) in zip(
                colunas, enumerate(dimensoes[inicio : inicio + POR_LINHA], start=inicio)
            ):
                with coluna, st.container(border=True):
                    tipo, filtro = _bloco(dimensao, f"{prefixo}_{i}")
                    if filtro is not None:
                        ativos[dimensao.nome] = (tipo, filtro)
    return ativos


def _limpar(prefixo: str) -> None:
    """Callback: apagar as keys faz os widgets renascerem no valor padrão."""
    for chave in [k for k in st.session_state if str(k).startswith(f"{prefixo}_")]:
        del st.session_state[chave]


def _bloco(dimensao: Dimensao, chave: str) -> tuple[TipoDimensao, Filtro | None]:
    """Seletor de tipo + o filtro daquele tipo."""
    st.markdown(f"**{dimensao.nome}**")
    tipos = [tipo.value for tipo in TipoDimensao]
    # As opções são as strings do Enum, não os membros: o session_state guarda
    # o valor escolhido entre re-execuções, e string compara sem surpresa.
    escolhido = st.selectbox(
        "Tipo",
        tipos,
        index=tipos.index(dimensao.deteccao.tipo.value),
        format_func=str.capitalize,
        key=f"{chave}_tipo",
        help=f"Detectado por amostragem: {dimensao.deteccao.descricao}.",
    )
    tipo = TipoDimensao(escolhido)
    # O tipo entra na key dos widgets de baixo: trocar de "número" para "data"
    # não pode reaproveitar o valor de um slider num seletor de datas.
    chave = f"{chave}_{tipo.name}"

    if tipo is TipoDimensao.NUMERO:
        return tipo, _filtro_numero(dimensao, chave)
    if tipo is TipoDimensao.DATA:
        return tipo, _filtro_data(dimensao, chave)
    return tipo, _filtro_texto(dimensao, chave)


def _filtro_texto(dimensao: Dimensao, chave: str) -> FiltroTexto | None:
    distintos = dimensao.distintos()
    selecionados: list[str] = []
    excluir = False

    if len(distintos) <= config.MAX_VALORES_MULTISELECT:
        contagem = dict(distintos)
        selecionados = st.multiselect(
            "Valores",
            [valor for valor, _ in distintos],
            format_func=lambda valor: f"{valor or '(vazio)'} ({contagem[valor]})",
            placeholder="Todos",
            key=f"{chave}_valores",
        )
        excluir = (
            st.radio(
                "Os valores marcados",
                ["incluir", "excluir"],
                horizontal=True,
                key=f"{chave}_modo",
            )
            == "excluir"
        )
    else:
        quantidade = f"{len(distintos):,}".replace(",", ".")
        st.caption(f"{quantidade} valores distintos — muitos para listar; use a busca.")

    contem = st.text_input(
        "Contém",
        key=f"{chave}_contem",
        help="Um ou mais termos separados por vírgula. Ignora acentos e maiúsculas.",
    )
    if not selecionados and not contem.strip():
        return None
    return FiltroTexto(frozenset(selecionados), excluir, contem)


def _filtro_numero(dimensao: Dimensao, chave: str) -> FiltroNumero | None:
    extremos = dimensao.extremos(TipoDimensao.NUMERO)
    if extremos is None:
        st.caption("Nenhum valor foi lido como número.")
        return None

    minimo, maximo = extremos
    if dimensao.deteccao_para(TipoDimensao.NUMERO).inteiro:
        minimo, maximo = int(minimo), int(maximo)

    faixa = (minimo, maximo)
    if minimo < maximo:
        faixa = st.slider(
            "Intervalo", min_value=minimo, max_value=maximo, value=faixa, key=f"{chave}_faixa"
        )
    else:
        st.caption(f"Todos os valores são {minimo}.")

    incluir = _incluir_vazios(dimensao, TipoDimensao.NUMERO, chave)
    if faixa == (minimo, maximo) and incluir:
        return None
    return FiltroNumero(faixa[0], faixa[1], incluir)


def _filtro_data(dimensao: Dimensao, chave: str) -> FiltroData | None:
    extremos = dimensao.extremos(TipoDimensao.DATA)
    if extremos is None:
        st.caption("Nenhum valor foi lido como data.")
        return None

    inicio, fim = extremos
    escolha = st.date_input(
        "Período",
        value=(inicio, fim),
        min_value=inicio,
        max_value=fim,
        format="DD/MM/YYYY",
        key=f"{chave}_periodo",
    )
    # Enquanto o usuário escolhe, o seletor devolve só a data inicial: vale
    # como "a partir de", até a segunda data chegar.
    periodo: tuple[date, ...] = escolha if isinstance(escolha, tuple) else (escolha,)
    de = periodo[0] if periodo else inicio
    ate = periodo[1] if len(periodo) > 1 else fim

    incluir = _incluir_vazios(dimensao, TipoDimensao.DATA, chave)
    if (de, ate) == (inicio, fim) and incluir:
        return None
    return FiltroData(de, ate, incluir)


def _incluir_vazios(dimensao: Dimensao, tipo: TipoDimensao, chave: str) -> bool:
    """Checkbox só aparece se existir vazio — senão a pergunta não faz sentido."""
    vazios = dimensao.vazios(tipo)
    if not vazios:
        return True
    return st.checkbox(
        f"Incluir vazios ou ilegíveis ({vazios})", value=True, key=f"{chave}_vazios"
    )
