import pygame
import sys

from client.game import Game
from client.audio import get_audio
from client.ui.menu_manager import MenuManager, GameState


def main():
    pygame.init()

    # Charge la configuration depuis MongoDB
    _load_config()

    # Initialise l'audio
    audio = get_audio()
    audio.load_sounds()
    audio.generate_placeholder_sounds()
    audio.start_ambient_music()

    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Factorio-like")

    # Gestionnaire de menus
    menu_manager = MenuManager(screen)
    menu_manager.init_screens()

    game = None
    clock = pygame.time.Clock()
    running = True

    while running:
        dt = clock.tick(144) / 1000.0
        fps = clock.get_fps()

        # Vérifie si déconnexion demandée depuis le menu pause
        if menu_manager.get_option('disconnect_requested', False):
            menu_manager.set_option('disconnect_requested', False)
            if game:
                game.cleanup()
                game = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h),
                                                 pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF)
                menu_manager.screen = screen
                if game:
                    game.screen = screen
                    game.renderer.screen = screen

            # Si on est en jeu
            if menu_manager.state == GameState.PLAYING and game:
                # Échap en jeu
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if game.inventory_ui.visible:
                        game.inventory_ui.close()
                    elif game.inspected_entity is not None:
                        game.close_inspection()
                    elif game.selected_entity_type is not None:
                        game.selected_entity_type = None
                    else:
                        # Capture l'écran avant d'ouvrir le menu pause
                        pause_screen = menu_manager.screens.get(GameState.PAUSED)
                        if pause_screen:
                            pause_screen.set_game_screenshot(screen)
                        menu_manager.change_state(GameState.PAUSED, instant=True)
                    continue

                game.input_handler.handle_event(event)

            # Menu pause
            elif menu_manager.state == GameState.PAUSED:
                menu_manager.handle_event(event)

            else:
                menu_manager.handle_event(event)

        # Update
        if menu_manager.state == GameState.PLAYING:
            if game is None:
                host, port, name = menu_manager.get_connection_info()
                game = Game(screen)
                try:
                    game.connect(host, port, name)
                except Exception as e:
                    print(f"Échec connexion: {e}")
                    game = None
                    menu_manager.change_state(GameState.CONNECT, instant=True)
            elif game:
                game.fps = fps
                if game.connected:
                    game.update_single(dt)

                if game.network:
                    game.network.receive()
                    game.bandwidth = game.network.bandwidth

                if not game.connected and not game.connecting:
                    game.cleanup()
                    game = None
                    menu_manager.change_state(GameState.MAIN_MENU, instant=True)

        elif menu_manager.state == GameState.PAUSED:
            # En pause, on continue de recevoir le réseau pour ne pas timeout
            if game and game.network:
                game.fps = fps
                game.network.receive()
            menu_manager.update(dt)

        else:
            menu_manager.update(dt)

        # Render
        if menu_manager.state == GameState.PLAYING and game and game.connected:
            game.renderer.render(game)
            game.inventory_ui.render_hotbar(screen, game)

            if game.inspected_entity:
                game.renderer.render_inspection_panel(game)

            game.inventory_ui.render(screen, game)

            if game.show_debug:
                game.renderer.render_debug(game)

        elif menu_manager.state == GameState.PAUSED:
            # PauseScreen gère tout (screenshot + overlay + widgets)
            menu_manager.render()

        else:
            menu_manager.render()

        pygame.display.flip()

    # Cleanup
    if game:
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