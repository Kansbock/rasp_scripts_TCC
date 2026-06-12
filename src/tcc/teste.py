from gpiozero import MotionSensor
from signal import pause

# O pino 17 é onde você conectou o sinal do PIR
pir = MotionSensor(17)

print("Teste do PIR iniciado. Mova a mão na frente do sensor!")

def detectado():
    print("Movimento detectado!")

def fim_movimento():
    print("Fim do movimento.")

pir.when_motion = detectado
pir.when_no_motion = fim_movimento

pause()
