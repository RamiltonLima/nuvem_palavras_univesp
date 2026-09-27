"""Os documentos do corpus e suas dimensões, prontos para filtrar e agrupar.

A saída desta camada é a mesma entrada que o `core` sempre recebeu: `bytes`. Os
documentos escolhidos pelos filtros são unidos com uma quebra de linha — que já
é fronteira de segmento no núcleo, então uma sequência de palavras nunca
atravessa de um registro para o outro. É isso que deixa o `core` sem saber que
dimensões existem.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from functools import cached_property

from .filtros import Filtro
from .tipos import Deteccao, TipoDimensao, converter, detectar

SEPARADOR_DOCUMENTOS = b"\n"


class Dimensao:
    """Uma coluna: os valores crus e, sob demanda, convertidos para cada tipo.

    A conversão fica em cache por tipo porque o usuário pode trocar na tela o
    tipo detectado — e voltar — sem que a coluna seja relida a cada clique.
    """

    def __init__(self, nome: str, brutos: Sequence[str]) -> None:
        self.nome = nome
        self.brutos = tuple(brutos)
        self._convertidos: dict[TipoDimensao, tuple] = {}
        self._deteccoes: dict[TipoDimensao, Deteccao] = {}

    def __repr__(self) -> str:
        return f"<Dimensao {self.nome!r} {self.deteccao.descricao}, {len(self.brutos)} valores>"

    @cached_property
    def deteccao(self) -> Deteccao:
        """O tipo que a amostragem sugere — o padrão do seletor na tela."""
        return detectar(self.brutos)

    def deteccao_para(self, tipo: TipoDimensao) -> Deteccao:
        if tipo is self.deteccao.tipo:
            return self.deteccao
        if tipo not in self._deteccoes:
            self._deteccoes[tipo] = detectar(self.brutos, forcar=tipo)
        return self._deteccoes[tipo]

    def valores(self, tipo: TipoDimensao) -> tuple:
        """Um valor convertido por documento, na mesma ordem dos documentos."""
        if tipo not in self._convertidos:
            self._convertidos[tipo] = converter(self.brutos, self.deteccao_para(tipo))
        return self._convertidos[tipo]

    def distintos(self) -> list[tuple[str, int]]:
        """Valores de texto com a contagem, do mais frequente para o menos."""
        return Counter(self.valores(TipoDimensao.TEXTO)).most_common()

    def extremos(self, tipo: TipoDimensao) -> tuple[float | date, float | date] | None:
        """(mínimo, máximo) dos valores lidos, ou `None` se nenhum foi lido."""
        presentes = [valor for valor in self.valores(tipo) if valor is not None]
        return (min(presentes), max(presentes)) if presentes else None

    def vazios(self, tipo: TipoDimensao) -> int:
        """Quantos documentos não têm valor legível neste tipo."""
        return sum(valor is None for valor in self.valores(tipo))


class Colecao:
    """Documentos em bytes + dimensões. Sem dimensões é a "dimensão única"."""

    def __init__(
        self, documentos: Sequence[bytes], colunas: Mapping[str, Sequence[str]]
    ) -> None:
        self.documentos = tuple(documentos)
        self.dimensoes = {nome: Dimensao(nome, valores) for nome, valores in colunas.items()}

    def __len__(self) -> int:
        return len(self.documentos)

    def __repr__(self) -> str:
        return f"<Colecao {len(self)} documentos, dimensões {self.nomes}>"

    @property
    def nomes(self) -> list[str]:
        return list(self.dimensoes)

    @property
    def tem_dimensoes(self) -> bool:
        return bool(self.dimensoes)

    def todos(self) -> tuple[int, ...]:
        return tuple(range(len(self)))

    def filtrar(
        self, filtros: Mapping[str, tuple[TipoDimensao, Filtro]]
    ) -> tuple[int, ...]:
        """Índices dos documentos aceitos por TODOS os filtros (E lógico)."""
        ativos = [
            (self.dimensoes[nome].valores(tipo), filtro)
            for nome, (tipo, filtro) in filtros.items()
        ]
        if not ativos:
            return self.todos()
        return tuple(
            i
            for i in range(len(self))
            if all(filtro.aceita(valores[i]) for valores, filtro in ativos)
        )

    def juntar(self, indices: Sequence[int]) -> bytes:
        """Os documentos escolhidos num corpus só, separados por quebra de linha.

        Um documento sozinho volta intacto: é o caso das fontes de texto único,
        e não mexer nos bytes preserva a detecção de codificação do núcleo.
        """
        if len(indices) == 1:
            return self.documentos[indices[0]]
        return SEPARADOR_DOCUMENTOS.join(self.documentos[i] for i in indices)

    def agrupar(self, indices: Sequence[int]) -> dict[tuple[str, ...], bytes]:
        """Os documentos escolhidos, unidos por combinação de valores das dimensões.

        A chave usa os valores crus (como vieram do arquivo), que é o que vai
        para o CSV bruto. Sem dimensões, tudo cai num grupo só, de chave `()`.
        """
        colunas = [dimensao.brutos for dimensao in self.dimensoes.values()]
        grupos: dict[tuple[str, ...], list[int]] = {}
        for i in indices:
            grupos.setdefault(tuple(coluna[i] for coluna in colunas), []).append(i)
        return {chave: self.juntar(membros) for chave, membros in grupos.items()}
