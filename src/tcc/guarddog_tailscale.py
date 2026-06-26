"""Guarddog (watchdog) para o Tailscale.

Monitora periodicamente o estado do Tailscale e tenta recuperar a conexao
automaticamente quando ela cai:

  1. Se o servico `tailscaled` estiver inativo, reinicia via systemctl.
  2. Se o backend nao estiver "Running" (ex.: Stopped, NeedsLogin, NoState),
     executa `tailscale up` para reconectar.
  3. (Opcional) Verifica conectividade real com `tailscale ping` a um peer.

Pensado para rodar continuamente no Raspberry Pi, como os demais scripts do
projeto. Precisa de privilegios de root para reiniciar o servico e, em geral,
para `tailscale up`; rode como root (servico systemd) ou garanta `sudo -n`.

O no precisa ter sido autenticado ao menos uma vez (`tailscale up` interativo
com URL de login); o watchdog so reconecta um no ja autorizado.

Configuracao via variaveis de ambiente (todas opcionais):
  TS_WATCHDOG_INTERVALO     Segundos entre checagens (padrao 60).
  TS_WATCHDOG_CMD_TIMEOUT   Timeout de cada comando externo em s (padrao 30).
  TS_WATCHDOG_SERVICE       Nome do servico systemd (padrao "tailscaled").
  TS_WATCHDOG_PING_HOST     Host/IP Tailscale para checar conectividade real
                            (vazio = desativado).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from time import sleep

# --- Configuracoes (sobrescritiveis por variaveis de ambiente) ---
INTERVALO_SEGUNDOS = int(os.getenv("TS_WATCHDOG_INTERVALO", "60"))
CMD_TIMEOUT = int(os.getenv("TS_WATCHDOG_CMD_TIMEOUT", "30"))
TAILSCALED_SERVICE = os.getenv("TS_WATCHDOG_SERVICE", "tailscaled")
PING_HOST = os.getenv("TS_WATCHDOG_PING_HOST", "").strip()

# Tempo de espera apos reiniciar o daemon antes de reavaliar o backend.
ESPERA_POS_RESTART = 5

TAILSCALE_BIN = shutil.which("tailscale")
SYSTEMCTL_BIN = shutil.which("systemctl")
SUDO_BIN = shutil.which("sudo")


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


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
        cmd,
        capture_output=True,
        text=True,
        timeout=CMD_TIMEOUT,
        check=False,
    )


def daemon_ativo() -> bool | None:
    """True/False se o tailscaled esta ativo; None se nao da para checar."""
    if not SYSTEMCTL_BIN:
        return None
    try:
        resultado = run([SYSTEMCTL_BIN, "is-active", TAILSCALED_SERVICE])
    except subprocess.TimeoutExpired:
        log("Timeout ao consultar o status do tailscaled.")
        return None
    return resultado.stdout.strip() == "active"


def reiniciar_daemon() -> None:
    if not SYSTEMCTL_BIN:
        log("systemctl indisponivel; nao e possivel reiniciar o tailscaled.")
        return
    log(f"Reiniciando o servico {TAILSCALED_SERVICE}...")
    try:
        resultado = run(_privileged([SYSTEMCTL_BIN, "restart", TAILSCALED_SERVICE]))
    except subprocess.TimeoutExpired:
        log("Timeout ao reiniciar o tailscaled.")
        return
    if resultado.returncode == 0:
        log("Servico reiniciado com sucesso.")
    else:
        log(f"Falha ao reiniciar (rc={resultado.returncode}): {resultado.stderr.strip()}")


def backend_state() -> str | None:
    """Retorna o BackendState do Tailscale (ex.: Running) ou None se indisponivel."""
    try:
        resultado = run([TAILSCALE_BIN, "status", "--json"])
    except subprocess.TimeoutExpired:
        log("Timeout ao consultar 'tailscale status'.")
        return None
    # Algumas versoes retornam rc != 0 quando parado/deslogado, mas ainda
    # imprimem JSON valido em stdout; por isso tentamos sempre parsear.
    try:
        dados = json.loads(resultado.stdout)
    except (json.JSONDecodeError, ValueError):
        if resultado.stderr.strip():
            log(f"'tailscale status' falhou: {resultado.stderr.strip()}")
        return None
    return dados.get("BackendState")


def subir_tailscale() -> None:
    log("Executando 'tailscale up' para reconectar...")
    try:
        resultado = run(_privileged([TAILSCALE_BIN, "up"]))
    except subprocess.TimeoutExpired:
        log("Timeout em 'tailscale up'.")
        return
    if resultado.returncode == 0:
        log("'tailscale up' executado com sucesso.")
    else:
        log(f"Falha em 'tailscale up' (rc={resultado.returncode}): {resultado.stderr.strip()}")


def conectividade_ok() -> bool:
    """Verifica conectividade real via `tailscale ping` quando PING_HOST esta definido."""
    if not PING_HOST:
        return True
    try:
        resultado = run(
            [TAILSCALE_BIN, "ping", "--c=1", "--until-direct=false", "--timeout=5s", PING_HOST]
        )
    except subprocess.TimeoutExpired:
        return False
    return resultado.returncode == 0


def checar_e_recuperar() -> None:
    # 1) O daemon precisa estar ativo.
    if daemon_ativo() is False:
        log("tailscaled esta inativo.")
        reiniciar_daemon()
        sleep(ESPERA_POS_RESTART)

    # 2) O backend precisa estar "Running".
    estado = backend_state()
    if estado is None:
        log("Nao foi possivel obter o estado do Tailscale; tentando reconectar.")
        subir_tailscale()
        return
    if estado != "Running":
        log(f"BackendState='{estado}' (esperado 'Running'). Reconectando...")
        subir_tailscale()
        return

    # 3) (Opcional) Conectividade real com um peer.
    if not conectividade_ok():
        log(f"BackendState=Running, mas o ping para {PING_HOST} falhou. Reconectando...")
        subir_tailscale()
        return

    detalhe = f" (ping {PING_HOST} ok)" if PING_HOST else ""
    log(f"Tailscale OK: BackendState=Running{detalhe}.")


def main() -> None:
    if not TAILSCALE_BIN:
        log("ERRO: binario 'tailscale' nao encontrado no PATH. Instale o Tailscale.")
        raise SystemExit(1)

    if not _is_root() and not SUDO_BIN:
        log(
            "AVISO: sem root e sem sudo; reiniciar o servico e 'tailscale up' "
            "podem falhar por permissao."
        )

    log(
        "Guarddog do Tailscale iniciado "
        f"(intervalo={INTERVALO_SEGUNDOS}s, servico={TAILSCALED_SERVICE}, "
        f"ping_host={PING_HOST or 'desativado'})."
    )

    try:
        while True:
            try:
                checar_e_recuperar()
            except Exception as e:  # nunca deixar o watchdog morrer por erro transitorio
                log(f"Erro inesperado durante a checagem: {e}")
            sleep(INTERVALO_SEGUNDOS)
    except KeyboardInterrupt:
        log("Guarddog encerrado.")


if __name__ == "__main__":
    main()
