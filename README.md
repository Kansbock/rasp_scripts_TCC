# rasp_scripts_TCC

Scripts para Raspberry Pi: captura de fotos por sensor de movimento (PIR) e
envio das imagens para uma API na AWS.

## Scripts

- `src/tcc/teste.py` — testa o sensor PIR (pino GPIO 17).
- `src/tcc/captura.py` — captura fotos quando há movimento e salva em `~/fotos`.
- `src/tcc/sincronizar_fotos.py` — liga o dongle 4G, envia as fotos para a API,
  apaga as locais e desliga o dongle, num ciclo diário (ver abaixo).
- `src/tcc/guarddog_tailscale.py` — watchdog que monitora o Tailscale e reconecta
  automaticamente (reinicia o `tailscaled` e/ou executa `tailscale up`).

### Sincronização das fotos (com dongle 4G)

Executa em loop o seguinte ciclo:

1. Liga a energia dos USBs do dongle 4G (via `uhubctl`).
2. Verifica repetidamente até confirmar conexão com a internet.
3. Envia as fotos de `~/fotos` para a API/bucket e apaga as enviadas.
4. Espera 1 hora (janela com o dongle ligado, útil também para acesso remoto).
5. Desliga a energia dos USBs do dongle 4G.
6. Espera 24 horas até o próximo ciclo.

Precisa de root para controlar a energia das portas USB (rode como serviço root
ou garanta `sudo -n` sem senha). Descubra a localização/porta do dongle rodando
`uhubctl` sem argumentos e configure as variáveis abaixo.

```bash
sudo DONGLE_UHUBCTL_LOCATION=1-1 DONGLE_UHUBCTL_PORTS=2 python3 src/tcc/sincronizar_fotos.py
```

Variáveis de ambiente opcionais:

- `API_URL` — endpoint de upload.
- `SYNC_PASTA_FOTOS` — pasta das fotos (padrão `~/fotos`).
- `SYNC_ESPERA_POS_ENVIO_S` — espera após o envio, dongle ligado (padrão `3600`).
- `SYNC_ESPERA_CICLO_S` — espera até o próximo ciclo (padrão `86400`).
- `SYNC_INTERNET_HOSTS` — `host:porta,host:porta` para checar a internet.
- `SYNC_INTERNET_MAX_ESPERA_S` — máximo aguardando conexão; `0` = infinito (padrão `600`).
- `DONGLE_UHUBCTL_LOCATION` / `DONGLE_UHUBCTL_PORTS` — hub e porta(s) do dongle.
- `DONGLE_ESTABILIZACAO_S` — espera após ligar o dongle (padrão `20`).

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

O controle de energia do dongle 4G (em `sincronizar_fotos.py`) usa o `uhubctl`:

```bash
sudo apt install -y uhubctl
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
