import json
import random
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag

from captura.reportagens.coletar import Caminhos, log


@dataclass
class Artigo:
    """Dados extraídos de uma reportagem."""

    url: str
    autor: str
    data: str
    titulo: str
    tags: list[str]
    categorias: str
    quantidade_comentarios: int | None
    quantidade_imagens_ou_outras: int
    quantidade_links_externos: int
    corpo: str


class RepositorioArtigos:
    """Lê os links pendentes e armazena os artigos no banco SQLite."""

    MAX_TENTATIVAS = 3

    def __init__(self, caminho: Path = Caminhos.banco) -> None:
        self.conexao = sqlite3.connect(caminho, timeout=30)
        self.conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS artigos (
                url TEXT PRIMARY KEY,
                autor TEXT,
                data TEXT,
                titulo TEXT,
                tags TEXT,
                categorias TEXT,
                quantidade_comentarios INTEGER,
                quantidade_imagens_ou_outras INTEGER,
                quantidade_links_externos INTEGER,
                corpo TEXT
            )
            """
        )
        self.conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS falhas_extracao (
                url TEXT PRIMARY KEY,
                tentativas INTEGER NOT NULL DEFAULT 0,
                ultimo_erro TEXT
            )
            """
        )

    def links_pendentes(self) -> list[str]:
        """Retorna os links ainda não extraídos e que não esgotaram as tentativas."""
        consulta = (
            "SELECT l.url FROM links l "
            "LEFT JOIN artigos a ON a.url = l.url "
            "LEFT JOIN falhas_extracao f ON f.url = l.url "
            "WHERE a.url IS NULL AND COALESCE(f.tentativas, 0) < ?"
        )
        return [linha[0] for linha in self.conexao.execute(consulta, (self.MAX_TENTATIVAS,))]

    def registrar_falha(self, url: str, erro: str) -> None:
        """Incrementa o contador de tentativas de um link que falhou."""
        self.conexao.execute(
            """
            INSERT INTO falhas_extracao (url, tentativas, ultimo_erro) VALUES (?, 1, ?)
            ON CONFLICT(url) DO UPDATE SET
                tentativas = tentativas + 1,
                ultimo_erro = excluded.ultimo_erro
            """,
            (url, erro),
        )
        self.conexao.commit()

    def salvar(self, artigo: Artigo) -> None:
        """Insere ou atualiza o artigo; as tags são gravadas como JSON."""
        dados = asdict(artigo)
        dados["tags"] = json.dumps(artigo.tags, ensure_ascii=False)
        colunas = ", ".join(dados)
        marcadores = ", ".join(f":{c}" for c in dados)
        self.conexao.execute(
            f"INSERT OR REPLACE INTO artigos ({colunas}) VALUES ({marcadores})", dados
        )
        self.conexao.execute("DELETE FROM falhas_extracao WHERE url = ?", (artigo.url,))
        self.conexao.commit()

    def fechar(self) -> None:
        """Fecha a conexão com o banco."""
        self.conexao.close()


class ExtratorArtigo:
    """Baixa a página de uma reportagem e extrai seus campos."""

    DOMINIO = "nucleo.jor.br"
    URL_COMENTARIOS = "https://nucleo.jor.br/members/api/comments/counts/"
    CATEGORIA = "Reportagens"
    SELETOR_MIDIAS = "img, iframe, video, audio"

    def __init__(self) -> None:
        self.sessao = requests.Session()
        self.sessao.headers["User-Agent"] = "Mozilla/5.0 (coleta de pesquisa)"

    def extrair(self, url: str) -> Artigo:
        """Retorna o artigo extraído da URL."""
        resposta = self.sessao.get(url, timeout=30)
        resposta.raise_for_status()
        sopa = BeautifulSoup(resposta.text, "html.parser")
        principal = sopa.select_one("article.post")
        if principal is None:
            raise ValueError("bloco principal 'article.post' não encontrado")
        corpo = principal.select_one(".post-content")
        if corpo is None:
            raise ValueError("corpo '.post-content' não encontrado")

        return Artigo(
            url=url,
            autor=self.autores(principal),
            data=self.meta(sopa, "article:published_time")
            or self.atributo(principal.select_one("time.post-date"), "datetime"),
            titulo=self.texto(principal.select_one(".post-title")) or self.meta(sopa, "og:title"),
            tags=[m["content"] for m in sopa.select('meta[property="article:tag"]')],
            categorias=self.CATEGORIA,
            quantidade_comentarios=self.contar_comentarios(principal),
            quantidade_imagens_ou_outras=self.contar_midias(corpo),
            quantidade_links_externos=self.contar_links_externos(corpo),
            corpo=self.texto_corpo(corpo),
        )

    @staticmethod
    def autores(principal: Tag) -> str:
        """Retorna o(s) autor(es); posts com múltiplos autores só têm o nome no alt da imagem."""
        nome = principal.select_one(".post-author span")
        if nome is not None:
            return nome.get_text(strip=True)
        avatares = principal.select(".post-authors-avatar img[alt]")
        if avatares:
            return ", ".join(a["alt"] for a in avatares)
        return ""

    def contar_comentarios(self, principal: Tag) -> int | None:
        """Consulta a API de comentários do Ghost pelo id do post."""
        marcador = principal.select_one("[data-ghost-comment-count]")
        if marcador is None:
            return None
        post_id = marcador["data-ghost-comment-count"]
        resposta = self.sessao.get(self.URL_COMENTARIOS, params={"ids": post_id}, timeout=30)
        resposta.raise_for_status()
        return resposta.json().get(post_id, 0)

    def contar_midias(self, corpo: Tag) -> int:
        """Conta cartões do editor (imagem, embed, galeria...) e mídias soltas."""
        cartoes = corpo.select(".kg-card")
        soltas = [m for m in corpo.select(self.SELETOR_MIDIAS) if not m.find_parent(class_="kg-card")]
        return len(cartoes) + len(soltas)

    def contar_links_externos(self, corpo: Tag) -> int:
        """Conta links do corpo que apontam para fora do domínio do jornal."""
        total = 0
        for link in corpo.select("a[href]"):
            host = urlparse(link["href"]).netloc.lower()
            if host and not host.endswith(self.DOMINIO):
                total += 1
        return total

    @staticmethod
    def texto_corpo(corpo: Tag) -> str:
        """Retorna o texto do corpo do artigo."""
        return corpo.get_text("\n", strip=True)

    @staticmethod
    def texto(elemento: Tag | None) -> str:
        """Retorna o texto limpo do elemento ou vazio."""
        return elemento.get_text(strip=True) if elemento else ""

    @staticmethod
    def atributo(elemento: Tag | None, nome: str) -> str:
        """Retorna o atributo do elemento ou vazio."""
        return str(elemento.get(nome, "")) if elemento else ""

    @staticmethod
    def meta(sopa: BeautifulSoup, propriedade: str) -> str:
        """Retorna o conteúdo de uma meta tag pela propriedade."""
        elemento = sopa.select_one(f'meta[property="{propriedade}"]')
        return str(elemento.get("content", "")) if elemento else ""


class Extracao:
    """Percorre os links pendentes extraindo e salvando cada artigo."""

    def __init__(
        self,
        repositorio: RepositorioArtigos,
        extrator: ExtratorArtigo,
        espera_min: float = 2.0,
        espera_max: float = 5.0,
    ) -> None:
        self.repositorio = repositorio
        self.extrator = extrator
        self.espera_min = espera_min
        self.espera_max = espera_max

    def aguardar(self) -> None:
        """Pausa por um tempo aleatório entre a espera mínima e a máxima."""
        segundos = random.uniform(self.espera_min, self.espera_max)
        log(f"Aguardando {segundos:.1f}s...")
        time.sleep(segundos)

    def executar(self) -> None:
        """Extrai todos os artigos pendentes."""
        pendentes = self.repositorio.links_pendentes()
        log(f"Início da extração: {len(pendentes)} links pendentes")
        falhas = 0
        for posicao, url in enumerate(pendentes, start=1):
            log(f"[{posicao}/{len(pendentes)}] {url}")
            try:
                artigo = self.extrator.extrair(url)
                self.repositorio.salvar(artigo)
                log(
                    f"  OK: '{artigo.titulo}' | {artigo.autor} | {artigo.data} | "
                    f"comentários={artigo.quantidade_comentarios} "
                    f"mídias={artigo.quantidade_imagens_ou_outras} "
                    f"links externos={artigo.quantidade_links_externos}"
                )
            except Exception as erro:
                falhas += 1
                self.repositorio.registrar_falha(url, str(erro))
                log(f"  ERRO: {erro}")
            if posicao < len(pendentes):
                self.aguardar()
        log(f"Fim da extração: {len(pendentes) - falhas} salvos, {falhas} falhas")


if __name__ == "__main__":
    repositorio = RepositorioArtigos()
    try:
        Extracao(repositorio, ExtratorArtigo()).executar()
    except KeyboardInterrupt:
        log("Interrompido pelo usuário; artigos já extraídos foram mantidos")
    finally:
        repositorio.fechar()
