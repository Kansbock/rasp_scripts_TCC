"""Sincroniza as fotos com o bucket na AWS controlando o dongle 4G.

Ciclo executado em loop:

  1. Liga a energia dos USBs do dongle 4G (via uhubctl).
  2. Verifica repetidamente ate ter certeza de que ha conexao com a internet.
  3. Envia as fotos de ~/fotos para a API/bucket e apaga as locais enviadas.
  4. Espera 1 hora (janela com o dongle ligado, util tambem p/ acesso remoto).
  5. Desliga a energia dos USBs do dongle 4G.
  6. Espera 24 horas ate o proximo ciclo.

O controle de energia usa `uhubctl`, que precisa de root e de um hub USB com
chaveamento de energia. Descubra a localizacao/porta do seu dongle rodando
`uhubctl` (sem argumentos) e configure DONGLE_UHUBCTL_LOCATION / _PORTS.
Instale com `sudo apt install uhubctl`.

Configuracao por variaveis de ambiente (todas opcionais, com padroes):
  API_KEY                      (obrigatoria) chave da API, via .env.
  API_URL                      Endpoint de upload.
  SYNC_PASTA_FOTOS             Pasta das fotos (padrao ~/fotos).
  SYNC_ESPERA_POS_ENVIO_S      Espera apos o envio, dongle ligado (padrao 3600).
  SYNC_ESPERA_CICLO_S          Espera ate o proximo ciclo (padrao 86400).
  SYNC_INTERNET_HOSTS          "host:porta,host:porta" para checar a internet.
  SYNC_INTERNET_TIMEOUT_S      Timeout por checagem (padrao 10).
  SYNC_INTERNET_INTERVALO_S    Espera entre checagens (padrao 10).
  SYNC_INTERNET_MAX_ESPERA_S   Maximo aguardando conexao; 0 = infinito (padrao 600).
  DONGLE_UHUBCTL_LOCATION      Localizacao do hub (ex.: 1-1).
  DONGLE_UHUBCTL_PORTS         Porta(s) do dongle (ex.: 2).
  DONGLE_ESTABILIZACAO_S       Espera apos ligar o dongle (padrao 20).
  SYNC_CMD_TIMEOUT_S           Timeout de comandos externos (padrao 30).
"""

from __future__ import annotations

import base64
import os
import shutil
import socket
import subprocess
from pathlib import Path
from time import monotonic, sleep, strftime

import requests
from dotenv import load_dotenv

load_dotenv()

# --- Configuracoes (sobrescritiveis por variaveis de ambiente) ---
API_URL = os.getenv(
    "API_URL",
    "https://7o79fzgdc0.execute-api.us-east-1.amazonaws.com/prod/upload",
)
PASTA_FOTOS = Path(os.getenv("SYNC_PASTA_FOTOS", str(Path.home() / "fotos")))

ESPERA_POS_ENVIO_S = int(os.getenv("SYNC_ESPERA_POS_ENVIO_S", str(60 * 60)))         # 1 hora
ESPERA_CICLO_S = int(os.getenv("SYNC_ESPERA_CICLO_S", str(24 * 60 * 60)))            # 24 horas

INTERNET_TIMEOUT_S = int(os.getenv("SYNC_INTERNET_TIMEOUT_S", "10"))
INTERNET_INTERVALO_S = int(os.getenv("SYNC_INTERNET_INTERVALO_S", "10"))
INTERNET_MAX_ESPERA_S = int(os.getenv("SYNC_INTERNET_MAX_ESPERA_S", str(10 * 60)))   # 0 = infinito

DONGLE_LOCATION = os.getenv("DONGLE_UHUBCTL_LOCATION", "").strip()
DONGLE_PORTS = os.getenv("DONGLE_UHUBCTL_PORTS", "").strip()
DONGLE_ESTABILIZACAO_S = int(os.getenv("DONGLE_ESTABILIZACAO_S", "20"))

CMD_TIMEOUT_S = int(os.getenv("SYNC_CMD_TIMEOUT_S", "30"))

UHUBCTL_BIN = shutil.which("uhubctl")
SUDO_BIN = shutil.which("sudo")


def _parse_hosts(valor: str) -> list[tuple[str, int]]:
    hosts: list[tuple[str, int]] = []
    for item in valor.split(","):
        item = item.strip()
        if not item:
            continue
        host, _, porta = item.partition(":")
        hosts.append((host, int(porta) if porta else 53))
    return hosts


INTERNET_HOSTS = _parse_hosts(os.getenv("SYNC_INTERNET_HOSTS", "1.1.1.1:53,8.8.8.8:53"))


def log(msg: str) -> None:
    print(f"[{strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def _is_root() -> bool:
    geteuid = getattr(os, "geteuid", None)
    return geteuid() == 0 if geteuid else False


def _privileged(cmd: list[str]) -> list[str]:
    """Prefixa o comando com `sudo -n` quando nao estamos como root."""
    if _is_root():
        return cmd
    if SUDO_BIN:
        return [SUDO_BIN, "-n", *cmd]
    return cmd


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=CMD_TIMEOUT_S, check=False
    )


def _uhubctl(acao: str) -> bool:
    """Executa `uhubctl -a <acao>` (on/off) nas portas configuradas."""
    if not UHUBCTL_BIN:
        log("AVISO: 'uhubctl' nao encontrado; pulando o controle de energia do dongle.")
        return False
    cmd = [UHUBCTL_BIN, "-a", acao]
    if DONGLE_LOCATION:
        cmd += ["-l", DONGLE_LOCATION]
    if DONGLE_PORTS:
        cmd += ["-p", DONGLE_PORTS]
    if not DONGLE_LOCATION and not DONGLE_PORTS:
        log("AVISO: DONGLE_UHUBCTL_LOCATION/PORTS nao definidos; uhubctl afetara todas as portas suportadas.")
    try:
        resultado = run(_privileged(cmd))
    except subprocess.TimeoutExpired:
        log(f"Timeout ao executar 'uhubctl -a {acao}'.")
        return False
    if resultado.returncode == 0:
        return True
    log(f"Falha em 'uhubctl -a {acao}' (rc={resultado.returncode}): {resultado.stderr.strip()}")
    return False


def ligar_dongle() -> None:
    log("Ligando a energia dos USBs do dongle 4G...")
    if _uhubctl("on"):
        log("Dongle ligado.")
    if DONGLE_ESTABILIZACAO_S > 0:
        log(f"Aguardando {DONGLE_ESTABILIZACAO_S}s para o modem registrar na rede...")
        sleep(DONGLE_ESTABILIZACAO_S)


def desligar_dongle() -> None:
    log("Desligando a energia dos USBs do dongle 4G...")
    if _uhubctl("off"):
        log("Dongle desligado.")


def tem_internet() -> bool:
    """True se conseguir abrir conexao TCP com algum dos hosts de checagem."""
    for host, porta in INTERNET_HOSTS:
        try:
            with socket.create_connection((host, porta), timeout=INTERNET_TIMEOUT_S):
                return True
        except OSError:
            continue
    return False


def aguardar_internet() -> bool:
    """Verifica repetidamente ate confirmar conexao. Retorna True se conectou."""
    log("Verificando conexao com a internet...")
    inicio = monotonic()
    tentativa = 0
    while True:
        tentativa += 1
        if tem_internet():
            log(f"Internet confirmada (tentativa {tentativa}).")
            return True
        decorrido = monotonic() - inicio
        if INTERNET_MAX_ESPERA_S and decorrido >= INTERNET_MAX_ESPERA_S:
            log(f"Sem internet apos {int(decorrido)}s e {tentativa} tentativas; desistindo deste ciclo.")
            return False
        log(f"Ainda sem internet (tentativa {tentativa}); nova checagem em {INTERNET_INTERVALO_S}s...")
        sleep(INTERNET_INTERVALO_S)


def enviar_e_apagar_fotos(pasta_origem: Path, api_key: str) -> None:
    arquivos = list(pasta_origem.glob("*.jpg")) + list(pasta_origem.glob("*.jpeg"))
    if not arquivos:
        log("Nenhuma foto para enviar.")
        return

    log(f"Encontradas {len(arquivos)} fotos. Iniciando envio...")
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    for arquivo in arquivos:
        try:
            with open(arquivo, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

            payload = {"image_data": encoded_string}
            response = requests.post(API_URL, json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                log(f"Sucesso: {arquivo.name} enviado. Apagando arquivo local.")
                arquivo.unlink()
            else:
                log(f"Erro ao enviar {arquivo.name}: HTTP {response.status_code}")
        except Exception as e:
            log(f"Falha critica no arquivo {arquivo.name}: {e}")


def main() -> None:
    api_key = os.getenv("API_KEY")
    if not api_key:
        log("ERRO: variavel API_KEY nao definida. Configure o arquivo .env.")
        raise SystemExit(1)

    if not UHUBCTL_BIN:
        log("AVISO: 'uhubctl' nao encontrado. Instale com 'sudo apt install uhubctl'.")
    if not _is_root() and not SUDO_BIN:
        log("AVISO: sem root e sem sudo; o uhubctl pode falhar por permissao.")

    PASTA_FOTOS.mkdir(parents=True, exist_ok=True)
    log(f"Sincronizador iniciado. Pasta monitorada: {PASTA_FOTOS}")

    try:
        while True:
            try:
                # 1) Liga os USBs do dongle 4G.
                ligar_dongle()

                # 2) Garante que ha internet antes de tentar enviar.
                if aguardar_internet():
                    # 3) Envia as fotos para o bucket.
                    enviar_e_apagar_fotos(PASTA_FOTOS, api_key)
                else:
                    log("Envio adiado: sem conexao neste ciclo.")

                # 4) Mantem o dongle ligado por 1 hora.
                log(f"Aguardando {ESPERA_POS_ENVIO_S // 60} min com o dongle ligado...")
                sleep(ESPERA_POS_ENVIO_S)
            except Exception as e:  # nunca deixar o ciclo derrubar o servico
                log(f"Erro inesperado no ciclo: {e}")
            finally:
                # 5) Desliga os USBs do dongle 4G (mesmo apos erro).
                desligar_dongle()

            # 6) Espera 24 horas ate o proximo ciclo.
            log(f"Aguardando {ESPERA_CICLO_S // 3600}h ate o proximo ciclo...")
            sleep(ESPERA_CICLO_S)
    except KeyboardInterrupt:
        log("Sincronizador encerrado.")


if __name__ == "__main__":
    main()
