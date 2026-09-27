"""Um arquivo CSV: um campo vira o corpus, outros viram dimensões.

Cada linha do arquivo é um documento. O usuário aponta a coluna com o texto e
marca as colunas que servirão de filtro (autor, cidade, data…). O plugin só
entrega os valores crus dessas colunas; descobrir se são número, data ou texto
é trabalho da camada `dimensoes`.

A pasta se chama `tabela`, e não `csv`, para ninguém confundir com o módulo
`csv` da biblioteca padrão, que é usado aqui dentro.
"""

from __future__ import annotations

import codecs
import csv
import io
import zlib
from dataclasses import dataclass
from typing import Any

import streamlit as st

from ..base import Corpus, ErroDeFonte, FonteTexto

CODIFICACOES = ("utf-8", "cp1252", "latin-1", "utf-16")

OUTRO = "outro"
SEPARADORES = {
    ",": "Vírgula ( , )",
    ";": "Ponto e vírgula ( ; )",
    "\t": "Tabulação",
    "|": "Barra vertical ( | )",
    OUTRO: "Outro…",
}

ASPAS = {'"': 'Aspas duplas ( " )', "'": "Aspas simples ( ' )", "": "Sem aspas"}

# A prévia lê só o começo do arquivo: o formulário roda a cada clique na tela.
BYTES_PREVIA = 64 * 1024
LINHAS_PREVIA = 5
CARACTERES_PREVIA = 80

# O limite padrão do módulo csv é 131 072 caracteres por campo — um artigo
# longo passa disso. `sys.maxsize` seria o óbvio, mas estoura o `long` do C no
# Windows; 2**31 - 1 é o maior valor aceito em todas as plataformas.
LIMITE_CAMPO = 2**31 - 1


@dataclass(frozen=True)
class PedidoCsv:
    """O que o formulário coletou; volta intacto para `obter_corpus`."""

    arquivo: Any
    codificacao: str
    separador: str
    aspas: str
    cabecalho: bool
    colunas: tuple[str, ...]
    campo_corpus: int
    dimensoes: tuple[int, ...]


class FonteCsv(FonteTexto):
    id = "csv"
    nome = "Arquivo CSV"
    icone = "📊"
    descricao = "Uma tabela: um campo com o texto e outros que servem de filtro."

    def formulario(self) -> PedidoCsv | None:
        arquivo = st.file_uploader(
            "Arquivo CSV",
            type=["csv", "tsv", "txt"],
            key=f"{self.id}_arquivo",
            help=self.descricao,
        )

        col_cod, col_sep, col_aspas = st.columns(3)
        codificacao = col_cod.selectbox(
            "Codificação",
            CODIFICACOES,
            key=f"{self.id}_codificacao",
            help="Arquivos salvos pelo Excel em português costumam ser cp1252.",
        )
        separador = col_sep.selectbox(
            "Separador",
            list(SEPARADORES),
            format_func=SEPARADORES.__getitem__,
            key=f"{self.id}_separador",
        )
        if separador == OUTRO:
            separador = col_sep.text_input(
                "Caractere separador", max_chars=1, key=f"{self.id}_separador_outro"
            )
        aspas = col_aspas.selectbox(
            "Aspas",
            list(ASPAS),
            format_func=ASPAS.__getitem__,
            key=f"{self.id}_aspas",
            help="Campos entre aspas podem conter o separador e quebras de linha.",
        )
        cabecalho = st.checkbox(
            "A primeira linha é o cabeçalho", value=True, key=f"{self.id}_cabecalho"
        )

        if arquivo is None or not separador:
            return None

        try:
            colunas, previa = self._espiar(arquivo, codificacao, separador, aspas, cabecalho)
        except (UnicodeDecodeError, csv.Error) as erro:
            st.error(
                f"Não consegui ler o começo do arquivo com essas opções ({erro}). "
                "Tente outra codificação ou outro separador."
            )
            return None
        if not colunas:
            st.warning("O arquivo parece vazio.")
            return None

        st.caption(f"Prévia — {len(colunas)} colunas")
        st.dataframe(previa, hide_index=True, width="stretch")

        # Keys amarradas ao arquivo E às colunas lidas: trocar de arquivo, de
        # separador ou de codificação muda as colunas, e as marcações recomeçam
        # — senão o seletor guardaria o índice de uma coluna que já não existe.
        assinatura = zlib.crc32("\x1f".join(colunas).encode("utf-8"))
        prefixo = f"{self.id}_{arquivo.file_id}_{assinatura}"
        campo_corpus = st.selectbox(
            "Campo com o texto (corpus)",
            options=range(len(colunas)),
            index=self._provavel_corpus(colunas, previa),
            format_func=colunas.__getitem__,
            key=f"{prefixo}_corpus",
        )

        candidatas = [i for i in range(len(colunas)) if i != campo_corpus]
        dimensoes: list[int] = []
        if candidatas:
            st.markdown("**Dimensões** — campos que servirão de filtro para o corpus")
            grade = st.columns(3)
            for posicao, i in enumerate(candidatas):
                if grade[posicao % 3].checkbox(colunas[i], key=f"{prefixo}_dim_{i}"):
                    dimensoes.append(i)

        return PedidoCsv(
            arquivo=arquivo,
            codificacao=codificacao,
            separador=separador,
            aspas=aspas,
            cabecalho=cabecalho,
            colunas=tuple(colunas),
            campo_corpus=campo_corpus,
            dimensoes=tuple(dimensoes),
        )

    def obter_corpus(self, pedido: PedidoCsv) -> Corpus:
        try:
            texto = pedido.arquivo.getvalue().decode(pedido.codificacao)
        except UnicodeDecodeError as erro:
            raise ErroDeFonte(
                f"O arquivo não está em {pedido.codificacao} (byte inválido na "
                f"posição {erro.start}). Tente outra codificação — arquivos do "
                "Excel em português costumam ser cp1252."
            ) from None

        n = len(pedido.colunas)
        nomes = [pedido.colunas[i] for i in pedido.dimensoes]
        documentos: list[bytes] = []
        valores: list[list[str]] = [[] for _ in pedido.dimensoes]
        sem_texto = 0

        leitor = self._leitor(texto, pedido.separador, pedido.aspas)
        if pedido.cabecalho:
            next(leitor, None)
        try:
            for linha in leitor:
                if not any(campo.strip() for campo in linha):
                    continue
                linha = self._ajustar(linha, n, leitor.line_num)
                corpo = linha[pedido.campo_corpus].strip()
                if not corpo:
                    sem_texto += 1
                    continue
                documentos.append(corpo.encode("utf-8"))
                for coluna, i in zip(valores, pedido.dimensoes):
                    coluna.append(linha[i].strip())
        except csv.Error as erro:
            raise ErroDeFonte(
                f"CSV malformado perto da linha {leitor.line_num}: {erro}. "
                "Confira o separador e as aspas."
            ) from None

        campo = pedido.colunas[pedido.campo_corpus]
        if not documentos:
            raise ErroDeFonte(f"Nenhuma linha tem texto no campo `{campo}`.")

        rotulo = f"{pedido.arquivo.name} ({_milhar(len(documentos))} registros"
        if sem_texto:
            rotulo += f"; {_milhar(sem_texto)} sem texto em `{campo}` ignorados"
        return Corpus(
            documentos=tuple(documentos),
            nome=rotulo + ")",
            origem=self.id,
            dimensoes={nome: tuple(coluna) for nome, coluna in zip(nomes, valores)},
            codificacao=pedido.codificacao,
        )

    # ------------------------------------------------------------------ etapas
    @staticmethod
    def _leitor(texto: str, separador: str, aspas: str) -> Any:
        csv.field_size_limit(LIMITE_CAMPO)
        # O BOM do Excel colaria no nome da primeira coluna; sai aqui, para
        # qualquer codificação escolhida.
        fluxo = io.StringIO(texto.removeprefix("﻿"), newline="")
        if aspas:
            return csv.reader(fluxo, delimiter=separador, quotechar=aspas)
        return csv.reader(fluxo, delimiter=separador, quoting=csv.QUOTE_NONE)

    @classmethod
    def _espiar(
        cls, arquivo: Any, codificacao: str, separador: str, aspas: str, cabecalho: bool
    ) -> tuple[list[str], list[dict[str, str]]]:
        """Nomes das colunas e as primeiras linhas, lendo só o começo do arquivo."""
        with arquivo.getbuffer() as buffer:
            inicio = bytes(buffer[:BYTES_PREVIA])
        # Decodificador incremental: o corte em 64 KB pode cair no meio de um
        # caractere multibyte, e `final=False` guarda esse pedaço em vez de falhar.
        texto = codecs.getincrementaldecoder(codificacao)().decode(inicio, final=False)

        linhas: list[list[str]] = []
        for linha in cls._leitor(texto, separador, aspas):
            if any(campo.strip() for campo in linha):
                linhas.append(linha)
            if len(linhas) > LINHAS_PREVIA:
                break
        if not linhas:
            return [], []

        if cabecalho:
            colunas = _nomes_unicos(linhas.pop(0))
        else:
            colunas = [f"coluna_{i + 1}" for i in range(len(linhas[0]))]
            linhas = linhas[:LINHAS_PREVIA]

        previa = [
            {
                nome: (linha[i] if i < len(linha) else "")[:CARACTERES_PREVIA]
                for i, nome in enumerate(colunas)
            }
            for linha in linhas
        ]
        return colunas, previa

    @staticmethod
    def _provavel_corpus(colunas: list[str], previa: list[dict[str, str]]) -> int:
        """A coluna de textos mais longos na prévia — o palpite inicial do seletor."""
        if not previa:
            return 0
        tamanhos = [sum(len(linha[nome]) for linha in previa) for nome in colunas]
        return tamanhos.index(max(tamanhos))

    @staticmethod
    def _ajustar(linha: list[str], n: int, numero: int) -> list[str]:
        """Completa linha curta; recusa linha com campos a mais.

        Campo a mais quase sempre é separador dentro do texto sem aspas — seguir
        em frente deslocaria as colunas e o "autor" viraria pedaço do artigo.
        Campos extras vazios (separador sobrando no fim da linha) são tolerados.
        """
        if len(linha) > n:
            if any(campo.strip() for campo in linha[n:]):
                raise ErroDeFonte(
                    f"A linha {numero} tem {len(linha)} campos, mas o arquivo tem "
                    f"{n} colunas. Confira o separador e as aspas."
                )
            return linha[:n]
        return linha + [""] * (n - len(linha))


def _nomes_unicos(cabecalho: list[str]) -> list[str]:
    """Nome vazio vira `coluna_N`; nome repetido ganha sufixo `_2`, `_3`…"""
    nomes: list[str] = []
    for i, bruto in enumerate(cabecalho):
        base = bruto.strip() or f"coluna_{i + 1}"
        nome, sufixo = base, 2
        while nome in nomes:
            nome, sufixo = f"{base}_{sufixo}", sufixo + 1
        nomes.append(nome)
    return nomes


def _milhar(numero: int) -> str:
    return f"{numero:,}".replace(",", ".")
