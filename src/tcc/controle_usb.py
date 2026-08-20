import schedule
import time

# O barramento principal do Raspberry Pi 3B+ geralmente é '1-1'
USB_BUS = '1-1' 

def set_usb_status(enable=True):
    """Ativa ou desativa o barramento USB."""
    action = "bind" if enable else "unbind"
    path = f"/sys/bus/usb/drivers/usb/{action}"
    
    try:
        with open(path, 'w') as f:
            f.write(USB_BUS)
            
        estado = "LIGADAS" if enable else "DESLIGADAS"
        print(f"[{time.strftime('%H:%M:%S')}] Entradas USB {estado}.")
        
    except PermissionError:
        print("Erro: Permissão negada. Você executou o script com 'sudo'?")
    except Exception as e:
        print(f"Erro inesperado ao alterar status do USB: {e}")

def ligar_usb():
    set_usb_status(enable=True)

def desligar_usb():
    set_usb_status(enable=False)

# Configuração dos horários agendados
schedule.every().day.at("14:30").do(ligar_usb)
schedule.every().day.at("15:00").do(desligar_usb)

print("Script de controle USB iniciado.")

# --- ALTERAÇÃO AQUI: Desliga o USB imediatamente ao iniciar ---
print("Executando desligamento inicial das portas USB...")
desligar_usb() 
# --------------------------------------------------------------

print("\nAguardando os horários programados (Liga às 14:00, Desliga às 15:00)...")
print("Pressione Ctrl+C para sair.\n")

# Loop principal para manter o script rodando e verificando o relógio
try:
    while True:
        schedule.run_pending()
        time.sleep(30) # Verifica a cada 30 segundos para economizar CPU
except KeyboardInterrupt:
    print("\nScript encerrado pelo usuário.")
    ligar_usb() # Garante que o USB volte a funcionar caso você pare o script manualmente
