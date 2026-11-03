# Epic7 Shop Bot — interface desktop segura (v2)

Projeto refatorado a partir do [script original](https://github.com/Frperoger/Rerol-Secretshop-e7).
Não utiliza o HTML do protótipo. O código original `epic7_shop_bot.py` pode ser mantido como referência, mas **a interface nova inicia em `main.py`**.

## Requisitos

- Windows 10/11, 64 bits, Python 3.11 ou superior.
- Jogo aberto e visível na resolução em que os templates foram capturados.
- A pasta original `templates/` deve permanecer na raiz do repositório (o pacote de atualização não inclui as imagens, porque elas já existem no GitHub).

## Instalação no repositório existente

1. Extraia o ZIP de atualização **na raiz de `Rerol-Secretshop-e7`**, permitindo substituir `requirements.txt`. Preserve `epic7_shop_bot.py` e `templates/`.
2. Abra o terminal (PowerShell) nessa pasta.
3. Execute:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Se preferir, depois de instalar as dependências, clique em `iniciar_gui.bat` (o Windows precisa resolver `python` no PATH).

## Segurança / como o bot opera

- **Sem privilégios elevados por padrão:** não há UAC forçado. Se o emulador estiver em contexto elevado, a entrada simulada poderá não funcionar; utilize o mesmo nível de privilégios apenas quando estritamente necessário.
- **FailSafe do PyAutoGUI permanece ativo:** mover o cursor para um canto de tela pode provocar a parada automática.
- **HWND rigoroso:** checa que a janela é a mesma, está em primeiro plano, não foi movida/redimensionada e que o ponto de clique está nela (`WindowFromPoint`), inclusive **depois do movimento do cursor**.
- **Perda de foco:** pausa por até 30 segundos (configurável); recomeça a varredura sem renovar a loja. Não clica em outras janelas.
- **Cancelamento:** `Ctrl+Alt+Q` enquanto o aplicativo está aberto (quando disponível), botão Parar no painel ou no menu da bandeja. Se o sistema bloquear o atalho global, use o menu da bandeja. A liberação do botão do mouse fica em bloco `finally`.
- **Compra:** só contabiliza como *verificada visualmente* quando a modal de preço apareceu, foi confirmada e o botão de compra correspondente deixou de ser detectado na mesma linha (ou há template opcional de estado vendido). A detecção não equivale à conferência do saldo real.
- **Resultado incerto:** se uma ação potencialmente irreversível começou e não foi possível verificar o estado, **o loop para imediatamente**. Os gastos associados podem não aparecer nos totais estimados. Confira manualmente o jogo antes de reiniciar.
- **Renovação:** exige visualização da modal de confirmação, clique nela e desaparecimento da modal; contabiliza o custo como estimativa, sem OCR de gemas.
- **Diagnóstico de reconhecimento:** na aba Calibração, selecione uma captura PNG da loja. Mostra contornos do ícone/botão, sem automação do mouse.

**Importante:** esta versão foi desenhada para falhar com segurança, mesmo que isso resulte em mais interrupções por confirmação inconclusiva. Para melhorar a confirmação das compras, cada item pode apontar para um PNG opcional de estado `Vendido`, salvo na pasta de templates.

## Organização de arquivos e persistência

- `app/core/`: visão, orçamento e geometria puros, independentes de Qt/Windows.
- `app/platform/`: seleção de janela Win32, proteção de foco e eventos físicos.
- `app/engine/`: estado e loop de automação por execução.
- `app/ui/`: Qt Widgets e painel de calibração offline.
- `%APPDATA%\Epic7ShopBot\config.json`: configurações (gravação atômica).
- `%APPDATA%\Epic7ShopBot\templates\`: PNGs editáveis; arquivos previamente existentes **nunca são sobrescritos** na inicialização.
- `%APPDATA%\Epic7ShopBot\history.jsonl`: histórico de execuções.
- `%APPDATA%\Epic7ShopBot\logs\sessao.log`: log de execução rotativo (até 3 backups).

O saldo e os gastos exibidos são **estimativas calculadas** a partir dos preços declarados e das transações verificadas; não uma leitura dos contadores no jogo.

## Testes

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

Os testes unitários rodam sem o jogo e sem o Windows. O **teste com o jogo real em Windows ainda é obrigatório** antes de considerar a distribuição homologada: início/cancelamento, perda de foco em momentos distintos, dois monitores, DPI 100/125/150%, compra com telas lentas e orçamento esgotado. Também é recomendável verificar as regras de uso do jogo.

## Empacotar como EXE

No Windows com `requirements-dev.txt` instalado:

```powershell
python -m PyInstaller --noconfirm build.spec
```

Resultado: `dist\Epic7ShopBot\Epic7ShopBot.exe` e sua pasta com dependências. Escolhemos **onedir** primeiro para facilitar inspeção de plugins Qt. Apenas após homologar em máquina limpa avalie mudar para `onefile`; o executável não exige Python instalado.

## Compatibilidade com a versão anterior

A implementação anterior de exemplo (`gui.py`/`bot_engine.py`, baseada em Tkinter) **não deve ser copiada junto com esta versão**. Aqui a interface é PySide6 e a lógica está dividida em módulos independentes. Não substitua ou apague os templates PNG existentes.
