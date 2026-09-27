import random
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class Caminhos:
    """Resolve os caminhos utilizados pela aplicação."""

    raiz = Path(__file__).resolve().parent
    dados = raiz / "data"
    banco = dados / "reportagens.db"


def log(mensagem: str) -> None:
    """Imprime uma mensagem na tela com data e hora."""
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {mensagem}", flush=True)


class RepositorioLinks:
    """Armazena os links coletados no banco SQLite."""

    def __init__(self, caminho: Path = Caminhos.banco) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self.conexao = sqlite3.connect(caminho)
        self.conexao.execute("CREATE TABLE IF NOT EXISTS links (url TEXT PRIMARY KEY)")

    def salvar(self, links: list[str]) -> int:
        """Insere os links ignorando repetidos e retorna quantos eram novos."""
        antes = self.conexao.total_changes
        self.conexao.executemany(
            "INSERT OR IGNORE INTO links (url) VALUES (?)", [(url,) for url in links]
        )
        self.conexao.commit()
        return self.conexao.total_changes - antes

    def total(self) -> int:
        """Retorna a quantidade de links armazenados."""
        return self.conexao.execute("SELECT COUNT(*) FROM links").fetchone()[0]

    def fechar(self) -> None:
        """Fecha a conexão com o banco."""
        self.conexao.close()


class ColetorLinks:
    """Coleta os links dos cards da seção Reportagens percorrendo a paginação."""

    URL = "https://nucleo.jor.br/reportagem/"
    SELETOR_CARD = ".tag-posts-list article.card-post a.card-link"

    def __init__(
        self,
        repositorio: RepositorioLinks,
        espera_min: float = 3.0,
        espera_max: float = 10.0,
    ) -> None:
        self.repositorio = repositorio
        self.espera_min = espera_min
        self.espera_max = espera_max
        self.sessao = requests.Session()
        self.sessao.headers["User-Agent"] = "Mozilla/5.0 (coleta de pesquisa)"

    def url_pagina(self, numero: int) -> str:
        """Monta a URL da página de listagem."""
        return self.URL if numero == 1 else f"{self.URL}page/{numero}/"

    def aguardar(self) -> None:
        """Pausa por um tempo aleatório entre a espera mínima e a máxima."""
        segundos = random.uniform(self.espera_min, self.espera_max)
        log(f"Aguardando {segundos:.1f}s...")
        time.sleep(segundos)

    def coletar_pagina(self, numero: int) -> list[str] | None:
        """Retorna os links da página ou None se ela não existir."""
        url = self.url_pagina(numero)
        log(f"Página {numero}: GET {url}")
        resposta = self.sessao.get(url, timeout=30)
        if resposta.status_code == 404:
            log(f"Página {numero}: 404, fim da paginação")
            return None
        resposta.raise_for_status()
        sopa = BeautifulSoup(resposta.text, "html.parser")
        return [urljoin(self.URL, a["href"]) for a in sopa.select(self.SELETOR_CARD)]

    def executar(self, pagina_inicial: int = 1) -> None:
        """Percorre as páginas até acabar, salvando os links a cada página."""
        log("Início da coleta")
        numero = pagina_inicial
        while True:
            links = self.coletar_pagina(numero)
            if not links:
                if links is not None:
                    log(f"Página {numero}: nenhum card encontrado, encerrando")
                break
            novos = self.repositorio.salvar(links)
            log(
                f"Página {numero}: {len(links)} cards, {novos} novos "
                f"(total no banco: {self.repositorio.total()})"
            )
            numero += 1
            self.aguardar()
        log(f"Fim da coleta: {self.repositorio.total()} links em {Caminhos.banco}")


if __name__ == "__main__":
    repositorio = RepositorioLinks()
    try:
        ColetorLinks(repositorio).executar()
    except KeyboardInterrupt:
        log("Interrompido pelo usuário; links já coletados foram mantidos")
    finally:
        repositorio.fechar()
