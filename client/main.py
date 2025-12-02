import pygame
import sys

from client.game import Game
from client.audio import get_audio


def main():
    pygame.init()

    # Charge la configuration depuis MongoDB
    _load_config()

    # Initialise l'audio
    audio = get_audio()
    audio.load_sounds()
    audio.generate_placeholder_sounds()
    audio.start_ambient_music()  # Cherche automatiquement dans assets/sounds/

    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Factorio-like")

    game = Game(screen)

    try:
        game.run()
    except KeyboardInterrupt:
        pass
    finally:
        game.cleanup()
        audio.cleanup()
        pygame.quit()


def _load_config():
    """Charge la configuration depuis MongoDB ou utilise les valeurs par défaut."""
    from admin.config import get_config

    config = get_config()
    try:
        config.load_from_mongodb()
        print("Configuration chargée depuis MongoDB")
    except Exception as e:
        print(f"MongoDB non disponible ({e}), utilisation des valeurs par défaut")
        config.load_defaults()


if __name__ == '__main__':
    main()