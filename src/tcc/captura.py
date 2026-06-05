from gpiozero import MotionSensor
from picamera2 import Picamera2
from time import sleep
from pathlib import Path
from datetime import datetime

FOTOS_DIR = Path.home() / "fotos"
FOTOS_DIR.mkdir(parents=True, exist_ok=True)

COOLDOWN = 5 * 60  # 5 minutos em segundos

pir = MotionSensor(17)

picam2 = Picamera2()
picam2.configure(picam2.create_still_configuration())
picam2.start()

print("Iniciando o sensor PIR. Aguarde 2 segundos para calibração...")
sleep(2)
print(f"Pronto! Fotos serão salvas em: {FOTOS_DIR}")
print("Aguardando movimento...")

try:
    while True:
        pir.wait_for_motion()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho = FOTOS_DIR / f"foto_{timestamp}.jpg"
        picam2.capture_file(str(caminho))
        print(f"Movimento detectado! Foto salva: {caminho}")

        # Durante este sleep, nenhum sinal do PIR é processado (cooldown de 5 min)
        print("Cooldown de 5 minutos iniciado. Sinais serão ignorados.")
        sleep(COOLDOWN)
        print("Cooldown encerrado. Aguardando movimento...")

except KeyboardInterrupt:
    print("\nPrograma encerrado.")
finally:
    picam2.stop()