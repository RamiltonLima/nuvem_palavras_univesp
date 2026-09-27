"""Texto colado direto na tela.

O plugin mais curto que existe, e por isso o melhor exemplo de como escrever um:
o formulário é um campo de texto, o corpus é esse texto em UTF-8. Nenhum
arquivo, nenhuma rede.
"""

from __future__ import annotations

import streamlit as st

from ..base import Corpus, ErroDeFonte, FonteTexto


class FonteColar(FonteTexto):
    id = "colar"
    nome = "Colar texto"
    icone = "📝"
    descricao = "Cole ou digite o texto direto aqui, sem precisar de arquivo."

    def formulario(self) -> str | None:
        texto = st.text_area(
            "Texto",
            height=260,
            placeholder="Cole aqui o texto que você quer analisar…",
            key=f"{self.id}_texto",
            help=self.descricao,
        )
        # Devolver None com o campo vazio é o que mantém o botão Processar
        # desabilitado — o app não precisa saber nada sobre este plugin.
        return texto.strip() or None

    def obter_corpus(self, pedido: str) -> Corpus:
        if not pedido.strip():
            raise ErroDeFonte("Não há texto para processar.")
        # O Corpus é sempre bytes; quem já nasce com str encoda aqui e deixa a
        # decodificação por conta do núcleo, como todas as outras fontes.
        return Corpus.unico(
            dados=pedido.encode("utf-8"),
            nome=f"texto colado ({len(pedido)} caracteres)",
            origem=self.id,
        )
