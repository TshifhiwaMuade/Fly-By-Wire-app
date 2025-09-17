import sys
import pygame

#Setup screen and display output for pygame display
pygame.init()
W, H = 1200, 600
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Alert Demo")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont(None, 200, bold = True)
TEXT = 'ALERT! ALERT!'

RED = (255, 0, 0)
BLACK = (0, 0, 0)

show_alert = False #This will become true after space is pressed
flash = False
flash_timer = 0
FLASH_INTERVAL = 500 #milliseconds

#Sound effects
alert_sfx = pygame.mixer.Sound("alert-33762.mp3") #Alert sound affect triggered when alert system is acttive

#Lightweight script running to wait for the input of the allert, in this case simulated by the press of spacebar
  
while True:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            pygame.quit(); sys.exit()
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                pygame.quit(); sys.exit()
            if e.key == pygame.K_SPACE:
                show_alert = True
                flash_timer = pygame.time.get_ticks() #resets the timer
    
    screen.fill(BLACK) # clear each frame

    if show_alert:
        now = pygame.time.get_ticks()
        if now - flash_timer > FLASH_INTERVAL:
            flash = not flash
            flash_timer = now
        if flash:
            surf = FONT.render(TEXT, True, RED)
            rect = surf.get_rect(center=(W // 2, H // 2))
            screen.blit(surf, rect)
            alert_sfx.play()
    
    pygame.display.flip()
    clock.tick(60)