#  PokeCards — FAST-TRADE
**Escanea cartas Pokémon y encuentra su precio en TCG**

FAST-TRADE es una aplicación web que permite subir o escanear imágenes de cartas Pokémon, extraer sus datos mediante OCR y consultar su precio actual en la base de datos de [TCGPlayer](https://www.tcgplayer.com/) u otras APIs compatibles.

---

##  Contenido
- [Descripción](#-descripción)
- [Requisitos](#-requisitos)
- [Instalación rápida](#-instalación-rápida)
- [Uso en la máquina virtual (EC2)](#-uso-en-la-máquina-virtual-ec2)
- [Gestión de sesiones con tmux](#-gestión-de-sesiones-con-tmux)
- [Estructura del proyecto](#-estructura-del-proyecto)

---

##  Descripción

Este proyecto combina:
- **OCR (Reconocimiento Óptico de Caracteres)** para leer el nombre y detalles de la carta.
- **APIs de precios TCG** para obtener el valor actual.
- **Interfaz web** para escanear, visualizar y comparar precios.

El backend se ejecuta en una **máquina virtual (EC2 de AWS)** con Python y entorno virtual.

---

##  Requisitos
- Acceso SSH a la máquina virtual (clave `.pem`).
- Python 3.8+ con `venv`.
- `tmux` instalado (para mantener sesiones activas).
- Conexión a internet estable.
- Dependencias del proyecto (ver `requirements.txt`).

---

##  Instalación rápida (local)

1. Abre una terminal (PowerShell o Git Bash en Windows):
```bash
cd OneDrive\Escritorio\PROJECTS\PokeCards
```

2. Conéctate a tu servidor EC2:
```bash
ssh -i "app_credenciales_pozzzo.pem" ubuntu@ec2-52-203-146-149.compute-1.amazonaws.com
```

3. Una vez dentro de la máquina virtual:
```bash
source venv/bin/activate
cd FAST-TRADE/Codigos/
```

---

##  Uso en la máquina virtual (EC2)

Arranca el entorno del proyecto y usa `tmux` para mantener procesos corriendo incluso si te desconectas del servidor.

### Conectar a una sesión existente
```bash
tmux attach -t Pokemon
```

### Desconectarte sin detener el proceso
Dentro de `tmux`, presiona:
```
Ctrl + b  luego  d
```

### Crear una nueva sesión
Por ejemplo, para probar otro servidor:
```bash
tmux new -s server_test1
```

---

##  Gestión de sesiones con tmux

| Acción | Comando |
|--------|----------|
| Listar sesiones activas | `tmux ls` |
| Unirse a una sesión | `tmux attach -t <nombre>` |
| Crear nueva sesión | `tmux new -s <nombre>` |
| Salir sin cerrar sesión | `Ctrl + b` → `d` |
| Cerrar una sesión | `tmux kill-session -t <nombre>` |

---

##  Estructura del proyecto
```
FAST-TRADE/
├─ Codigos/              # Backend y scripts principales
│  ├─ tcg.py
│  ├─ requirements.txt
│  └─ ...
├─ web/                  # Frontend (página para escanear cartas)
├─ docs/                 # Documentación adicional
└─ README.md             # Este archivo
```

---

##  Ejemplo de flujo completo

1. En tu máquina local:
```bash
cd OneDrive\Escritorio\PROJECTS\PokeCards
ssh -i "app_credenciales_pozzzo.pem" ubuntu@ec2-52-203-146-149.compute-1.amazonaws.com
```

2. Dentro de la VM:
```bash
source venv/bin/activate
cd FAST-TRADE/Codigos/
tmux new -s Pokemon
```

3. En esa sesión:
```bash
python app.py   # o el comando de inicio del servidor
```

4. Para salir sin detenerlo:
```
Ctrl + b  luego  d
```

5. Si deseas iniciar otro servidor de prueba:
```bash
tmux new -s server_test1
```

---
