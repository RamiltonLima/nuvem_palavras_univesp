"""Tira as tags de um HTML e devolve só o texto que estava entre elas.

Usa o `html.parser` da biblioteca padrão em vez do BeautifulSoup: são ~40 linhas,
dependência zero, e o comportamento fica explícito no código em vez de escondido
num `get_text()`.

O que ele resolve, e que um `re.sub(r"<[^>]+>", "", html)` não resolveria:

- **descarta o conteúdo de `<script>` e `<style>`** — sem isso a nuvem enche de
  `function`, `var`, `px`, `rgba`;
- **transforma bloco em quebra de linha** — e isso não é cosmético: `\\n` é uma
  das fronteiras de `core.vetorizador.SEPARADOR_SEGMENTO`, então cada parágrafo
  vira um segmento e as sequências de palavras não atravessam de um bloco para
  o outro.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

# O conteúdo destas tags é descartado inteiro: é código ou metadado, não texto.
IGNORADAS = frozenset(
    {"script", "style", "noscript", "head", "template", "svg", "canvas", "iframe"}
)

# Estas encerram um bloco visual, então viram quebra de linha — que é o que faz
# o núcleo tratá-las como fim de frase.
QUEBRAM = frozenset(
    {
        "p", "br", "div", "section", "article", "header", "footer", "main",
        "aside", "nav", "li", "ul", "ol", "tr", "td", "th", "table",
        "blockquote", "pre", "figcaption", "hr",
        "h1", "h2", "h3", "h4", "h5", "h6",
    }
)

# Colapsa espaços e tabs repetidos SEM tocar nas quebras de linha (por isso o
# `[^\S\n]`: "espaço em branco que não é \n").
_ESPACOS = re.compile(r"[^\S\n]+")
_LINHAS_VAZIAS = re.compile(r"\n\s*\n+")


class _ExtratorDeTexto(HTMLParser):
    """Acumula o texto visível, pulando o conteúdo das tags ignoradas."""

    def __init__(self) -> None:
        # convert_charrefs=True (o padrão) já resolve &amp;, &nbsp; e afins
        # antes de chegar no handle_data.
        super().__init__(convert_charrefs=True)
        self._partes: list[str] = []
        # Contador, e não booleano, porque HTML de verdade tem tag aninhada e
        # tag mal fechada. Enquanto for > 0, tudo que chega é descartado.
        self._profundidade_ignorada = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in IGNORADAS:
            self._profundidade_ignorada += 1
        elif tag in QUEBRAM:
            self._partes.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in IGNORADAS:
            # max(0, ...) para uma tag de fechamento órfã não deixar o contador
            # negativo e engolir o resto da página.
            self._profundidade_ignorada = max(0, self._profundidade_ignorada - 1)
        elif tag in QUEBRAM:
            self._partes.append("\n")

    def handle_data(self, data: str) -> None:
        if self._profundidade_ignorada == 0:
            self._partes.append(data)

    def texto(self) -> str:
        bruto = "".join(self._partes)
        bruto = _ESPACOS.sub(" ", bruto)
        bruto = _LINHAS_VAZIAS.sub("\n", bruto)
        return bruto.strip()


def extrair_texto(html: str) -> str:
    """HTML -> texto puro, com um parágrafo por linha."""
    extrator = _ExtratorDeTexto()
    # `convert_charrefs` só descarrega o último pedaço de texto no `close()`.
    extrator.feed(html)
    extrator.close()
    return extrator.texto()
