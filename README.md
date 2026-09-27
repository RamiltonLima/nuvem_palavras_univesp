# ☁️ Nuvem de Palavras

Aplicação web para analisar a frequência de palavras em textos e visualizar os resultados em uma nuvem de palavras, tabela de frequência e gráficos de n-gramas.

Projeto Integrador II — UNIVESP.

Feito em **Python + Streamlit + Apache ECharts**.

## O que faz

* Nuvem de palavras interativa.
* Tabela com frequência e percentual das palavras.
* N-gramas de 2 a 10 palavras.
* Stop words editáveis.
* Filtro por dimensões quando o texto vem de CSV.
* Exportação dos resultados em CSV.
* Quatro formas de entrada de texto:

  * `.txt`
  * texto colado
  * página da web
  * CSV

No CSV, algumas colunas podem ser usadas como dimensões, por exemplo:

`autor`, `cidade`, `data`, `categoria`.

Assim é possível filtrar o corpus antes da análise.

## Requisitos

* Python 3.13 ou 3.14
* Aproximadamente 350 MB livres

## Instalação

```bash
git clone https://github.com/RamiltonLima/nuvem_palavras.git
cd nuvem_palavras
```

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

## Executar

```bash
streamlit run app.py
```

Depois acesse:

`http://localhost:8501`

Para parar, `Ctrl+C` no terminal.

## Como usar

1. Entre em **⚙️ Preferências**.
2. Escolha de onde vem o texto.
3. Configure as opções necessárias.
4. Clique em **Processar**.
5. Veja os resultados em **☁️ Palavras**.

O processamento acontece em memória. Nada é salvo em disco.

## Fontes

| Fonte         | Uso                            |
| ------------- | ------------------------------ |
| 📄 `.txt`     | Arquivo de texto, até 10 MB    |
| 📝 Texto      | Digitação ou texto colado      |
| 🌐 Página web | Extrai o texto da página       |
| 📊 CSV        | Texto + dimensões para filtros |

A fonte web pega o texto disponível no HTML, então menus, rodapés e outros textos da página também podem aparecer. Nesse caso, eles podem ser colocados nas stop words.

## Estrutura

```text
plugins/       fontes de texto
dimensoes/     filtros do CSV
core/          processamento
visual/        gráficos e tabelas

app.py         aplicação
config.py      configurações
stopwords.txt  stop words padrão
```

A ideia é manter as partes separadas. Por exemplo, `core/` não depende do Streamlit e pode ser usado sozinho:

```bash
python -c "from core import Vetorizador; print(Vetorizador.de_texto('Céu azul. Céu azul.').analisar().top(5))"
```

### Adicionar uma nova fonte

Crie uma pasta em `plugins/` seguindo o modelo de `plugins/colar/`.

O registro encontra a nova fonte automaticamente e ela aparece na interface.

O contrato está em `plugins/base.py`.

## Deploy

O projeto pode ser publicado no **Streamlit Community Cloud** diretamente pelo GitHub.

Não precisa configurar variáveis de ambiente ou segredos.

## Limitações

Por enquanto:

* `casa` e `casas` são palavras diferentes (não há stemming).
* Só é possível processar uma fonte por vez.
* Não suporta PDF ou DOCX.
* Algumas páginas que dependem de JavaScript não funcionam.
* A aparência da nuvem é fixa.
