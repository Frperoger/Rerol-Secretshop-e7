# Epic7 Shop Bot — interface desktop segura (v2)

Projeto refatorado a partir do [script original](https://github.com/Frperoger/Rerol-Secretshop-e7).

## Requisitos

- Jogo aberto e visível na resolução em que os templates foram capturados.
- A pasta original `templates/` deve permanecer na raiz do repositório (o pacote de atualização não inclui as imagens, porque elas já existem no GitHub).

## Segurança / como o bot opera

- **Sem privilégios elevados por padrão:** não há UAC forçado. Se o emulador estiver em contexto elevado, a entrada simulada poderá não funcionar; utilize o mesmo nível de privilégios apenas quando estritamente necessário.
- **FailSafe do PyAutoGUI permanece ativo:** mover o cursor para um canto de tela pode provocar a parada automática.
- **HWND rigoroso:** checa que a janela é a mesma, está em primeiro plano, não foi movida/redimensionada e que o ponto de clique está nela (`WindowFromPoint`), inclusive **depois do movimento do cursor**.
- **Perda de foco:** pausa por até 30 segundos (configurável); recomeça a varredura sem renovar a loja. Não clica em outras janelas.
- **Cancelamento:** `Ctrl+Alt+Q` enquanto o aplicativo está aberto (quando disponível), botão Parar no painel ou no menu da bandeja. Se o sistema bloquear o atalho global, use o menu da bandeja.
- **Compra:** só contabiliza como *verificada visualmente* quando a modal de preço apareceu, foi confirmada e o botão de compra correspondente deixou de ser detectado na mesma linha (ou há template opcional de estado vendido). A detecção não equivale à conferência do saldo real.
- **Resultado incerto:** se uma ação potencialmente irreversível começou e não foi possível verificar o estado, **o loop para imediatamente**. Os gastos associados podem não aparecer nos totais estimados. Confira manualmente o jogo antes de reiniciar.
- **Renovação:** exige visualização da modal de confirmação, clique nela e desaparecimento da modal.
- **Diagnóstico de reconhecimento:** na aba Calibração, selecione uma captura PNG da loja. Mostra contornos do ícone/botão, sem automação do mouse.

**Importante:** esta versão foi desenhada para falhar com segurança, mesmo que isso resulte em mais interrupções por confirmação inconclusiva. Para melhorar a confirmação das compras, cada item pode apontar para um PNG opcional de estado `Vendido`, salvo na pasta de templates.

### Direitos autorais e licença

Copyright © 2026 [Nome do titular]. Todos os direitos reservados.

O Rerol-Secretshop-e7 é um software independente, disponibilizado gratuitamente para uso pessoal, conforme os termos do arquivo LICENSE.

É proibida a venda, comercialização, distribuição remunerada ou exploração comercial do software sem autorização prévia e expressa do titular dos direitos.

Este projeto não possui vínculo oficial com a Smilegate ou com os responsáveis pelo jogo Epic Seven.