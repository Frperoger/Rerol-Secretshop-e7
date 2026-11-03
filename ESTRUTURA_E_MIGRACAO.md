# Estrutura para integrar ao GitHub

Este ZIP é um **overlay**: os caminhos começam diretamente na raiz do repositório `Frperoger/Rerol-Secretshop-e7`. Não contém nem substitui os templates PNG ou o script de automação legado.

```text
Rerol-Secretshop-e7/
├── main.py                       [NOVO] ponto de entrada PySide6 / DPI
├── epic7_shop_bot.py             [PRESERVAR] script original do repositório
├── requirements.txt              [SUBSTITUIR] dependências da versão desktop
├── requirements-dev.txt          [NOVO] testes e empacotamento
├── build.spec                    [NOVO] PyInstaller onedir, sem admin obrigatório
├── iniciar_gui.bat               [NOVO] atalho de inicialização Windows
├── .gitignore                    [NOVO]
├── README.md                     [NOVO]
├── ESTRUTURA_E_MIGRACAO.md       [NOVO] este mapa
├── CHECKLIST_WINDOWS.md          [NOVO] roteiro de homologação real
├── templates/                    [PRESERVAR] PNGs existentes no GitHub
│   ├── confirmar.png
│   ├── renovar.png
│   ├── item1_icone.png
│   ├── item1_comprar_qtd.png
│   ├── item1_comprar_preco.png
│   ├── item2_icone.png
│   ├── item2_comprar_qtd.png
│   └── item2_comprar_preco.png
├── app/
│   ├── __init__.py
│   ├── config.py                  JSON atômico e templates AppData não destrutivos
│   ├── logging_setup.py           logging rotativo
│   ├── models.py                 modelos e erros tipados
│   ├── core/
│   │   ├── __init__.py
│   │   ├── budget.py              validação financeira / sem sobrecustos
│   │   ├── geometry.py            coordenadas em pixels
│   │   └── vision.py              matchTemplate e associação na mesma linha
│   ├── platform/
│   │   ├── __init__.py
│   │   ├── windows.py             Win32, DPI v2, HWND, foco, hit-test
│   │   └── desktop.py             mss, mouse, scroll, transações verificadas
│   ├── engine/
│   │   ├── __init__.py
│   │   └── runner.py              estado isolado por execução / pausas
│   └── ui/
│       ├── __init__.py
│       ├── controller.py          sinais Qt e thread de trabalho
│       ├── diagnostics.py         detecção em PNG offline sem cliques
│       ├── main_window.py         abas Bot/Itens/Orçamento/Calibração/Relatório
│       └── style.py               tema escuro Qt
└── tests/
    ├── test_budget_config.py
    ├── test_vision_geometry.py
    ├── test_runner.py
    └── test_desktop_safety.py
```

## Principais decisões diferentes da especificação Adapta

1. A interface PySide6 foi mantida, mas a engenharia de foco **não reposiciona** nem fixa janelas no topo. Ela oculta o painel para a bandeja e verifica `HWND`, foco, geometria e oclusão antes de clicar.
2. `pyautogui.FAILSAFE` permanece ativo. `Ctrl+Alt+Q` e Parar na bandeja são canais de parada adicionais.
3. Uma compra nunca é contabilizada apenas pelo disparo de um clique; requer evidência visual pós-transação em duas capturas. Evidências insuficientes geram encerramento com status **resultado incerto**.
4. O motor de automação é Python puro; a UI recebe telemetria via sinais Qt. Uma execução não herda contadores nem eventos de parada da anterior.
5. O teste de reconhecimento é inicialmente **offline**, em PNG, sem disparar ações no desktop.
6. O `.exe` inicial é `onedir` e **não força** privilégio de administrador. O `onefile` fica para uma etapa posterior de homologação.
7. Configurações e PNGs editáveis ficam no perfil do usuário, sem sobreposição automática de gabaritos alterados.

## Atualização no GitHub

Copie os arquivos do ZIP para uma cópia local do repositório original e rode os testes. Depois faça commit e push pelos seus meios habituais:

```powershell
# dentro do repositório clonado
Expand-Archive -Path ..\Epic7_Shop_Bot_v2_overlay.zip -DestinationPath . -Force
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe main.py
# Depois de validar em Windows:
git add .
git commit -m "Refatora bot e adiciona interface PySide6 com protecoes de execucao"
git push origin main
```

Os comandos **não são executados automaticamente**. É recomendável publicar inicialmente em uma branch e revisar o diff antes de mesclar em `main`.
