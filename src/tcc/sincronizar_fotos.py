import base64
import json
import os
import subprocess
import tempfile
import time

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# CARREGA CONFIGURAÇÕES
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURAÇÕES
# ============================================================

USB_BUS = "1-1"
USB_DRIVER_DIR = "/sys/bus/usb/drivers/usb"

HORA_INICIO = 18
HORA_FIM = 21

# Máximo de uploads simultâneos
BATCH_SIZE = 5

# Pasta das fotos
PASTA_FOTOS = Path.home() / "fotos"

# API
API_URL = (
    "https://7o79fzgdc0.execute-api.us-east-1.amazonaws.com"
    "/prod/upload"
)


# ============================================================
# USB
# ============================================================

def is_usb_ligado():
    """
    Verifica se o barramento USB está ligado.
    """

    return os.path.exists(
        os.path.join(
            USB_DRIVER_DIR,
            USB_BUS
        )
    )


def ligar_usb():
    """
    Liga o barramento USB.
    """

    try:
        comando = (
            f"echo '{USB_BUS}' | "
            f"sudo tee "
            f"{os.path.join(USB_DRIVER_DIR, 'bind')} "
            "> /dev/null"
        )

        subprocess.run(
            comando,
            shell=True,
            check=True
        )

        print("Entradas USB LIGADAS.")

    except Exception as e:
        print(f"Erro ao ligar USB: {e}")


def desligar_usb():
    """
    Desliga o barramento USB.
    """

    try:
        comando = (
            f"echo '{USB_BUS}' | "
            f"sudo tee "
            f"{os.path.join(USB_DRIVER_DIR, 'unbind')} "
            "> /dev/null"
        )

        subprocess.run(
            comando,
            shell=True,
            check=True
        )

        print("Entradas USB DESLIGADAS.")

    except Exception as e:
        print(f"Erro ao desligar USB: {e}")


# ============================================================
# ENVIA UMA FOTO
# ============================================================

def enviar_foto(arquivo, api_key):
    """
    Envia uma foto usando curl -6.

    O JSON fica em arquivo temporário para evitar:
        [Errno 7] Argument list too long

    A foto só é apagada depois de HTTP 200.
    """

    temp_path = None

    try:

        print(
            f"[UPLOAD] Iniciando: {arquivo.name}"
        )

        # ----------------------------------------------------
        # LER FOTO
        # ----------------------------------------------------

        print(
            f"[UPLOAD] Lendo: {arquivo.name}"
        )

        with open(arquivo, "rb") as image_file:
            dados = image_file.read()

        print(
            f"[UPLOAD] Arquivo lido: "
            f"{len(dados)} bytes"
        )

        # ----------------------------------------------------
        # BASE64
        # ----------------------------------------------------

        encoded_string = base64.b64encode(
            dados
        ).decode("utf-8")

        print(
            f"[UPLOAD] Base64 gerado: "
            f"{len(encoded_string)} caracteres"
        )

        # ----------------------------------------------------
        # MONTA JSON
        # ----------------------------------------------------

        payload = {
            "image_data": encoded_string,
            "file_name": arquivo.name
        }

        # ----------------------------------------------------
        # CRIA JSON TEMPORÁRIO
        # ----------------------------------------------------

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False
        ) as temp_file:

            json.dump(
                payload,
                temp_file,
                ensure_ascii=False
            )

            temp_path = temp_file.name

        print(
            "[UPLOAD] JSON temporário criado."
        )

        # ----------------------------------------------------
        # CURL IPV6
        # ----------------------------------------------------

        print(
            f"[UPLOAD] Enviando "
            f"{arquivo.name} via curl -6..."
        )

        inicio = time.time()

        resultado = subprocess.run(
            [
                "curl",

                "-6",
                "--silent",
                "--show-error",

                # Timeout de conexão
                "--connect-timeout",
                "30",

                # Timeout total
                "--max-time",
                "180",

                "-X",
                "POST",

                "-H",
                f"x-api-key: {api_key}",

                "-H",
                "Content-Type: application/json",

                # IMPORTANTE:
                # o JSON vem do arquivo, não da linha de comando
                "--data-binary",
                f"@{temp_path}",

                # Retorna o HTTP status
                "-w",
                "\nHTTP_STATUS:%{http_code}",

                API_URL
            ],
            capture_output=True,
            text=True
        )

        tempo = time.time() - inicio

        print(
            f"[UPLOAD] {arquivo.name}: "
            f"finalizado em {tempo:.2f}s"
        )

        # ----------------------------------------------------
        # ERROS DO CURL
        # ----------------------------------------------------

        stdout = resultado.stdout.strip()
        stderr = resultado.stderr.strip()

        if stderr:
            print(
                f"[CURL] {arquivo.name}: {stderr}"
            )

        if stdout:
            print(
                f"[CURL] Resposta: {stdout}"
            )

        # ----------------------------------------------------
        # PEGA HTTP STATUS
        # ----------------------------------------------------

        status_code = None

        if "HTTP_STATUS:" in stdout:

            try:

                status_text = (
                    stdout
                    .split("HTTP_STATUS:")[-1]
                    .strip()
                )

                status_code = int(
                    status_text
                )

            except ValueError:

                status_code = None

        # ----------------------------------------------------
        # SUCESSO
        # ----------------------------------------------------

        if (
            resultado.returncode == 0
            and status_code == 200
        ):

            print(
                f"[OK] {arquivo.name} "
                "enviado com sucesso!"
            )

            # Apaga a foto somente após sucesso
            try:

                arquivo.unlink()

                print(
                    f"[OK] {arquivo.name} "
                    "apagado localmente."
                )

            except Exception as e:

                print(
                    f"[AVISO] Upload teve sucesso, "
                    f"mas não foi possível apagar "
                    f"{arquivo.name}: {e}"
                )

            return True

        # ----------------------------------------------------
        # ERRO
        # ----------------------------------------------------

        print(
            f"[ERRO] Upload falhou: "
            f"{arquivo.name}"
        )

        print(
            f"[ERRO] Código HTTP: "
            f"{status_code}"
        )

        return False

    except subprocess.TimeoutExpired:

        print(
            f"[TIMEOUT] {arquivo.name}: "
            "curl excedeu 180 segundos."
        )

        return False

    except Exception as e:

        print(
            f"[ERRO CRÍTICO] "
            f"{arquivo.name}: {e}"
        )

        return False

    finally:

        # ====================================================
        # APAGA JSON TEMPORÁRIO
        # ====================================================

        if temp_path:

            try:

                if os.path.exists(temp_path):

                    os.unlink(temp_path)

                    print(
                        "[TEMP] Arquivo JSON "
                        "temporário removido."
                    )

            except Exception as e:

                print(
                    "[AVISO] Não foi possível "
                    f"remover JSON temporário: {e}"
                )


# ============================================================
# ENVIA UM BATCH
# ============================================================

def enviar_batch(arquivos, api_key):

    print()
    print("=" * 60)

    print(
        f"INICIANDO BATCH COM "
        f"{len(arquivos)} REQUISIÇÕES"
    )

    print(
        f"Uploads simultâneos: "
        f"{BATCH_SIZE}"
    )

    print("=" * 60)

    sucessos = 0
    erros = 0

    with ThreadPoolExecutor(
        max_workers=BATCH_SIZE
    ) as executor:

        futures = {}

        for arquivo in arquivos:

            future = executor.submit(
                enviar_foto,
                arquivo,
                api_key
            )

            futures[future] = arquivo

        for future in as_completed(futures):

            arquivo = futures[future]

            try:

                sucesso = future.result()

                if sucesso:
                    sucessos += 1
                else:
                    erros += 1

            except Exception as e:

                erros += 1

                print(
                    f"[THREAD ERROR] "
                    f"{arquivo.name}: {e}"
                )

    print()
    print("=" * 60)

    print("BATCH FINALIZADO")

    print(
        f"Sucessos: {sucessos}"
    )

    print(
        f"Erros:    {erros}"
    )

    print("=" * 60)

    print()


# ============================================================
# BUSCA FOTOS E ENVIA
# ============================================================

def enviar_e_apagar_fotos(pasta_origem):

    # --------------------------------------------------------
    # API KEY
    # --------------------------------------------------------

    api_key = os.getenv("API_KEY")

    if not api_key:

        print(
            "ERRO: API_KEY não encontrada."
        )

        print(
            "Verifique o arquivo .env."
        )

        return

    # --------------------------------------------------------
    # PASTA
    # --------------------------------------------------------

    origem = Path(pasta_origem)

    if not origem.exists():

        print(
            f"ERRO: pasta não encontrada: "
            f"{origem}"
        )

        return

    # --------------------------------------------------------
    # FOTOS
    # --------------------------------------------------------

    arquivos = []

    arquivos.extend(
        origem.glob("*.jpg")
    )

    arquivos.extend(
        origem.glob("*.jpeg")
    )

    arquivos.extend(
        origem.glob("*.JPG")
    )

    arquivos.extend(
        origem.glob("*.JPEG")
    )

    if not arquivos:

        print(
            "Nenhuma foto encontrada."
        )

        return

    print(
        f"Encontradas "
        f"{len(arquivos)} fotos."
    )

    print(
        f"Enviando em batches de "
        f"{BATCH_SIZE}."
    )

    # --------------------------------------------------------
    # CALCULA BATCHES
    # --------------------------------------------------------

    total_batches = (
        (
            len(arquivos)
            + BATCH_SIZE
            - 1
        )
        // BATCH_SIZE
    )

    # --------------------------------------------------------
    # ENVIA BATCHES
    # --------------------------------------------------------

    for inicio in range(
        0,
        len(arquivos),
        BATCH_SIZE
    ):

        batch = arquivos[
            inicio:
            inicio + BATCH_SIZE
        ]

        numero_batch = (
            inicio // BATCH_SIZE
        ) + 1

        print()
        print(
            f">>> BATCH "
            f"{numero_batch}/{total_batches}"
        )

        enviar_batch(
            batch,
            api_key
        )


# ============================================================
# INÍCIO DO PROGRAMA
# ============================================================

print("=" * 60)

print(
    "SISTEMA DE AUTOMAÇÃO - COMEDOURO TCC"
)

print("=" * 60)

print(
    f"Monitorando: {PASTA_FOTOS}"
)

print(
    f"Horário de envio: "
    f"{HORA_INICIO:02d}:00 até "
    f"{HORA_FIM:02d}:00"
)

print(
    f"Batch de requisições: "
    f"{BATCH_SIZE}"
)

print(
    "Método de upload: curl -6"
)

print(
    "JSON enviado através de arquivo temporário."
)

print(
    "Controle USB ativo."
)

print("=" * 60)


# ============================================================
# LOOP PRINCIPAL
# ============================================================

while True:

    try:

        hora_atual = datetime.now().hour

        horario_formatado = time.strftime(
            "%H:%M:%S"
        )

        # ====================================================
        # HORÁRIO DE ENVIO
        # ====================================================

        if (
            HORA_INICIO
            <= hora_atual
            < HORA_FIM
        ):

            print(
                f"[{horario_formatado}] "
                "Dentro do horário de envio "
                "(18h-21h)."
            )

            # ------------------------------------------------
            # USB
            # ------------------------------------------------

            if not is_usb_ligado():

                print(
                    "USBs estão desligados."
                )

                ligar_usb()

                print(
                    "Aguardando 5 minutos "
                    "para estabilização de "
                    "hardware e rede..."
                )

                time.sleep(300)

            else:

                print(
                    "USBs já estão ligados."
                )

            # ------------------------------------------------
            # ENVIO
            # ------------------------------------------------

            enviar_e_apagar_fotos(
                PASTA_FOTOS
            )

        # ====================================================
        # FORA DO HORÁRIO
        # ====================================================

        else:

            if is_usb_ligado():

                print(
                    f"[{horario_formatado}] "
                    "Fora do horário."
                )

                print(
                    "Desligando USBs..."
                )

                desligar_usb()

            else:

                print(
                    f"[{horario_formatado}] "
                    "Modo de economia: "
                    "USBs já estão desligados."
                )

        # ----------------------------------------------------
        # ESPERA
        # ----------------------------------------------------

        print(
            "Aguardando 60 segundos "
            "para a próxima checagem global...\n"
        )

        time.sleep(60)

    except KeyboardInterrupt:

        print(
            "\nPrograma interrompido."
        )

        break

    except Exception as e:

        print(
            f"Erro inesperado no "
            f"loop principal: {e}"
        )

        print(
            "Aguardando 60 segundos "
            "antes de tentar novamente..."
        )

        time.sleep(60)
