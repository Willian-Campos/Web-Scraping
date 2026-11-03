"""Coletor Chaves na Mão (SJC). Respeita o robots.txt: só caminhos + ?pg=2, sem outros parâmetros.
Cobertura: fatia por bairro x quartos (caminho da URL) e vai até a página 2 de cada fatia."""
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from db import conectar, salvar

BASE = "https://www.chavesnamao.com.br"
CIDADE = "sp-sao-jose-dos-campos"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36",
           "Accept-Language": "pt-BR,pt;q=0.9"}
ESPERA = 2.0  # segundos entre pedidos
sessao = requests.Session()
sessao.headers.update(HEADERS)


def baixar(url):
    time.sleep(ESPERA)
    r = sessao.get(url, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.text


def num(txt):
    return int(re.sub(r"\D", "", txt)) if txt and re.search(r"\d", txt) else None


def parse_card(card, negocio, tipo):
    a = card.select_one('a[href*="/imovel/"]')
    if not a:
        return None
    href = a["href"]
    m = re.search(r"/id-(\d+)", href)
    if not m:
        return None
    texto = card.get_text(" | ", strip=True)
    titulo = next((p for p in texto.split(" | ") if "São José dos Campos" in p and "," in p and "para" in p.lower()), "")
    preco = re.search(r"R\$\s*([\d\.]+)", texto)
    area = re.search(r"\|\s*(\d+(?:[\.,]\d+)?)\s*\|\s*m²", texto)
    reg = re.search(r"\|\s*([^|]+?),\s*São José dos Campos/SP", texto)
    gx = lambda pad: num(re.search(pad, titulo).group(1)) if re.search(pad, titulo) else None
    anunc = texto.split(" | ")[0]
    return {
        "fonte": "chavesnamao", "id_fonte": m.group(1), "url": BASE + href, "negocio": negocio, "tipo": tipo,
        "cidade": "São José dos Campos", "bairro": reg.group(1).strip() if reg else None, "titulo": titulo,
        "preco": float(preco.group(1).replace(".", "")) if preco else None,
        "area_m2": float(area.group(1).replace(",", ".")) if area else None,
        "quartos": gx(r"(\d+)\s*dormit"), "suites": gx(r"(\d+)\s*su[ií]te"),
        "banheiros": gx(r"(\d+)\s*banheiro"), "vagas": gx(r"(\d+)\s*vaga"), "anunciante": anunc,
    }


def pagina(url, negocio, tipo):
    html = baixar(url)
    if html is None:
        return [], None
    s = BeautifulSoup(html, "lxml")
    total = re.search(r'"name":\s*"([\d\.]+) ', html)
    itens = [parse_card(c, negocio, tipo) for c in s.select('div[class*="card_card"]')]
    return [i for i in itens if i], (num(total.group(1)) if total else None)


def bairros(negocio_slug):
    html = baixar(f"{BASE}/{negocio_slug}/{CIDADE}/bairros/")
    if not html:
        return []
    achados = set(re.findall(rf"/{negocio_slug}/{CIDADE}/([a-z0-9\-]+)/", html))
    return sorted(achados - {"bairros", "1-quarto", "2-quartos", "3-quartos", "4-quartos"})


def rodar(negocio="venda", tipo="apartamento", limite_bairros=None):
    slug = "apartamentos-a-venda" if negocio == "venda" else "apartamentos-para-alugar"
    con = conectar()
    inicio = datetime.now().isoformat(timespec="seconds")
    lista = bairros(slug)
    print(f"{len(lista)} bairros encontrados")
    if limite_bairros:
        lista = lista[:limite_bairros]
    vistos = set()
    esperado = None
    for b in lista:
        for q in ["1-quarto", "2-quartos", "3-quartos", "4-quartos"]:
            for pg in ("", "?pg=2"):
                url = f"{BASE}/{slug}/{CIDADE}/{b}/{q}/{pg}"
                itens, total = pagina(url, negocio, tipo)
                for i in itens:
                    salvar(con, i)
                    vistos.add(i["id_fonte"])
                con.commit()
                print(f"{b}/{q}/{pg or 'pg1'}: {len(itens)} cards (total fatia {total}) | únicos acumulados {len(vistos)}")
                if len(itens) < 12:
                    break
    con.execute("INSERT INTO execucoes VALUES (?,?,?,?,?,?)",
                ("chavesnamao", inicio, datetime.now().isoformat(timespec="seconds"), esperado, len(vistos), f"{negocio}/{tipo}"))
    con.commit()


if __name__ == "__main__":
    rodar(limite_bairros=int(sys.argv[1]) if len(sys.argv) > 1 else None)
