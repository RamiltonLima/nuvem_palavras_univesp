"""A fonte mais básica: um arquivo .txt enviado pelo navegador."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ..base import Corpus, ErroDeFonte, FonteTexto


class FonteTxt(FonteTexto):
    id = "txt"
    nome = "Arquivo .txt"
    icone = "📄"
    descricao = "Um arquivo de texto puro. O limite de upload está em .streamlit/config.toml."

    EXTENSOES = ("txt",)

    # A anotação é `Any` em vez de `UploadedFile` de propósito: o tipo real mora
    # em streamlit.runtime.uploaded_file_manager, um módulo interno que já mudou
    # de lugar entre versões. Não vale amarrar o plugin a ele só por uma anotação.
    def formulario(self) -> Any | None:
        # O uploader devolve o mesmo objeto em toda re-execução enquanto o
        # arquivo estiver na tela. Por isso dá para devolvê-lo cru como "pedido"
        # e só ler os bytes depois, no clique em Processar.
        return st.file_uploader(
            "Arquivo de texto",
            type=list(self.EXTENSOES),
            key=f"{self.id}_arquivo",
            help="Por enquanto apenas .txt. Para PDF ou DOCX, escreva um plugin novo.",
        )

    def obter_corpus(self, pedido: Any) -> Corpus:
        dados = pedido.getvalue()
        if not dados.strip():
            raise ErroDeFonte(f"O arquivo `{pedido.name}` está vazio.")
        return Corpus.unico(dados=dados, nome=pedido.name, origem=self.id)
