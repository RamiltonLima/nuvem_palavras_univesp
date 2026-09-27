"""O núcleo do app: bytes -> texto -> segmentos -> tokens -> contagens.

Nada aqui importa streamlit nem pandas, e isso é a regra mais importante do
projeto. É o que faz o pipeline rodar igual num script, num notebook e no app —
e o que permite trocar a camada de tela um dia sem encostar nesta pasta.
"""

from __future__ import annotations

import codecs
import re
from collections import Counter
from collections.abc import Hashable, Iterable, Mapping
from functools import cached_property
from typing import TypeVar

from .analise import Analise
from .stopwords import normalizar, sem_acento

# Ordem de tentativa na decodificação. `latin-1` fica fora da lista porque nunca
# levanta erro (aceita qualquer byte), então ele é o fallback explícito no final.
CODIFICACOES = ("utf-8-sig", "utf-8", "cp1252")

# Fronteiras de frase. Quebrar o texto aqui impede que a última palavra de uma
# frase forme um par com a primeira palavra da frase seguinte.
SEPARADOR_SEGMENTO = re.compile(r"[.!?;:\n\r]+")

# `[^\W\d_]` = "caractere de palavra que não é dígito nem underscore", ou seja,
# qualquer LETRA Unicode — inclusive as acentuadas. É o que diferencia isto de
# um `\w+` (que pegaria números) ou de um `.split()` (que colaria a pontuação).
# O sufixo opcional preserva hífen e apóstrofo internos: "guarda-chuva", "d'água".
TOKEN = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")

N_MINIMO = 2
N_MAXIMO = 10

K = TypeVar("K", bound=Hashable)


class Vetorizador:
    """Recebe o corpus em bytes e sabe transformá-lo em contagens.

    A divisão interna segue uma regra só: o que NÃO depende das stop words
    (decodificar, segmentar, tokenizar) é `cached_property` e vale para qualquer
    configuração de limpeza; o que DEPENDE fica em `analisar()`, que pode ser
    chamado várias vezes na mesma instância — para comparar duas listas de stop
    words, por exemplo — sem re-tokenizar uma linha sequer.

    É por isso que as stop words entram no método e não no `__init__`: se
    entrassem no construtor, cada mudança de parâmetro exigiria um objeto novo,
    e a classe não estaria ganhando nada sobre as funções soltas que existiam
    antes dela.

    Sem `__slots__` de propósito: `cached_property` grava o valor calculado no
    `__dict__` da instância, e os slots tirariam justamente esse `__dict__`.

    >>> Vetorizador.de_texto("Céu azul. Céu azul.").analisar().frequencias
    Counter({'céu': 2, 'azul': 2})
    """

    def __init__(
        self, dados: bytes, *, codificacoes: tuple[str, ...] = CODIFICACOES
    ) -> None:
        if not isinstance(dados, (bytes, bytearray)):
            raise TypeError(
                "Vetorizador recebe o corpus em bytes (é o que os plugins "
                "entregam). Se você já tem uma str, use Vetorizador.de_texto()."
            )
        self._dados = bytes(dados)
        self._codificacoes = codificacoes

    @classmethod
    def de_texto(cls, texto: str) -> Vetorizador:
        """Atalho para script e notebook: partir de uma str em vez de bytes."""
        return cls(texto.encode("utf-8"))

    def __len__(self) -> int:
        return self.total_tokens

    def __repr__(self) -> str:
        return (
            f"<Vetorizador {len(self._dados)} bytes, {self.codificacao}, "
            f"{len(self.segmentos)} segmentos>"
        )

    # ------------------------------------------------------------------ etapas
    @cached_property
    def _decodificado(self) -> tuple[str, str]:
        """Devolve (texto, codec que funcionou).

        Evita a dependência de um detector de encoding: na prática um .txt
        gerado no Windows é utf-8 (com ou sem BOM) ou cp1252, e o latin-1 aceita
        qualquer byte — então o app nunca quebra por causa de codificação, no
        pior caso troca um caractere estranho por outro.
        """
        for codec in self._codificacoes:
            try:
                texto = self._dados.decode(codec)
            except UnicodeDecodeError:
                continue
            # `utf-8-sig` decodifica arquivo sem BOM também (ele só remove o BOM
            # quando existe), então acertar aqui é o que impede a tela de dizer
            # "com BOM" para todo arquivo utf-8 comum.
            if codec == "utf-8-sig" and not self._dados.startswith(codecs.BOM_UTF8):
                return texto, "utf-8"
            return texto, codec
        return self._dados.decode("latin-1", errors="replace"), "latin-1"

    @property
    def texto(self) -> str:
        return self._decodificado[0]

    @property
    def codificacao(self) -> str:
        """Qual codec funcionou. Vale mostrar na tela: explica acento estranho."""
        return self._decodificado[1]

    @cached_property
    def segmentos(self) -> list[str]:
        """Trechos delimitados por pontuação forte ou quebra de linha.

        Na prática, "uma frase". Existem para servir de fronteira aos n-gramas.
        """
        return [
            trecho for trecho in SEPARADOR_SEGMENTO.split(self.texto) if trecho.strip()
        ]

    @cached_property
    def tokens_por_segmento(self) -> list[list[str]]:
        """As palavras de cada segmento, em minúsculas e com os acentos preservados.

        Guardado por segmento, e não achatado numa lista só, porque a fronteira
        de frase é o que impede a última palavra de uma frase de formar par com
        a primeira da seguinte lá na contagem de sequências.
        """
        return [TOKEN.findall(segmento.lower()) for segmento in self.segmentos]

    @cached_property
    def total_tokens(self) -> int:
        """Quantas palavras o texto tem ANTES de qualquer filtro."""
        return sum(len(tokens) for tokens in self.tokens_por_segmento)

    # ----------------------------------------------------------------- análise
    def analisar(
        self,
        stopwords: Iterable[str] = (),
        tamanho_minimo: int = 3,
        n_maximo: int = N_MAXIMO,
    ) -> Analise:
        """Aplica a limpeza e devolve TODAS as contagens de uma vez.

        Barato de chamar de novo com outros parâmetros: as etapas caras acima já
        estão em cache na instância.
        """
        limpos = self._filtrar(normalizar(stopwords), tamanho_minimo)
        frequencias = self._contar(limpos)

        # Calcular todos os `n` de uma vez custa pouco e é o que deixa o slider
        # da tela instantâneo: mexer nele só re-fatia um Counter que já existe.
        ngramas = {
            n: self._contar_ngramas(limpos, n) for n in range(N_MINIMO, n_maximo + 1)
        }

        return Analise(
            frequencias=frequencias,
            ngramas=ngramas,
            total_tokens=self.total_tokens,
            total_filtrados=sum(frequencias.values()),
            codificacao=self.codificacao,
        )

    def frequencias(
        self, stopwords: Iterable[str] = (), tamanho_minimo: int = 3
    ) -> Counter[str]:
        """Só a contagem de palavras, sem n-gramas — o que o CSV bruto precisa por grupo."""
        return self._contar(self._filtrar(normalizar(stopwords), tamanho_minimo))

    @staticmethod
    def _contar(segmentos: Iterable[list[str]]) -> Counter[str]:
        contagem: Counter[str] = Counter()
        for tokens in segmentos:
            contagem.update(tokens)
        return contagem

    def _filtrar(
        self, stopwords: frozenset[str], tamanho_minimo: int
    ) -> list[list[str]]:
        """Descarta o que é curto demais e o que está nas stop words.

        Continua devolvendo listas por segmento — perder o agrupamento aqui
        destruiria a fronteira de frase antes dos n-gramas. Segmentos que ficam
        vazios após o filtro somem, porque não formam sequência nenhuma.
        """
        sobreviventes = (
            [
                token
                for token in tokens
                if len(token) >= tamanho_minimo and sem_acento(token) not in stopwords
            ]
            for tokens in self.tokens_por_segmento
        )
        return [tokens for tokens in sobreviventes if tokens]

    @staticmethod
    def _contar_ngramas(segmentos: Iterable[list[str]], n: int) -> Counter[str]:
        """Conta sequências de `n` palavras adjacentes DENTRO de cada segmento.

        `zip(*(tokens[i:] for i in range(n)))` é a janela deslizante: para n=2
        ele casa a lista com ela mesma deslocada de uma posição, produzindo os
        pares; para n=3, três listas deslocadas, e assim por diante.
        """
        contagem: Counter[str] = Counter()
        for tokens in segmentos:
            if len(tokens) < n:
                continue
            contagem.update(
                " ".join(grupo) for grupo in zip(*(tokens[i:] for i in range(n)))
            )
        return contagem


def frequencias_por_grupo(
    grupos: Mapping[K, bytes], stopwords: Iterable[str] = (), tamanho_minimo: int = 3
) -> dict[K, Counter[str]]:
    """A contagem de palavras de cada grupo, com a mesma limpeza de `analisar()`.

    Existe à parte de `Vetorizador.frequencias` para normalizar as stop words
    uma vez só: com milhares de grupos, renormalizar a lista em cada um custaria
    mais do que contar as palavras.
    """
    stop = normalizar(stopwords)
    return {
        chave: Vetorizador._contar(Vetorizador(dados)._filtrar(stop, tamanho_minimo))
        for chave, dados in grupos.items()
    }
