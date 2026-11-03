# Homologação obrigatória no Windows

**Estado do pacote:** testes unitários e de contrato executados em ambiente Linux sem o jogo. A UI PySide6 e os eventos Win32 **não foram testados de ponta a ponta** neste ambiente. Antes de distribuir, validar os cenários abaixo em máquina Windows real e em ambiente de jogo controlado.

## Pré-voo (sem usar moeda do jogo)

- [x] Abrir `python main.py`, ver as cinco abas e sair sem console travado.
- [x] Configurar saldo/limite de gemas, preço e área segura; salvar, fechar, reabrir e verificar persistência.
- [x] Confirmar cópia dos PNGs para `%APPDATA%\Epic7ShopBot\templates` na primeira inicialização.
- [] Alterar um PNG de usuário e comprovar que não é sobrescrito na inicialização seguinte.
- [] Salvar captura real de loja como PNG; usar Calibração > Testar reconhecimento e analisar retângulos.
- [] Confirmar que o atalho global e o comando Parar da bandeja funcionam.

## Execução monitorada

- [ ] Com saldos limitados, realizar operação de teste acompanhando cada clique na tela.
- [ ] Fazer Alt+Tab **antes de um clique** e confirmar que não há movimento/click em outro programa.
- [ ] Cobrir parte da janela do jogo com outra janela sempre no topo e confirmar bloqueio do clique.
- [ ] Trocar o foco durante uma janela modal e confirmar status de **resultado incerto** quando a ação já começou.
- [ ] Mover/redimensionar o jogo durante a execução e confirmar interrupção por janela inválida.
- [ ] Verificar ausência de compras/renovações duplicadas após pausa e retorno de foco.
- [ ] Validar casos com animação lenta, confirmação de compra ausente e botão de renovação ausente.
- [ ] Verificar limites exatamente no teto (sem ultrapassar ouro/gemas declarados).
- [ ] Comparar métricas estimadas com o saldo real no jogo; ajustar gabaritos se houver inconsistência.
- [ ] Repetir testes em DPI 100%, 125%, 150%, monitor único e múltiplos monitores.

## Empacotamento

- [ ] Empacotar com `python -m PyInstaller --noconfirm build.spec` no Windows.
- [ ] Abrir `dist\Epic7ShopBot\Epic7ShopBot.exe` em um Windows limpo sem Python instalado.
- [ ] Confirmar plugin de plataforma Qt e imagens incluídas no executável.
- [ ] Confirmar que a falta de permissões adequadas produz falha explícita e não cliques em aplicativo estranho.
- [ ] Verificar logs em `%APPDATA%\Epic7ShopBot\logs\sessao.log`.
- [ ] Após estabilidade, avaliar distribuição onefile ou instalador assinado.
