"""Armazenamento local em SQLite (fonte da verdade). Sheets será só um espelho."""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "imoveis.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS anuncios (
    fonte TEXT NOT NULL,
    id_fonte TEXT NOT NULL,
    url TEXT,
    negocio TEXT,           -- venda | aluguel
    tipo TEXT,              -- apartamento | casa | ...
    cidade TEXT,
    bairro TEXT,
    titulo TEXT,
    preco REAL,
    area_m2 REAL,
    quartos INTEGER,
    suites INTEGER,
    banheiros INTEGER,
    vagas INTEGER,
    anunciante TEXT,
    primeira_vez TEXT,
    ultima_vez TEXT,
    PRIMARY KEY (fonte, id_fonte)
);
CREATE TABLE IF NOT EXISTS historico_preco (
    fonte TEXT, id_fonte TEXT, data TEXT, preco REAL
);
CREATE TABLE IF NOT EXISTS execucoes (
    fonte TEXT, inicio TEXT, fim TEXT, esperado INTEGER, coletado INTEGER, obs TEXT
);
"""


def conectar():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    return con


def salvar(con, a: dict):
    """Insere ou atualiza um anúncio; registra mudança de preço."""
    agora = datetime.now().isoformat(timespec="seconds")
    antigo = con.execute(
        "SELECT preco FROM anuncios WHERE fonte=? AND id_fonte=?", (a["fonte"], a["id_fonte"])
    ).fetchone()
    campos = ["url", "negocio", "tipo", "cidade", "bairro", "titulo", "preco", "area_m2",
              "quartos", "suites", "banheiros", "vagas", "anunciante"]
    if antigo is None:
        con.execute(
            f"INSERT INTO anuncios (fonte,id_fonte,{','.join(campos)},primeira_vez,ultima_vez) "
            f"VALUES (?,?,{','.join('?' * len(campos))},?,?)",
            [a["fonte"], a["id_fonte"], *[a.get(c) for c in campos], agora, agora],
        )
        con.execute("INSERT INTO historico_preco VALUES (?,?,?,?)", (a["fonte"], a["id_fonte"], agora, a.get("preco")))
    else:
        sets = ",".join(f"{c}=?" for c in campos)
        con.execute(f"UPDATE anuncios SET {sets}, ultima_vez=? WHERE fonte=? AND id_fonte=?",
                    [*[a.get(c) for c in campos], agora, a["fonte"], a["id_fonte"]])
        if antigo[0] != a.get("preco"):
            con.execute("INSERT INTO historico_preco VALUES (?,?,?,?)", (a["fonte"], a["id_fonte"], agora, a.get("preco")))
