import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        server.DB_PATH = Path(cls.tmp.name) / "test.db"
        server.init_db()
        cls.srv = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.url + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req) as r:
                return r.status, json.loads(r.read())
        except HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def stock(self, sku):
        return next(p["stock"] for p in self.call("GET", "/api/productos")[1] if p["sku"] == sku)

    def test_verificar(self):
        status, r = self.call("POST", "/api/verificar", {"items": [{"sku": "CON-PS5D", "qty": 2}, {"sku": "CON-XSX", "qty": 1}]})
        self.assertEqual(status, 200)
        self.assertFalse(r["ok"])
        self.assertEqual([l["faltante"] for l in r["lineas"]], [0, 1])

    def test_confirmar_descuenta_y_guarda(self):
        antes = self.stock("CTL-DS5")
        status, r = self.call("POST", "/api/pedidos", {"items": [{"sku": "CTL-DS5", "qty": 2}, {"sku": "CTL-DS5", "qty": 1}]})
        self.assertEqual(status, 201)
        self.assertEqual(self.stock("CTL-DS5"), antes - 3)
        self.assertIn(r["id"], [p["id"] for p in self.call("GET", "/api/pedidos")[1]])

    def test_sin_stock_es_409_y_no_toca_nada(self):
        antes = self.stock("JGO-FIFA")
        status, r = self.call("POST", "/api/pedidos", {"items": [{"sku": "ACC-HDST", "qty": 1}, {"sku": "JGO-FIFA", "qty": 99}]})
        self.assertEqual(status, 409)
        self.assertEqual(self.stock("JGO-FIFA"), antes)
        self.assertEqual(self.stock("ACC-HDST"), 18)

    def test_crud_y_validacion(self):
        self.assertEqual(self.call("POST", "/api/productos", {"sku": "t-1", "nombre": "Test", "stock": 4})[0], 201)
        self.assertEqual(self.call("POST", "/api/productos", {"sku": "T-1", "nombre": "Otro", "stock": 1})[0], 409)
        self.assertEqual(self.call("PUT", "/api/productos/T-1", {"nombre": "Test", "stock": -1})[0], 400)
        self.assertEqual(self.call("PUT", "/api/productos/T-1", {"nombre": "Test", "stock": 7})[0], 200)
        self.assertEqual(self.stock("T-1"), 7)
        self.assertEqual(self.call("DELETE", "/api/productos/T-1")[0], 200)
        self.assertEqual(self.call("DELETE", "/api/productos/T-1")[0], 404)
        self.assertEqual(self.call("POST", "/api/verificar", {"items": [{"sku": "CTL-DS5", "qty": 0}]})[0], 400)


if __name__ == "__main__":
    unittest.main()
