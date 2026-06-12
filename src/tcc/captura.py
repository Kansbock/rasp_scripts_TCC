from gpiozero import MotionSensor
from picamera2 import Picamera2
from time import sleep
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo # Biblioteca padrão do Python (3.9+)

FOTOS_DIR = Path.home() / "fotos"
FOTOS_DIR.mkdir(parents=True, exist_ok=True)

# Configurações
NUM_FOTOS = 3
DELAY_ENTRE_FOTOS = 1.5
COOLDOWN_MINUTOS = 5

# Define o fuso horário de Brasília
FUSO_BR = ZoneInfo("America/Sao_Paulo")

pir = MotionSensor(17)

print("Iniciando o sistema de captura...")

# Ajusta a data mínima com o fuso horário para permitir a matemática de tempo
ultima_captura = datetime.min.replace(tzinfo=FUSO_BR)

try:
    while True:
        pir.wait_for_motion()

        # Pega a hora atual exata em Brasília
        agora = datetime.now(FUSO_BR)

        # Verifica se o horário está entre 04:00 da manhã e 17:59 da tarde
        if 4 <= agora.hour < 18:
            
            if (agora - ultima_captura) > timedelta(minutes=COOLDOWN_MINUTOS):
                print(f"[{agora.strftime('%H:%M:%S')}] Movimento detectado! Iniciando sequência...")

                # Inicializa a câmera APENAS no momento da captura
                picam2 = Picamera2()
                picam2.configure(picam2.create_still_configuration())
                picam2.start()
                
                # Tempo para estabilização de exposição/branco da câmera
                sleep(2)

                for i in range(NUM_FOTOS):
                    timestamp = datetime.now(FUSO_BR).strftime("%Y%m%d_%H%M%S")
                    caminho = FOTOS_DIR / f"foto_{timestamp}_{i}.jpg"
                    picam2.capture_file(str(caminho))
                    print(f"Foto {i+1} capturada.")
                    sleep(DELAY_ENTRE_FOTOS)

                # Libera o hardware imediatamente após a sequência
                picam2.stop()
                picam2.close()

                ultima_captura = datetime.now(FUSO_BR)
                print("Sequência concluída. Câmera liberada. Entrando em cooldown.")
            else:
                print(f"[{agora.strftime('%H:%M:%S')}] Movimento detectado, mas está no período de cooldown. Ignorando.")
                sleep(1)
                
        else:
            # Fora do horário permitido
            print(f"[{agora.strftime('%H:%M:%S')}] Movimento detectado fora do horário de operação (04h às 18h). Ignorando.")
            # Um sleep ligeiramente maior para não flodar o terminal se algo ficar se mexendo na frente do sensor
            sleep(2)

except KeyboardInterrupt:
    print("\nPrograma encerrado.")
