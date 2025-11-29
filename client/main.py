import pygame
import sys

from client.game import Game


def main():
    pygame.init()

    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Factorio-like")

    game = Game(screen)

    try:
        game.run()
    except KeyboardInterrupt:
        pass
    finally:
        game.cleanup()
        pygame.quit()


if __name__ == '__main__':
    main()