"""Verifica Stock: servidor local con SQLite. Uso: python server.py"""
import json
import re
import sqlite3
import sys
import webbrowser
from contextlib import closing
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "stock.db"
HOST, PORT = "127.0.0.1", 8000
MAX_BODY = 1_000_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS productos(
  sku TEXT PRIMARY KEY,
  nombre TEXT NOT NULL,
  stock INTEGER NOT NULL CHECK (stock >= 0)
);
CREATE TABLE IF NOT EXISTS pedidos(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fecha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pedido_items(
  pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
  sku TEXT NOT NULL,
  nombre TEXT NOT NULL,
  cantidad INTEGER NOT NULL
);
"""

SEED = [
    ("CON-SW02", "Consola Switch OLED", 14),
    ("CON-PS5D", "Consola PlayStation 5 Digital", 3),
    ("CON-XSX", "Consola Xbox Series X", 0),
    ("CTL-DS5", "Control DualSense", 27),
    ("CTL-PROJ", "Control Pro Joy-Con", 6),
    ("JGO-ZELD", "The Legend of Zelda: Ecos", 9),
    ("JGO-FIFA", "FC 26", 2),
    ("JGO-MARI", "Mario Kart World", 0),
    ("ACC-HDST", "Audífonos gamer inalámbricos", 18),
    ("ACC-MICR", "Tarjeta microSD 512GB", 5),
]


class ApiError(Exception):
    def __init__(self, status, mensaje, **data):
        super().__init__(mensaje)
        self.status = status
        self.data = data


def connect():
    # Autocommit: las transacciones de varios pasos se abren a mano con BEGIN.
    db = sqlite3.connect(DB_PATH, isolation_level=None, timeout=5)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    nueva = not DB_PATH.exists()
    with closing(connect()) as db:
        db.executescript(SCHEMA)
        if nueva:
            db.executemany("INSERT INTO productos VALUES (?, ?, ?)", SEED)


def texto(valor, campo):
    if not isinstance(valor, str) or not valor.strip():
        raise ApiError(400, f"El campo «{campo}» es obligatorio")
    return valor.strip()


def entero(valor, minimo, campo):
    if type(valor) is not int or valor < minimo:
        raise ApiError(400, f"El campo «{campo}» debe ser un entero mayor o igual a {minimo}")
    return valor


def leer_items(body):
    items = body.get("items")
    if not isinstance(items, list) or not items:
        raise ApiError(400, "El pedido está vacío")
    cantidades = {}
    for item in items:
        if not isinstance(item, dict):
            raise ApiError(400, "Formato de pedido inválido")
        sku = texto(item.get("sku"), "sku")
        cantidades[sku] = cantidades.get(sku, 0) + entero(item.get("qty"), 1, "qty")
    return cantidades


def verificar(db, cantidades):
    lineas = []
    for sku, qty in cantidades.items():
        p = db.execute("SELECT nombre, stock FROM productos WHERE sku = ?", (sku,)).fetchone()
        if not p:
            raise ApiError(404, f"No existe el producto {sku}")
        lineas.append({
            "sku": sku,
            "nombre": p["nombre"],
            "pedido": qty,
            "disponible": p["stock"],
            "faltante": max(0, qty - p["stock"]),
        })
    return {"ok": all(l["faltante"] == 0 for l in lineas), "lineas": lineas}


def confirmar(db, cantidades):
    # IMMEDIATE bloquea escrituras ajenas entre la verificación y el descuento.
    db.execute("BEGIN IMMEDIATE")
    try:
        resultado = verificar(db, cantidades)
        if not resultado["ok"]:
            raise ApiError(409, "No hay stock suficiente para confirmar el pedido", **resultado)
        fecha = datetime.now().isoformat(sep=" ", timespec="minutes")
        pid = db.execute("INSERT INTO pedidos (fecha) VALUES (?)", (fecha,)).lastrowid
        for l in resultado["lineas"]:
            db.execute("UPDATE productos SET stock = stock - ? WHERE sku = ?", (l["pedido"], l["sku"]))
            db.execute("INSERT INTO pedido_items VALUES (?, ?, ?, ?)", (pid, l["sku"], l["nombre"], l["pedido"]))
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return {"id": pid, "fecha": fecha, **resultado}


def historial(db):
    # shortcut: solo los últimos 100 pedidos, paginar si el historial crece mucho.
    pedidos = [dict(r) for r in db.execute("SELECT id, fecha FROM pedidos ORDER BY id DESC LIMIT 100")]
    for p in pedidos:
        p["items"] = [dict(r) for r in db.execute(
            "SELECT sku, nombre, cantidad FROM pedido_items WHERE pedido_id = ?", (p["id"],))]
    return pedidos


def rutear(db, metodo, ruta, body):
    m = re.fullmatch(r"/api/productos/([^/]+)", ruta)
    if ruta == "/api/productos":
        if metodo == "GET":
            return 200, [dict(r) for r in db.execute("SELECT sku, nombre, stock FROM productos ORDER BY sku")]
        if metodo == "POST":
            sku = texto(body.get("sku"), "sku").upper()
            nombre = texto(body.get("nombre"), "nombre")
            stock = entero(body.get("stock"), 0, "stock")
            try:
                db.execute("INSERT INTO productos VALUES (?, ?, ?)", (sku, nombre, stock))
            except sqlite3.IntegrityError:
                raise ApiError(409, f"El SKU {sku} ya existe")
            return 201, {"sku": sku, "nombre": nombre, "stock": stock}
    elif m:
        sku = unquote(m[1])
        if metodo == "PUT":
            nombre = texto(body.get("nombre"), "nombre")
            stock = entero(body.get("stock"), 0, "stock")
            if not db.execute("UPDATE productos SET nombre = ?, stock = ? WHERE sku = ?", (nombre, stock, sku)).rowcount:
                raise ApiError(404, f"No existe el producto {sku}")
            return 200, {"sku": sku, "nombre": nombre, "stock": stock}
        if metodo == "DELETE":
            if not db.execute("DELETE FROM productos WHERE sku = ?", (sku,)).rowcount:
                raise ApiError(404, f"No existe el producto {sku}")
            return 200, {"sku": sku}
    elif ruta == "/api/verificar" and metodo == "POST":
        return 200, verificar(db, leer_items(body))
    elif ruta == "/api/pedidos":
        if metodo == "GET":
            return 200, historial(db)
        if metodo == "POST":
            return 201, confirmar(db, leer_items(body))
    raise ApiError(404, "Ruta no encontrada")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE / "static"), **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.api("GET")
        else:
            super().do_GET()

    def do_POST(self):
        self.api("POST")

    def do_PUT(self):
        self.api("PUT")

    def do_DELETE(self):
        self.api("DELETE")

    def leer_json(self):
        largo = int(self.headers.get("Content-Length") or 0)
        if largo > MAX_BODY:
            raise ApiError(413, "Solicitud demasiado grande")
        try:
            body = json.loads(self.rfile.read(largo) or b"{}")
        except ValueError:
            raise ApiError(400, "JSON inválido")
        if not isinstance(body, dict):
            raise ApiError(400, "Se esperaba un objeto JSON")
        return body

    def api(self, metodo):
        try:
            body = self.leer_json() if metodo in ("POST", "PUT") else {}
            with closing(connect()) as db:
                status, data = rutear(db, metodo, urlsplit(self.path).path, body)
        except ApiError as e:
            status, data = e.status, {"error": str(e), **e.data}
        except Exception as e:
            self.log_error("Error interno: %r", e)
            status, data = 500, {"error": "Error interno del servidor"}
        salida = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(salida)))
        self.end_headers()
        self.wfile.write(salida)


def main():
    init_db()
    url = f"http://{HOST}:{PORT}"
    try:
        servidor = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        print(f"El puerto {PORT} está ocupado; probablemente Verifica Stock ya está abierto en {url}")
        webbrowser.open(url)
        sys.exit(1)
    print(f"Verifica Stock funcionando en {url}  (Ctrl+C o cerrar esta ventana para detenerlo)")
    webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
