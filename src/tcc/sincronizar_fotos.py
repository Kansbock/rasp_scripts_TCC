import boto3
import os
from pathlib import Path
from dotenv import load_dotenv

# Aponta o caminho exato do arquivo .env
caminho_env = Path.home() / ".env"

# Carrega as variáveis de ambiente
load_dotenv(dotenv_path=caminho_env)

# Puxa as credenciais do sistema
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_SESSION_TOKEN = os.getenv('AWS_SESSION_TOKEN')
AWS_REGION = os.getenv('AWS_REGION', 'sa-east-1')

NOME_DO_BUCKET = 'comedouro-aves-fotos-tcc-2026'

# Inicializa o S3 com as variáveis importadas
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    aws_session_token=AWS_SESSION_TOKEN,
    region_name=AWS_REGION
)

FOTOS_DIR = Path.home() / "fotos"

def sincronizar_fotos():
    if not FOTOS_DIR.exists():
        print(f"A pasta {FOTOS_DIR} não existe.")
        return

    fotos = list(FOTOS_DIR.glob("*.jpg"))
    
    if not fotos:
        print("Nenhuma foto nova para enviar.")
        return

    print(f"Encontradas {len(fotos)} fotos para upload.")

    for foto in fotos:
        print(f"Enviando {foto.name}...")
        try:
            s3_client.upload_file(str(foto), NOME_DO_BUCKET, foto.name)
            foto.unlink()
            print(f"Sucesso! {foto.name} enviada e apagada localmente.")
        except Exception as e:
            print(f"Erro ao enviar {foto.name}: {e}")
            print("O arquivo será mantido para a próxima tentativa.")

if __name__ == "__main__":
    sincronizar_fotos()