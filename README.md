## Ruta entrada salida servidor
entrada
ir al terminal
cd C:\Users\dpozo\OneDrive\Documentos\Servidor
ssh -i "app_credenciales_pozzzo.pem" ubuntu@ec2-54-161-223-194.compute-1.amazonaws.com
source venv/bin/activate
cd FAST-TRADE/
cd Codigos/
tmux attach -t flask_server

PARA SALIR
Salir de tmux sin cerrar Flask (presiona):
CTRL + B, luego D
