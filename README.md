# rasp_scripts_TCC

Scripts para Raspberry Pi: captura de fotos por sensor de movimento (PIR) e
envio das imagens para uma API na AWS.

## Scripts

- `src/tcc/teste.py` — testa o sensor PIR (pino GPIO 17).
- `src/tcc/captura.py` — captura fotos quando há movimento e salva em `~/fotos`.
- `src/tcc/sincronizar_fotos.py` — envia as fotos para a API e apaga as locais.
- `src/tcc/guarddog_tailscale.py` — watchdog que monitora o Tailscale e reconecta
  automaticamente (reinicia o `tailscaled` e/ou executa `tailscale up`).

### Watchdog do Tailscale

Mantém o acesso remoto ativo: a cada intervalo verifica se o serviço
`tailscaled` está ativo e se o backend está `Running`; caso contrário, reinicia
o serviço e/ou executa `tailscale up`. Precisa de root para reiniciar o serviço
e reconectar (rode como serviço root ou garanta `sudo -n` sem senha). O nó já
deve ter sido autenticado uma vez.

```bash
sudo python3 src/tcc/guarddog_tailscale.py
```

Variáveis de ambiente opcionais:

- `TS_WATCHDOG_INTERVALO` — segundos entre checagens (padrão `60`).
- `TS_WATCHDOG_CMD_TIMEOUT` — timeout de cada comando externo em s (padrão `30`).
- `TS_WATCHDOG_SERVICE` — nome do serviço systemd (padrão `tailscaled`).
- `TS_WATCHDOG_PING_HOST` — host/IP Tailscale para checar conectividade real
  (vazio = desativado).

## Dependências de sistema (Raspberry Pi)

`picamera2` e `gpiozero` fazem parte do sistema e devem ser instalados via APT,
não pelo Poetry (eles dependem de bibliotecas nativas do Raspberry Pi OS):

```bash
sudo apt install -y python3-picamera2 python3-gpiozero
```

As demais dependências Python ficam no `pyproject.toml` e são instaladas com:

```bash
poetry install
```

## Configuração

Crie um arquivo `.env` na raiz do projeto com a chave da API:

```env
API_KEY=sua_chave_aqui
```

## Foco manual da câmera

Para descobrir o valor de `LensPosition` ideal antes de ajustar em `captura.py`:

```bash
libcamera-still -o foco_manual.jpg --autofocus-mode manual --lens-position 5.0
```
