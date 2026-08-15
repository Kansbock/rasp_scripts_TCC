import requests
import base64
import os
import time
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Configurações do barramento USB (Raspberry Pi 3B+)
USB_BUS = '1-1'
USB_DRIVER_DIR = "/sys/bus/usb/drivers/usb"

def is_usb_ligado():
    """Verifica se o barramento USB está montado (ligado) no sistema."""
    return os.path.exists(os.path.join(USB_DRIVER_DIR, USB_BUS))

def ligar_usb():
    """Liga as portas USB usando sudo para ter privilégio."""
    try:
        # Usamos 'sudo tee' para forçar a escrita como administrador no arquivo de sistema
        comando = f"echo '{USB_BUS}' | sudo tee {os.path.join(USB_DRIVER_DIR, 'bind')} > /dev/null"
        subprocess.run(comando, shell=True, check=True)
        print("Entradas USB LIGADAS.")
    except Exception as e:
        print(f"Erro ao ligar USB: {e}")

def desligar_usb():
    """Desliga as portas USB usando sudo para ter privilégio."""
    try:
        comando = f"echo '{USB_BUS}' | sudo tee {os.path.join(USB_DRIVER_DIR, 'unbind')} > /dev/null"
        subprocess.run(comando, shell=True, check=True)
        print("Entradas USB DESLIGADAS.")
    except Exception as e:
        print(f"Erro ao desligar USB: {e}")

def ligar_tailscale():
    """Inicia o serviço do Tailscale com sudo."""
    print("Iniciando serviço Tailscale...")
    try:
        # Adicionado 'sudo' na frente dos comandos de sistema
        subprocess.run(["sudo", "systemctl", "restart", "tailscaled"])
        subprocess.run(["sudo", "tailscale", "up"])
        print("Tailscale iniciado com sucesso.")
    except Exception as e:
        print(f"Erro ao iniciar Tailscale: {e}")
def is_tailscale_ligado():
    """Verifica se o serviço do Tailscale está ativo."""
    try:
        resultado = subprocess.run(
            ["systemctl", "is-active", "tailscaled"], 
            capture_output=True, text=True
        )
        return resultado.stdout.strip() == "active"
    except Exception:
        return False

def enviar_e_apagar_fotos(pasta_origem):
    url = "https://7o79fzgdc0.execute-api.us-east-1.amazonaws.com/prod/upload"
    api_key = os.getenv('API_KEY')
    origem = Path(pasta_origem)

    # Filtra apenas arquivos .jpg e .jpeg
    arquivos = list(origem.glob("*.jpg")) + list(origem.glob("*.jpeg"))

    if not arquivos:
        return

    print(f"Encontradas {len(arquivos)} fotos. Iniciando envio...")

    for arquivo in arquivos:
        try:
            with open(arquivo, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

            payload = {
                "image_data": encoded_string,
                "file_name": arquivo.name
            }
            headers = {"x-api-key": api_key, "Content-Type": "application/json"}

            response = requests.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                print(f"Sucesso: {arquivo.name} enviado. Apagando arquivo local.")
                # Deleta o arquivo permanentemente do Raspberry Pi
                arquivo.unlink()
            else:
                print(f"Erro ao enviar {arquivo.name}: {response.status_code}")

        except Exception as e:
            print(f"Falha crítica no arquivo {arquivo.name}: {e}")

# === INÍCIO DO PROGRAMA PRINCIPAL ===

pasta_fotos = Path.home() / "fotos"
print(f"Monitorando a pasta: {pasta_fotos}")
print("Sistema de automação com controle de USB e Tailscale iniciado.")

while True:
    hora_atual = datetime.now().hour
    horario_formatado = time.strftime('%H:%M:%S')

    # Verifica se a hora está entre 18:00 e 20:59
    if 12 <= hora_atual < 21:
        print(f"[{horario_formatado}] Dentro do horário de envio (18h-21h).")
        
        # O USB está desligado?
        if not is_usb_ligado():
            ligar_usb()
            print("Aguardando 5 minutos para estabilização de hardware e rede...")
            time.sleep(300) # Pausa de 5 minutos (300 segundos)
            ligar_tailscale()
            
        # O USB já está ligado?
        else:
            if not is_tailscale_ligado():
                ligar_tailscale()
        
        # Segue o fluxo padrão de enviar fotos
        enviar_e_apagar_fotos(pasta_fotos)

    # Fora do horário (21:00 às 17:59)
    else:
        # Se os USBs ainda estiverem ligados, desliga
        if is_usb_ligado():
            print(f"[{horario_formatado}] Fora do horário. Desligando USBs...")
            desligar_usb()
        else:
            print(f"[{horario_formatado}] Modo de economia: USBs já estão desligados.")

    # Pausa antes do próximo ciclo de checagem principal
    print("Aguardando 60 segundos para a próxima checagem global...\n")
    time.sleep(60)
