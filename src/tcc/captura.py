from gpiozero import MotionSensor
from picamera2 import Picamera2
from time import sleep
from pathlib import Path
from datetime import datetime, timedelta

FOTOS_DIR = Path.home() / "fotos"
FOTOS_DIR.mkdir(parents=True, exist_ok=True)

# Configurações
NUM_FOTOS = 3
DELAY_ENTRE_FOTOS = 1.5 
COOLDOWN_MINUTOS = 5

pir = MotionSensor(17)

print("Iniciando o sistema de captura...")

ultima_captura = datetime.min 

try:
    while True:
        pir.wait_for_motion()
        
        agora = datetime.now()
        
        if (agora - ultima_captura) > timedelta(minutes=COOLDOWN_MINUTOS):
            print("Movimento detectado! Iniciando sequência...")
            
            # Inicializa a câmera APENAS no momento da captura
            picam2 = Picamera2()
            picam2.configure(picam2.create_still_configuration())
            picam2.start()
            # Tempo para estabilização de exposição/branco da câmera
            sleep(2) 
            
            for i in range(NUM_FOTOS):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                caminho = FOTOS_DIR / f"foto_{timestamp}_{i}.jpg"
                picam2.capture_file(str(caminho))
                print(f"Foto {i+1} capturada.")
                sleep(DELAY_ENTRE_FOTOS)
            
            # Libera o hardware imediatamente após a sequência
            picam2.stop()
            picam2.close()
            
            ultima_captura = datetime.now()
            print("Sequência concluída. Câmera liberada. Entrando em cooldown.")
        else:
            print("Movimento detectado, mas está no período de cooldown. Ignorando.")
            sleep(1) 

except KeyboardInterrupt:
    print("\nPrograma encerrado.")
