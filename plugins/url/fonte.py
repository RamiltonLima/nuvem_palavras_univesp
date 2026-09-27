"""Uma página da web: baixa o HTML, confirma que é HTML e limpa as tags.

Este é o plugin que justifica a separação entre as duas interfaces do contrato.
O formulário roda a cada clique em qualquer widget da tela; se ele baixasse a
página, mexer num slider dispararia um GET. Aqui o formulário só coleta o
endereço, e a rede só é tocada em `obter_corpus`, no clique em Processar.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import requests
import streamlit as st

from ..base import Corpus, ErroDeFonte, FonteTexto
from .extrator import extrair_texto

TEMPO_LIMITE = 15  # segundos, por etapa (conexão e leitura)

# Teto coerente com o maxUploadSize=10 do .streamlit/config.toml: uma página de
# 5 MB de HTML já é gigante, e o processamento aqui é síncrono — sem o teto,
# um link para um arquivo enorme prenderia a tela.
LIMITE_BYTES = 5 * 1024 * 1024

TIPOS_ACEITOS = ("text/html", "application/xhtml")

# Alguns sites recusam requisição sem User-Agent. Identificar-se é mais honesto
# do que fingir ser um navegador.
CABECALHOS = {
    "User-Agent": "NuvemDePalavras/1.0 (app educacional; +https://streamlit.io)",
    "Accept": "text/html,application/xhtml+xml",
}


class FonteUrl(FonteTexto):
    id = "url"
    nome = "Página da web"
    icone = "🌐"
    descricao = "Baixa uma página, descarta as tags e usa só o texto entre elas."

    def formulario(self) -> str | None:
        endereco = st.text_input(
            "Endereço da página",
            placeholder="https://pt.wikipedia.org/wiki/Mobilidade_urbana",
            key=f"{self.id}_endereco",
            help=self.descricao,
        )
        st.caption(
            "O texto sai do HTML como está: menus e rodapés da página entram na "
            "contagem junto com o conteúdo. Use as stop words para limpar o que sobrar."
        )
        return endereco.strip() or None

    def obter_corpus(self, pedido: str) -> Corpus:
        url = self._validar(pedido)

        try:
            resposta = requests.get(
                url, timeout=TEMPO_LIMITE, headers=CABECALHOS, stream=True
            )
            resposta.raise_for_status()
        except requests.exceptions.Timeout:
            raise ErroDeFonte(
                f"A página demorou mais de {TEMPO_LIMITE}s para responder."
            ) from None
        except requests.exceptions.HTTPError as erro:
            raise ErroDeFonte(
                f"O servidor respondeu {resposta.status_code}. "
                f"Confira se o endereço está certo e se a página é pública."
            ) from erro
        except requests.exceptions.RequestException as erro:
            raise ErroDeFonte(f"Não consegui acessar a página: {erro}") from erro

        with resposta:
            self._conferir_que_e_html(resposta)
            html = self._ler_com_limite(resposta)

        texto = extrair_texto(html)
        if not texto.strip():
            raise ErroDeFonte(
                "A página baixou, mas não sobrou texto depois de tirar as tags. "
                "É provável que o conteúdo dela seja montado por JavaScript — "
                "nesse caso, copie o texto e use a fonte 📝 Colar texto."
            )

        return Corpus.unico(dados=texto.encode("utf-8"), nome=url, origem=self.id)

    # ------------------------------------------------------------------ etapas
    @staticmethod
    def _validar(endereco: str) -> str:
        """Só http e https, e com host.

        O app vai para a nuvem e passa a baixar qualquer endereço que um
        visitante digitar. Recusar os outros esquemas aqui é o que impede um
        `file:///etc/passwd` de virar nuvem de palavras.
        """
        # Digitar "exemplo.com" é o normal; completar o esquema evita um erro
        # que o usuário não entenderia.
        if "://" not in endereco:
            endereco = f"https://{endereco}"

        partes = urlsplit(endereco)
        if partes.scheme not in ("http", "https"):
            raise ErroDeFonte(
                f"Endereço `{partes.scheme}:` não é aceito — use http ou https."
            )
        if not partes.netloc:
            raise ErroDeFonte(f"`{endereco}` não parece um endereço válido.")
        return endereco

    @staticmethod
    def _conferir_que_e_html(resposta: requests.Response) -> None:
        """Recusa PDF, imagem e JSON antes de gastar tempo lendo o corpo."""
        tipo = resposta.headers.get("Content-Type", "").lower()
        if not any(aceito in tipo for aceito in TIPOS_ACEITOS):
            legivel = tipo.split(";")[0].strip() or "desconhecido"
            raise ErroDeFonte(
                f"O endereço devolveu `{legivel}`, e esta fonte só lê HTML. "
                f"Para outros formatos, baixe o arquivo e use outra fonte."
            )

    @staticmethod
    def _ler_com_limite(resposta: requests.Response) -> str:
        """Lê o corpo em pedaços, abortando se passar do teto.

        Ler em pedaços, e não com `resposta.text` direto, é o que garante que o
        limite valha mesmo quando o servidor não manda `Content-Length` (ou
        manda um valor mentiroso).
        """
        blocos: list[bytes] = []
        total = 0
        for bloco in resposta.iter_content(chunk_size=64 * 1024):
            total += len(bloco)
            if total > LIMITE_BYTES:
                raise ErroDeFonte(
                    f"A página passou de {LIMITE_BYTES // (1024 * 1024)} MB e o "
                    f"download foi interrompido."
                )
            blocos.append(bloco)

        bruto = b"".join(blocos)
        return bruto.decode(FonteUrl._codec(resposta), errors="replace")

    @staticmethod
    def _codec(resposta: requests.Response) -> str:
        """Descobre a codificação da página. Decodificar é responsabilidade daqui.

        O núcleo decodifica por tentativa e erro, o que é certo para um arquivo
        solto — mas aqui existe informação melhor: o cabeçalho HTTP. Por isso
        esta fonte entrega o texto já resolvido.

        A pegadinha: quando o `Content-Type` não declara charset, o `requests`
        assume `ISO-8859-1` (é o que a norma antiga do HTTP manda), e aí toda
        página em português sem charset viraria "informaÃ§Ã£o". Então só
        confiamos no `resposta.encoding` quando o charset veio EXPLÍCITO;
        senão, deixamos o detector (`apparent_encoding`) decidir.
        """
        cabecalho = resposta.headers.get("Content-Type", "").lower()
        if "charset=" in cabecalho and resposta.encoding:
            return resposta.encoding
        return resposta.apparent_encoding or "utf-8"
