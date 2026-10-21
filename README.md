# Verifica Stock

Sistema local para llevar el inventario y comprobar si un pedido puede surtirse con el stock disponible. Al confirmar un pedido, su stock se descuenta y el pedido queda en el historial.

Usa solo Python 3, sin nada que instalar aparte: `http.server` para el servidor y `sqlite3` para la base de datos.

## Cómo abrirlo

### 1. Instalar Python (una sola vez)

1. Descarga Python 3 desde [python.org/downloads](https://www.python.org/downloads/).
2. En el instalador, **marca la casilla «Add Python to PATH»** antes de pulsar *Install Now*.
3. Para comprobarlo, abre una terminal (tecla Windows → escribe `cmd`) y ejecuta:
   ```
   python --version
   ```
   Debe mostrar algo como `Python 3.12.0`.

### 2. Descargar el proyecto

- **Sin git:** en esta página, pulsa el botón verde **Code → Download ZIP** y descomprime el archivo donde quieras.
- **Con git:**
  ```
  git clone https://github.com/El1d0r/Stock-sistema.git
  ```

### 3. Iniciar

- **Windows:** haz doble clic en **`iniciar.bat`**. Se abre una ventana negra (el servidor) y el navegador en `http://127.0.0.1:8000`.
- **macOS / Linux:** desde la carpeta del proyecto ejecuta `python3 server.py`.

Mientras usas el sistema, deja abierta la ventana negra. Para apagarlo, ciérrala (o pulsa `Ctrl+C`).

## Cómo se usa

- **Inventario:** el nombre y el stock se editan directamente en la tabla (los cambios se guardan al salir del campo o al pulsar Enter). La última fila sirve para agregar productos.
- **Pedido:** elige un producto y una cantidad, pulsa *Añadir* y repite. Con *Verificar* ves si hay stock suficiente sin cambiar nada. *Confirmar pedido* descuenta el stock.
- **Historial:** lista de pedidos confirmados, del más reciente al más antiguo.

La primera vez se crea `stock.db` con 10 productos de ejemplo. Los datos se quedan en ese archivo entre usos.

## Problemas frecuentes

| Problema | Solución |
|---|---|
| «python no se reconoce como un comando» | Reinstala Python marcando «Add Python to PATH». |
| La ventana se cierra y dice que el puerto 8000 está ocupado | El sistema ya está abierto en otra ventana; usa esa o ciérrala y vuelve a iniciar. |
| Quiero empezar con el inventario vacío o reiniciar los datos | Cierra el sistema y borra `stock.db`; se vuelve a crear con los datos de ejemplo. |
| El navegador no se abre solo | Entra manualmente a `http://127.0.0.1:8000`. |

## Estructura

| Archivo | Qué hace |
|---|---|
| `iniciar.bat` | Lanzador para Windows |
| `server.py` | Servidor HTTP, API JSON y base de datos SQLite |
| `static/index.html` | Interfaz: inventario, pedido e historial |
| `test_server.py` | Pruebas de la API |

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/productos` | Lista de productos |
| POST | `/api/productos` | Crear `{sku, nombre, stock}` |
| PUT | `/api/productos/<sku>` | Editar `{nombre, stock}` |
| DELETE | `/api/productos/<sku>` | Borrar |
| POST | `/api/verificar` | `{items: [{sku, qty}]}` → detalle por producto y `ok` |
| POST | `/api/pedidos` | Confirmar pedido: descuenta stock (409 si no alcanza) |
| GET | `/api/pedidos` | Historial (últimos 100) |

## Pruebas

```
python -m unittest test_server.py
```
