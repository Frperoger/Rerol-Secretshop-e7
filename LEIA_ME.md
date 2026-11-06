# Compra com template de linha única — Epic7 Shop Bot v3.0.3

Substitui **o template de compra de todos os itens** pela imagem fornecida
`1/1 Comprar` de 272 × 80 pixels, preservando os nomes dos PNGs configurados
(`item1_comprar_qtd.png`, `item2_comprar_qtd.png`, `item3_comprar_qtd.png`, etc.).

## O que foi corrigido

1. Desfaz o patch anterior **exclusivo do Item 1**: remove a comparação dupla
   de escala original/calibrada e as funções especiais `same_row_button_variants`
   e `item1_buy_action_region`, quando presentes.
2. Instala o PNG novo nos templates de compra do repositório e na pasta ativa do
   usuário (`%APPDATA%\Epic7ShopBot\templates` ou pasta customizada).
3. Reconhece **primeiro o ícone**; procura o botão somente **à direita e na mesma
   linha vertical** desse ícone. Não pega o botão de outra linha, mesmo que seja
   visualmente idêntico.
4. Usa em todos os itens a região direita da imagem ao clicar em `Comprar`,
   evitando o seletor `1/1`. Clique de renovação, preço e modal não foram alterados.
5. Mantém escala calibrada única para todos os PNGs. Não força busca em várias
   escalas, nem muda o limiar ou a velocidade.

## Instalação no Windows

Feche o bot. Extraia o ZIP **na raiz do repositório**, na branch `v3`.

```powershell
git switch v3
.\.venv\Scripts\python.exe .\aplicar_compra_unificada_v303.py --check
.\.venv\Scripts\python.exe .\aplicar_compra_unificada_v303.py --apply
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp
.\.venv\Scripts\python.exe main.py
```

**Após aplicar, faça nova captura da loja aberta e clique em `Calibrar e salvar
escala`.** A substituição dos PNGs altera a assinatura dos templates; perfis
salvos anteriormente deixam de valer. A calibração deve ser feita com a mesma
resolução/zoom usados ao executar o bot.

O instalador não edita `config.json`, nem ícones, nem os templates de preço ou
renovação. Faz backups em `%APPDATA%\Epic7ShopBot\backups\compra_unificada_v303_*`.

Se a atualização anterior foi aplicada, `tests/test_item1_same_row_v303.py`
será removido com backup porque testa funções específicas agora desfeitas.

**Nota:** se forem cadastrados novos itens depois desta atualização com outros
nomes de PNG de compra, reaplique o instalador para copiar o mesmo template
para esses novos nomes.

**Validação:** testes simulados de correspondência e clique. É necessária
homologação visual no Epic Seven/Windows; o sucesso do `mouseDown`/`mouseUp`
não garante que o jogo recebeu o clique.
