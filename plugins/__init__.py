"""Fontes de texto do app, cada uma numa subpasta.

Como escrever uma nova:

    plugins/minha_fonte/
    ├─ __init__.py    from .fonte import MinhaFonte as FONTE
    └─ fonte.py       class MinhaFonte(FonteTexto): ...

Só isso — o `registro` acha a pasta sozinho e a opção aparece na tela. O
contrato (as duas interfaces: `formulario` e `obter_corpus`) está em `base.py`,
e `colar/` é o exemplo mais curto de todos, com ~20 linhas.

Esta camada pode importar streamlit à vontade: ela É a entrada. O que ela não
pode é importar `core` ou `visual` — a seta só aponta para fora.
"""
