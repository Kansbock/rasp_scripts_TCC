import requests
import base64
import os
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

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
            
            payload = {"image_data": encoded_string}
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

pasta_fotos = Path.home() / "fotos"

print(f"Monitorando a pasta: {pasta_fotos}")

while True:
    print(f"[{time.strftime('%H:%M:%S')}] Verificando novas fotos...")
    
    # Chama a função passando o caminho real
    enviar_e_apagar_fotos(pasta_fotos)
    
    print("Aguardando 60 segundos para a próxima checagem...")
    time.sleep(60)
