"""
IMPORTANTE: rode este script como administrador/com permissões suficientes se o
jogo também estiver rodando com privilégios elevados, senão o Windows pode
bloquear os cliques simulados de chegarem até a janela do jogo.

IMPORTANT: Run this script as an administrator or with sufficient privileges
if the game is also running with elevated privileges; otherwise,
Windows may block the simulated clicks from reaching the game window.

"""
import random
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pyautogui
import pygetwindow as gw
import keyboard
import mss
# Título (ou parte do título) da janela do jogo, como aparece na barra de tarefas.
TITULO_JANELA = "Epic Seven"

PASTA_TEMPLATES = Path(__file__).parent / "templates"

def _t(nome: str) -> Path:
    return PASTA_TEMPLATES / nome

@dataclass
class ItemDeCompra:
    nome: str
    template_icone: Path
    templates_comprar: list
    clicar_apenas_metade_inferior: bool = False
    template_confirmar_item: Path | None = None
    preco_gold: int = 0
# --- Item 1 (mais barato) ---------------------------------------------------
ITEM_1 = ItemDeCompra(
    nome="Item 1",
    template_icone=_t("item1_icone.png"),
    templates_comprar=[
        _t("item1_comprar_qtd.png"),
    ],
    clicar_apenas_metade_inferior=True,
    template_confirmar_item=_t("item1_comprar_preco.png"),
    preco_gold=184_000,
)
# --- Item 2 (mais caro) ------------------------------------------------------
ITEM_2 = ItemDeCompra(
    nome="Item 2",
    template_icone=_t("item2_icone.png"),
    templates_comprar=[
        _t("item2_comprar_qtd.png"),
    ],
    clicar_apenas_metade_inferior=True,
    template_confirmar_item=_t("item2_comprar_preco.png"),
    preco_gold=280_000,
)

ITENS = [ITEM_1, ITEM_2]
TEMPLATE_CONFIRMAR = _t("confirmar.png")
TEMPLATE_RENOVAR = _t("renovar.png")

LIMIAR_MATCH = 0.83

AREA_CLIQUE_SEGURO = (0.72, 0.20, 0.79, 0.90)

TECLA_CANCELAR = "ctrl+alt+q"

MAX_SCROLLS_PROCURANDO = 2

PAUSA_MIN = 0.1
PAUSA_MAX = 0.3

CUSTO_RENOVAR_GEMAS = 3
# =========================================================================
# INFRAESTRUTURA
# =========================================================================
evento_parar = threading.Event()

contador_compras = {}
contador_renovacoes = 0
gold_gasto = 0
gemas_gastas = 0

motivo_parada = "cancelado"

def pausa_humana(a=PAUSA_MIN, b=PAUSA_MAX):
    time.sleep(random.uniform(a, b))

def registrar_hotkey_cancelamento():
    def _cancelar():
        print(f"\n[!] Tecla de cancelamento ({TECLA_CANCELAR}) pressionada. Parando...")
        evento_parar.set()

    keyboard.add_hotkey(TECLA_CANCELAR, _cancelar)

def configurar_orcamento() -> dict:
    def _perguntar(rotulo: str, padrao: int) -> int:
        while True:
            entrada = input(f"  {rotulo} [{padrao}]: ").strip()
            if not entrada:
                return padrao
            try:
                valor = int(entrada)
                if valor < 0:
                    raise ValueError
                return valor
            except ValueError:
                print("    Valor inválido. Digite um número inteiro maior ou igual a 0.")

    print("\n=== Configuração de orçamento ===")
    print("(Enter usa o valor padrão entre colchetes)")
    gemas_iniciais = _perguntar("Gemas disponíveis", 0)
    dinheiro_inicial = _perguntar("Dinheiro disponível", 0)
    limite_gemas = _perguntar("Quanto gastar de gemas (0 = até acabar)", gemas_iniciais)
    limite_dinheiro = _perguntar("Quanto gastar de dinheiro (0 = até acabar)", dinheiro_inicial)
    
    if limite_gemas <= 0:
        limite_gemas = gemas_iniciais
    if limite_dinheiro <= 0:
        limite_dinheiro = dinheiro_inicial
        
    if limite_gemas > gemas_iniciais:
        raise ValueError(
            f"Erro de orçamento: o limite de gasto de gemas ({limite_gemas}) é maior"
            f"que as gemas disponíveis ({gemas_iniciais})."
        )
    if limite_dinheiro > dinheiro_inicial:
        raise ValueError(
            f"Erro de orçamento: o limite gasto de dinheiro"
            f"({limite_dinheiro:,}) é maior que o dinheiro disponível"
            f"({dinheiro_inicial:,}).".replace(",",".")
        )
    return {
        "gemas_iniciais": gemas_iniciais,
        "dinheiro_inicial": dinheiro_inicial,
        "limite_gemas": limite_gemas,
        "limite_dinheiro": limite_dinheiro,
    }

def orcamento_ok(limite_gemas: int, limite_dinheiro: int) -> bool:
    global motivo_parada
    if gemas_gastas >= limite_gemas:
        motivo_parada = "limite de gemas"
        return False
    if gold_gasto >= limite_dinheiro:
        motivo_parada = "limite de dinheiro"
        return False
    return True

@dataclass
class JanelaJogo:
    left: int
    top: int
    width: int
    height: int

    @property
    def bbox_mss(self):
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}
    
    def prop_para_abs(self, px, py):
        return self.left + int(px * self.width), self.top + int(py * self.height)

def localizar_janela_jogo() -> JanelaJogo:
    janelas = gw.getWindowsWithTitle(TITULO_JANELA)
    if not janelas:
        raise RuntimeError(
            f"Não encontrei nenhuma janela com título contendo '{TITULO_JANELA}'. "
            "Confira se o jogo está aberto e se TITULO_JANELA está certo."
        )
    w = janelas[0]
    if w.isMinimized:
        w.restore()
        time.sleep(0.5)
    try:
        w.activate()
        time.sleep(0.3)
    except Exception as e:
        print(f"[?] Não consegui focar a janela automaticamente ({e}). "
              "Clique manualmente na janela do jogo antes de continuar.")
    return JanelaJogo(left=w.left, top=w.top, width=w.width, height=w.height)

def capturar_janela(janela: JanelaJogo) -> np.ndarray:
    with mss.mss() as sct:
        raw = sct.grab(janela.bbox_mss)
        img = np.array(raw)  # BGRA
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

def carregar_template(caminho: Path) -> np.ndarray:
    img = cv2.imread(str(caminho), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(
            f"Não achei o template '{caminho}'. Crie o recorte PNG e coloque nesse caminho."
        )
    return img

def encontrar_template(screenshot: np.ndarray, template: np.ndarray, limiar=LIMIAR_MATCH):
    resultado = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(resultado)
    if max_val < limiar:
        return None
    h, w = template.shape[:2]
    return max_loc[0], max_loc[1], w, h, max_val

PAUSA_CLIQUE_MIN = 0.05
PAUSA_CLIQUE_MAX = 0.12

def clicar_abs(x, y):
    pyautogui.moveTo(x, y, duration=random.uniform(0.15, 0.35))
    time.sleep(random.uniform(0.03, 0.08))  # pequena pausa pro jogo registrar o hover
    pyautogui.mouseDown()
    time.sleep(random.uniform(PAUSA_CLIQUE_MIN, PAUSA_CLIQUE_MAX))
    pyautogui.mouseUp()

MARGEM_CLIQUE_BOTAO = 0.20

def clicar_dentro_da_caixa(janela: JanelaJogo, caixa, apenas_metade_inferior: bool = False):
    x, y, w, h, _ = caixa
    mx = w * MARGEM_CLIQUE_BOTAO
    my = h * MARGEM_CLIQUE_BOTAO
    offset_x = random.uniform(mx, w - mx) if w > 2 * mx else w / 2
    y_min, y_max = my, h - my
    if apenas_metade_inferior:
        y_min = max(y_min, h / 2)
    offset_y = random.uniform(y_min, y_max) if y_max > y_min else (y_min + y_max) / 2
    abs_x = janela.left + x + offset_x
    abs_y = janela.top + y + offset_y
    clicar_abs(abs_x, abs_y)

def clique_aleatorio_seguro(janela: JanelaJogo):
    x1p, y1p, x2p, y2p = AREA_CLIQUE_SEGURO
    px = random.uniform(x1p, x2p)
    py = random.uniform(y1p, y2p)
    x, y = janela.prop_para_abs(px, py)
    clicar_abs(x, y)

SCROLL_QUANTIDADE_BAIXO = -250
SCROLL_TOPO_PASSOS = 0
SCROLL_TOPO_QUANTIDADE = 20
SCROLL_TOPO_PAUSA = 0.03  
PAUSA_SCROLL_MIN = 0.05
PAUSA_SCROLL_MAX = 0.15

def rolar_para_baixo(janela: JanelaJogo, quantidade=SCROLL_QUANTIDADE_BAIXO):
    cx, cy = janela.prop_para_abs(0.5, 0.5)
    pyautogui.moveTo(cx, cy, duration=0.08)
    pyautogui.scroll(quantidade)

def rolar_para_topo(janela: JanelaJogo, passos=SCROLL_TOPO_PASSOS):
    cx, cy = janela.prop_para_abs(0.5, 0.5)
    pyautogui.moveTo(cx, cy, duration=0.08)
    for _ in range(passos):
        pyautogui.scroll(SCROLL_TOPO_QUANTIDADE)
        time.sleep(SCROLL_TOPO_PAUSA)
# =========================================================================
# LÓGICA PRINCIPAL
# ========================================================================
def encontrar_qualquer_template(screenshot: np.ndarray, templates: list, limiar=LIMIAR_MATCH):
    for template in templates:
        achado = encontrar_template(screenshot, template, limiar)
        if achado:
            return achado
    return None

FAIXA_MESMA_LINHA_PROP = 1.6

def encontrar_template_na_mesma_linha(screenshot: np.ndarray, template: np.ndarray, y_centro: float, altura_ref: float, limiar=LIMIAR_MATCH):
    altura_total = screenshot.shape[0]
    metade_faixa = (altura_ref * FAIXA_MESMA_LINHA_PROP) / 2
    y0 = max(0, int(y_centro - metade_faixa))
    y1 = min(altura_total, int(y_centro + metade_faixa))
    if y1 <= y0:
        return None
    faixa = screenshot[y0:y1, :]
    achado = encontrar_template(faixa, template, limiar)
    if achado is None:
        return None
    x, y, w, h, conf = achado
    return x, y + y0, w, h, conf

def encontrar_qualquer_template_na_mesma_linha(screenshot: np.ndarray, templates: list, y_centro: float, altura_ref: float, limiar=LIMIAR_MATCH):
    for template in templates:
        achado = encontrar_template_na_mesma_linha(screenshot, template, y_centro, altura_ref, limiar)
        if achado:
            return achado
    return None

def tentar_comprar_item(janela: JanelaJogo, item: ItemDeCompra, template_confirmar) -> bool:
    screenshot = capturar_janela(janela)
    achado_icone = encontrar_template(screenshot, item.template_icone)
    if not achado_icone:
        return False
    ix, iy, iw, ih, conf_icone = achado_icone
    y_centro_icone = iy + ih / 2
    print(f"    [{item.nome}] Ícone encontrado na loja (confiança {conf_icone:.2f}).")
    botao_comprar = encontrar_qualquer_template_na_mesma_linha(
        screenshot, item.templates_comprar, y_centro_icone, ih
    )
    if not botao_comprar:
        print(f"    [{item.nome}] Não achei o botão de comprar alinhado com o ícone — abortando essa tentativa.")
        return False
    conf_botao = botao_comprar[-1]
    print(f"    [{item.nome}] Botão de comprar confirmado na mesma linha (confiança {conf_botao:.2f}). Comprando...")
    clicar_dentro_da_caixa(janela, botao_comprar, apenas_metade_inferior=item.clicar_apenas_metade_inferior)
    pausa_humana()
    if item.template_confirmar_item is not None:
        screenshot2 = capturar_janela(janela)
        confirmar_item = encontrar_template(screenshot2, item.template_confirmar_item)
        if confirmar_item:
            clicar_dentro_da_caixa(janela, confirmar_item)
            pausa_humana()
    if template_confirmar is not None:
        screenshot3 = capturar_janela(janela)
        confirmar = encontrar_template(screenshot3, template_confirmar)
        if confirmar:
            clicar_dentro_da_caixa(janela, confirmar)
            pausa_humana()
    return True

def renovar_loja(janela: JanelaJogo, template_renovar, template_confirmar) -> bool:
    rolar_para_topo(janela)
    pausa_humana()
    screenshot = capturar_janela(janela)
    botao = encontrar_template(screenshot, template_renovar)
    if not botao:
        print("    [!] Não achei o botão de renovar loja na tela.")
        return False
    clicar_dentro_da_caixa(janela, botao)
    pausa_humana()
    if template_confirmar is not None:
        screenshot2 = capturar_janela(janela)
        confirmar = encontrar_template(screenshot2, template_confirmar)
        if confirmar:
            clicar_dentro_da_caixa(janela, confirmar)
            pausa_humana()

    return True

def procurar_e_comprar(janela: JanelaJogo, itens: list, template_confirmar, limite_dinheiro:int) -> set:
    global contador_compras, gold_gasto
    comprados = set()
    rolar_para_topo(janela)
    pausa_humana(PAUSA_SCROLL_MIN, PAUSA_SCROLL_MAX)
    for tentativa in range(MAX_SCROLLS_PROCURANDO + 1):
        if evento_parar.is_set():
            return comprados
        for idx, item in enumerate(itens):
            if idx in comprados:
                continue
            if gold_gasto + item.preco_gold > limite_dinheiro:
                continue
            if tentar_comprar_item(janela, item, template_confirmar):
                contador_compras[item.nome] = contador_compras.get(item.nome, 0) + 1
                gold_gasto += item.preco_gold
                print(f"[✓] {item.nome} comprado.")
                comprados.add(idx)
        if len(comprados) == len(itens):
            break
        if tentativa < MAX_SCROLLS_PROCURANDO:
            rolar_para_baixo(janela)
            pausa_humana(PAUSA_SCROLL_MIN, PAUSA_SCROLL_MAX)
    return comprados

def loop_principal():
    global contador_renovacoes, gemas_gastas, motivo_parada
    
    orcamento = configurar_orcamento()
    gemas_iniciais = orcamento["gemas_iniciais"]
    dinheiro_inicial = orcamento["dinheiro_inicial"]
    limite_gemas = orcamento["limite_gemas"]
    limite_dinheiro = orcamento["limite_dinheiro"]
    
    print("Localizando janela do jogo...")
    janela = localizar_janela_jogo()
    print(f"Janela encontrada: {janela}")
    print("Carregando templates...")
    for item in ITENS:
        item.template_icone = carregar_template(item.template_icone)
        item.templates_comprar = [carregar_template(p) for p in item.templates_comprar]
        if item.template_confirmar_item is not None:
            if item.template_confirmar_item.exists():
                item.template_confirmar_item = carregar_template(item.template_confirmar_item)
            else:
                item.template_confirmar_item = None
    template_renovar = carregar_template(TEMPLATE_RENOVAR)
    template_confirmar = None
    if TEMPLATE_CONFIRMAR.exists():
        template_confirmar = carregar_template(TEMPLATE_CONFIRMAR)

    registrar_hotkey_cancelamento()
    print(f"Pressione {TECLA_CANCELAR} a qualquer momento para cancelar.")
    print(f"Orçamento: gastar até {limite_gemas} gemas e {limite_dinheiro:,} de dinheiro."
          .replace(",", "."))
    print("Iniciando em 3 segundos — deixe a janela do jogo em foco...")
    time.sleep(3)
    itens_ja_comprados_nesta_rodada_de_loja = set()
    while not evento_parar.is_set():
        if not orcamento_ok(limite_gemas, limite_dinheiro):
            break
        clique_aleatorio_seguro(janela)
        pausa_humana()
        if evento_parar.is_set():
            break
        comprados_agora = procurar_e_comprar(janela, ITENS, template_confirmar, limite_dinheiro)
        itens_ja_comprados_nesta_rodada_de_loja |= comprados_agora
        if evento_parar.is_set():
            break
        if not orcamento_ok(limite_gemas, limite_dinheiro):
            break
        if len(itens_ja_comprados_nesta_rodada_de_loja) == len(ITENS):
            print("[*] Os itens configurados já foram comprados nesta rotação da loja. Renovando...")
        else:
            print("[*] Item(ns) não encontrado(s) na loja atual. Renovando...")
        if not renovar_loja(janela, template_renovar, template_confirmar):
            print("[!] Falha ao renovar a loja. Parando por segurança.")
            motivo_parada = "erro ao renovar a loja"
            break
        contador_renovacoes += 1
        gemas_gastas += CUSTO_RENOVAR_GEMAS
        itens_ja_comprados_nesta_rodada_de_loja.clear()
        pausa_humana(1.0, 1.8)

    if evento_parar.is_set() and motivo_parada == "cancelado":
        motivo_parada = "cancelado pelo usuário"

    total_itens = sum(contador_compras.values())
    print("\n=== Relatório da execução ===")
    print(f"Motivo da parada: {motivo_parada}")
    print(f"Gemas: {gemas_iniciais} -> {gemas_iniciais - gemas_gastas} "
          f"(gastas: {gemas_gastas})")
    print(f"Dinheiro: {dinheiro_inicial:,} -> {dinheiro_inicial - gold_gasto:,}"
          .replace(",", "."))
    print(f"Loja renovada: {contador_renovacoes}x")
    print(f"Ouro gasto comprando: {gold_gasto:,}".replace(",", "."))
    print(f"Itens comprados (total: {total_itens}):")
    if contador_compras:
        for nome_item, qtd in contador_compras.items():
            print(f"  - {nome_item}: {qtd}")
    else:
        print("  (nenhum item comprado)")
    print("==============================\n")
    print("Bot finalizado.")
    
if __name__ == "__main__":
    try:
        loop_principal()
    except KeyboardInterrupt:
        print("\nInterrompido manualmente (Ctrl+C).")
    except Exception as e:
        print(f"\n[ERRO] {e}")
        sys.exit(1)