"""Camada de saída: como o resultado aparece na tela.

Três arquivos, do mais puro para o mais acoplado:

- `opcoes.py`   dicts de configuração do ECharts — dado puro, sem Streamlit
- `tabelas.py`  Counter -> DataFrame — só pandas, sem Streamlit
- `paineis.py`  os blocos de tela — aqui sim mora o Streamlit da exibição

Lê a `Analise` que o `core` produziu e não processa nada.
"""
