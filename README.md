# Epic Seven — Secret Shop Reroll Bot (v2)

[Português](#português) | [English](#english)

## Português

Aplicativo desktop com interface gráfica para automatizar a busca de itens na Loja Secreta do **Epic Seven**.

### Recursos

- Interface gráfica para iniciar, acompanhar e parar a automação.
- Reconhecimento de itens por imagens (`templates/`).
- Verificações de foco da janela e interrupção em situações incertas.
- Ferramentas de calibração e diagnóstico de imagens.

### Como executar

**Pelo Release (mais simples):** baixe a versão compilada na seção [Releases](https://github.com/Frperoger/Rerol-Secretshop-e7/releases), extraia os arquivos caso necessário e execute o aplicativo (`.exe`) diretamente. Não é necessário instalar Python nem executar o código-fonte.

**Pelo código-fonte:**

1. Instale o Python e as dependências: `pip install -r requirements.txt`.
2. Abra o jogo e mantenha sua janela visível.
3. Execute `python main.py` ou use `iniciar_gui.bat` no Windows.
4. Configure o aplicativo e inicie a automação pela interface.

Para testar o código: `pip install -r requirements-dev.txt` e `python -m pytest -q`.

**Atenção:** monitore a execução e confirme compras e gastos diretamente no jogo. A automação pode parar quando não conseguir verificar uma ação com segurança.

**Aviso:** projeto gratuito, independente e não oficial. Não possui vínculo com os responsáveis por Epic Seven. Verifique os termos de uso do jogo antes de utilizar automações.

## English

Desktop application with a graphical interface for automating item searches in the **Epic Seven** Secret Shop.

### Features

- GUI to start, monitor, and stop automation.
- Image-based item recognition (`templates/`).
- Window-focus checks and safe stops when an action cannot be verified.
- Image calibration and diagnostic tools.

### How to run

**From a Release (easiest):** download the packaged version from [Releases](https://github.com/Frperoger/Rerol-Secretshop-e7/releases), extract the files if needed, and run the application (`.exe`) directly. You do not need to install Python or run the source code.

**From source:**

1. Install Python and the dependencies: `pip install -r requirements.txt`.
2. Open the game and keep its window visible.
3. Run `python main.py`, or use `iniciar_gui.bat` on Windows.
4. Configure the application and start automation from the GUI.

To run tests: `pip install -r requirements-dev.txt` and `python -m pytest -q`.

**Caution:** supervise execution and verify purchases and spending in the game. Automation may stop if an action cannot be confirmed safely.

**Disclaimer:** free, independent, unofficial project. Not affiliated with the creators or publishers of Epic Seven. Review the game's terms before using automation.
