"""O resultado de uma análise: um objeto de dados, só de leitura."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Analise:
    """Tudo que a tela precisa para desenhar, calculado uma única vez.

    Os `Counter` guardam a contagem COMPLETA. Os sliders da tela apenas fatiam
    com `.most_common(n)`, que é barato — nada é reprocessado ao mexer neles.

    O que este objeto deliberadamente NÃO guarda: os tokens e os segmentos. O
    `@st.cache_data` faz pickle do que a função devolve, e a lista de listas de
    tokens de um .txt de 10 MB são centenas de MB indo parar num cache que é
    compartilhado por todas as sessões. Nada na tela usa esses tokens — quem
    precisar deles pede ao `Vetorizador`, que sabe recalculá-los.

    `frozen=True` sinaliza "resultado, não rascunho". Não é imutabilidade real
    (os `Counter` lá dentro continuam mutáveis), mas impede a troca acidental de
    um campo. Cuidado correlato: `cached_property` não funciona em dataclass
    congelada (ela tentaria escrever no `__dict__`), por isso as derivadas
    abaixo são `@property` simples — todas custam O(1) ou uma ordenação já
    barata.
    """

    frequencias: Counter[str]
    ngramas: dict[int, Counter[str]] = field(default_factory=dict)
    total_tokens: int = 0
    total_filtrados: int = 0
    codificacao: str = "utf-8"

    @property
    def palavras_distintas(self) -> int:
        return len(self.frequencias)

    @property
    def vazia(self) -> bool:
        """Nada sobrou depois do filtro — a tela mostra um aviso em vez do gráfico."""
        return not self.frequencias

    def top(self, quantidade: int) -> list[tuple[str, int]]:
        """As `quantidade` palavras mais frequentes, como pares (palavra, contagem)."""
        return self.frequencias.most_common(quantidade)

    def top_sequencias(self, n: int, quantidade: int) -> list[tuple[str, int]]:
        """As sequências de `n` palavras mais frequentes.

        Devolve lista vazia se aquele `n` não foi calculado, em vez de estourar
        KeyError: o slider da tela e o `n_maximo` do processamento podem
        divergir se um for alterado sem o outro.
        """
        return self.ngramas.get(n, Counter()).most_common(quantidade)
