import math
import time
from datetime import datetime

import RPi.GPIO as GPIO
import board
import busio
import pygame
import adafruit_ssd1306

TRIG_PIN = 23
ECHO_PIN = 24
LED_PIN = 18

OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_ADDRESS = 0x3C

ALERT_DISTANCE = 20.0
MAX_DISTANCE = 200.0

# Sensor is fixed in the photographed hardware.
# The GUI therefore shows detections straight ahead.
RADAR_ANGLE = -90.0

GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(ECHO_PIN, GPIO.IN)
GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)

i2c = busio.I2C(board.SCL, board.SDA)
oled = adafruit_ssd1306.SSD1306_I2C(
    OLED_WIDTH, OLED_HEIGHT, i2c, addr=OLED_ADDRESS
)

oled.fill(0)
oled.show()


def get_distance():
    GPIO.output(TRIG_PIN, GPIO.LOW)
    time.sleep(0.0002)

    GPIO.output(TRIG_PIN, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(TRIG_PIN, GPIO.LOW)

    timeout = time.monotonic() + 0.03
    while GPIO.input(ECHO_PIN) == GPIO.LOW:
        if time.monotonic() > timeout:
            return None

    pulse_start = time.monotonic()

    timeout = time.monotonic() + 0.03
    while GPIO.input(ECHO_PIN) == GPIO.HIGH:
        if time.monotonic() > timeout:
            return None

    pulse_end = time.monotonic()
    distance = (pulse_end - pulse_start) * 17150.0

    if distance < 2.0 or distance > MAX_DISTANCE:
        return None

    return round(distance, 1)


def update_oled(distance, alert):
    oled.fill(0)
    oled.text("Radar System", 4, 2, 1)

    if distance is None:
        oled.text("Dist: --.- cm", 4, 18, 1)
    else:
        oled.text(f"Dist: {distance:.1f} cm", 4, 18, 1)

    oled.text(datetime.now().strftime("%H:%M:%S"), 4, 34, 1)
    oled.text("ALERT!" if alert else "NORMAL", 4, 50, 1)
    oled.show()


pygame.init()

WIDTH = 900
HEIGHT = 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Raspberry Pi Ultrasonic Radar")
clock = pygame.time.Clock()

font = pygame.font.Font(None, 30)
small_font = pygame.font.Font(None, 24)

CENTER_X = WIDTH // 2
CENTER_Y = HEIGHT - 65
RADAR_RADIUS = 450


def polar_to_xy(distance, angle_degrees):
    radius = min(distance, MAX_DISTANCE) / MAX_DISTANCE * RADAR_RADIUS
    angle = math.radians(angle_degrees)
    return (
        int(CENTER_X + radius * math.cos(angle)),
        int(CENTER_Y + radius * math.sin(angle))
    )


def draw_radar(distance, alert):
    screen.fill((0, 0, 0))

    for fraction in (0.25, 0.50, 0.75, 1.0):
        radius = int(RADAR_RADIUS * fraction)
        pygame.draw.arc(
            screen, (0, 100, 0),
            (CENTER_X-radius, CENTER_Y-radius, radius*2, radius*2),
            math.pi, 2*math.pi, 2
        )

    pygame.draw.line(
        screen, (0, 120, 0),
        (CENTER_X-RADAR_RADIUS, CENTER_Y),
        (CENTER_X+RADAR_RADIUS, CENTER_Y), 2
    )

    end_x, end_y = polar_to_xy(MAX_DISTANCE, RADAR_ANGLE)
    pygame.draw.line(
        screen, (0, 255, 0),
        (CENTER_X, CENTER_Y), (end_x, end_y), 3
    )

    if distance is not None:
        x, y = polar_to_xy(distance, RADAR_ANGLE)
        pygame.draw.circle(
            screen,
            (255, 0, 0) if alert else (255, 180, 0),
            (x, y),
            10 if alert else 7
        )

    screen.blit(font.render("RADAR SYSTEM", True, (0, 255, 0)), (20, 20))

    text = "Distance: --.- cm" if distance is None else f"Distance: {distance:.1f} cm"
    screen.blit(small_font.render(text, True, (255, 255, 255)), (20, 55))

    status = "ALERT" if alert else "NORMAL"
    status_color = (255, 0, 0) if alert else (0, 255, 0)
    screen.blit(font.render(status, True, status_color), (WIDTH-130, 25))

    screen.blit(
        small_font.render(datetime.now().strftime("%H:%M:%S"), True, (255,255,255)),
        (WIDTH-130, 60)
    )

    pygame.display.flip()


running = True
distance = None
alert = False
last_measurement = 0.0

try:
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        now = time.monotonic()

        if now - last_measurement >= 0.10:
            distance = get_distance()
            last_measurement = now

            alert = distance is not None and distance <= ALERT_DISTANCE

            GPIO.output(LED_PIN, GPIO.HIGH if alert else GPIO.LOW)
            update_oled(distance, alert)

        draw_radar(distance, alert)
        clock.tick(60)

finally:
    GPIO.output(LED_PIN, GPIO.LOW)
    GPIO.cleanup()
    oled.fill(0)
    oled.show()
    pygame.quit()
