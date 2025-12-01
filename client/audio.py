"""
Système audio pour le jeu.
Gère l'ambiance, les sons des machines et les effets UI.
"""

import pygame
import os
from typing import Dict, Optional
from enum import Enum, auto


class SoundType(Enum):
    """Types de sons."""
    # UI
    UI_CLICK = auto()
    UI_BUILD = auto()
    UI_DESTROY = auto()
    UI_ERROR = auto()
    UI_SELECT = auto()

    # Machines
    MACHINE_MINER = auto()
    MACHINE_FURNACE = auto()
    MACHINE_ASSEMBLER = auto()
    MACHINE_CONVEYOR = auto()
    MACHINE_INSERTER = auto()

    # Ambiance
    AMBIENT_WIND = auto()
    AMBIENT_FACTORY = auto()


class AudioManager:
    """Gestionnaire audio centralisé."""

    _instance: Optional['AudioManager'] = None

    def __init__(self, sounds_dir: str = "assets/sounds"):
        self.sounds_dir = sounds_dir
        self.sounds: Dict[SoundType, pygame.mixer.Sound] = {}
        self.master_volume = 0.5
        self.music_volume = 0.3
        self.sfx_volume = 0.5
        self.enabled = True

        # État des sons de machines (pour éviter les répétitions)
        self._playing_machines: Dict[int, pygame.mixer.Channel] = {}

        # Initialise le mixer
        self._init_mixer()

    @classmethod
    def get_instance(cls, sounds_dir: str = "assets/sounds") -> 'AudioManager':
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = cls(sounds_dir)
        return cls._instance

    def _init_mixer(self):
        """Initialise le mixer pygame."""
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(32)  # Plus de canaux pour les machines
            print("Audio initialisé")
        except Exception as e:
            print(f"Erreur initialisation audio: {e}")
            self.enabled = False

    def load_sounds(self):
        """Charge tous les sons depuis le répertoire assets."""
        if not self.enabled:
            return

        # Mapping fichiers -> types
        sound_files = {
            SoundType.UI_CLICK: "ui_click.wav",
            SoundType.UI_BUILD: "ui_build.wav",
            SoundType.UI_DESTROY: "ui_destroy.wav",
            SoundType.UI_ERROR: "ui_error.wav",
            SoundType.UI_SELECT: "ui_select.wav",
            SoundType.MACHINE_MINER: "machine_miner.wav",
            SoundType.MACHINE_FURNACE: "machine_furnace.wav",
            SoundType.MACHINE_ASSEMBLER: "machine_assembler.wav",
            SoundType.MACHINE_CONVEYOR: "machine_conveyor.wav",
            SoundType.MACHINE_INSERTER: "machine_inserter.wav",
        }

        for sound_type, filename in sound_files.items():
            path = os.path.join(self.sounds_dir, filename)
            if os.path.exists(path):
                try:
                    self.sounds[sound_type] = pygame.mixer.Sound(path)
                    print(f"Son chargé: {filename}")
                except Exception as e:
                    print(f"Erreur chargement {filename}: {e}")
            else:
                # Crée un son vide si fichier manquant
                pass

    def generate_placeholder_sounds(self):
        """Génère des sons placeholder si les fichiers n'existent pas."""
        if not self.enabled:
            return

        import math
        import struct

        def generate_tone(frequency: float, duration: float, volume: float = 0.3) -> pygame.mixer.Sound:
            """Génère un son simple (onde sinusoïdale)."""
            sample_rate = 44100
            n_samples = int(duration * sample_rate)

            samples = []
            for i in range(n_samples):
                t = i / sample_rate
                # Envelope (fade in/out)
                envelope = 1.0
                if i < n_samples * 0.1:
                    envelope = i / (n_samples * 0.1)
                elif i > n_samples * 0.7:
                    envelope = (n_samples - i) / (n_samples * 0.3)

                value = math.sin(2 * math.pi * frequency * t) * volume * envelope
                # Stéréo
                sample = int(value * 32767)
                samples.append(struct.pack('<hh', sample, sample))

            sound = pygame.mixer.Sound(buffer=b''.join(samples))
            return sound

        def generate_noise(duration: float, volume: float = 0.2) -> pygame.mixer.Sound:
            """Génère du bruit blanc."""
            import random
            sample_rate = 44100
            n_samples = int(duration * sample_rate)

            samples = []
            for i in range(n_samples):
                envelope = 1.0
                if i < n_samples * 0.05:
                    envelope = i / (n_samples * 0.05)
                elif i > n_samples * 0.8:
                    envelope = (n_samples - i) / (n_samples * 0.2)

                value = (random.random() * 2 - 1) * volume * envelope
                sample = int(value * 32767)
                samples.append(struct.pack('<hh', sample, sample))

            return pygame.mixer.Sound(buffer=b''.join(samples))

        # Génère les sons UI
        if SoundType.UI_CLICK not in self.sounds:
            self.sounds[SoundType.UI_CLICK] = generate_tone(800, 0.05, 0.2)

        if SoundType.UI_BUILD not in self.sounds:
            self.sounds[SoundType.UI_BUILD] = generate_tone(600, 0.15, 0.3)

        if SoundType.UI_DESTROY not in self.sounds:
            self.sounds[SoundType.UI_DESTROY] = generate_tone(200, 0.2, 0.3)

        if SoundType.UI_ERROR not in self.sounds:
            self.sounds[SoundType.UI_ERROR] = generate_tone(150, 0.3, 0.2)

        if SoundType.UI_SELECT not in self.sounds:
            self.sounds[SoundType.UI_SELECT] = generate_tone(1000, 0.08, 0.15)

        # Génère les sons de machines (plus longs, pour boucle)
        # Volume à 1.0 - le channel gère le volume dynamique basé sur la distance
        if SoundType.MACHINE_MINER not in self.sounds:
            self.sounds[SoundType.MACHINE_MINER] = generate_noise(1.0, 1.0)

        if SoundType.MACHINE_FURNACE not in self.sounds:
            self.sounds[SoundType.MACHINE_FURNACE] = generate_tone(80, 1.0, 1.0)

        if SoundType.MACHINE_CONVEYOR not in self.sounds:
            self.sounds[SoundType.MACHINE_CONVEYOR] = generate_tone(200, 0.5, 1.0)

        if SoundType.MACHINE_INSERTER not in self.sounds:
            self.sounds[SoundType.MACHINE_INSERTER] = generate_tone(400, 0.3, 1.0)

        if SoundType.MACHINE_ASSEMBLER not in self.sounds:
            self.sounds[SoundType.MACHINE_ASSEMBLER] = generate_tone(150, 1.0, 1.0)

        print("Sons placeholder générés")

    def play(self, sound_type: SoundType, volume: float = None):
        """Joue un son une fois."""
        if not self.enabled:
            return

        sound = self.sounds.get(sound_type)
        if sound:
            vol = volume if volume is not None else self.sfx_volume
            sound.set_volume(vol * self.master_volume)
            sound.play()

    def play_ui_click(self):
        """Son de clic UI."""
        self.play(SoundType.UI_CLICK, 0.3)

    def play_build(self):
        """Son de construction."""
        self.play(SoundType.UI_BUILD, 0.4)

    def play_destroy(self):
        """Son de destruction."""
        self.play(SoundType.UI_DESTROY, 0.4)

    def play_error(self):
        """Son d'erreur."""
        self.play(SoundType.UI_ERROR, 0.3)

    def play_select(self):
        """Son de sélection."""
        self.play(SoundType.UI_SELECT, 0.2)

    def start_ambient_music(self, music_file: str = None):
        """Démarre la musique d'ambiance."""
        if not self.enabled:
            return

        if music_file and os.path.exists(music_file):
            try:
                pygame.mixer.music.load(music_file)
                pygame.mixer.music.set_volume(self.music_volume)
                pygame.mixer.music.play(-1)  # Boucle infinie
                print(f"Musique d'ambiance: {music_file}")
            except Exception as e:
                print(f"Erreur musique: {e}")
        else:
            # Pas de fichier, on génère une ambiance simple
            self._start_generated_ambient()

    def _start_generated_ambient(self):
        """Génère une ambiance sonore simple."""
        # L'ambiance sera gérée par update_machine_sounds
        pass

    def stop_music(self):
        """Arrête la musique."""
        if self.enabled:
            pygame.mixer.music.stop()

    def set_music_volume(self, volume: float):
        """Change le volume de la musique (0.0 - 1.0)."""
        self.music_volume = max(0.0, min(1.0, volume))
        if self.enabled:
            pygame.mixer.music.set_volume(self.music_volume)

    def set_sfx_volume(self, volume: float):
        """Change le volume des effets (0.0 - 1.0)."""
        self.sfx_volume = max(0.0, min(1.0, volume))

    def set_master_volume(self, volume: float):
        """Change le volume global (0.0 - 1.0)."""
        self.master_volume = max(0.0, min(1.0, volume))
        # Met à jour le volume de tous les canaux en cours
        for channel in self._playing_machines.values():
            if channel.get_busy():
                # Recalcule le volume sera fait au prochain update
                pass

    def toggle_audio(self):
        """Active/désactive l'audio."""
        self.enabled = not self.enabled
        if not self.enabled:
            pygame.mixer.stop()
            pygame.mixer.music.stop()
            # Vide les références pour permettre le redémarrage au unmute
            self._playing_machines.clear()
        return self.enabled

    def update_machine_sounds(self, entities: dict, player_x: float, player_y: float, max_distance: float = 15.0):
        """Met à jour les sons des machines proches du joueur."""
        if not self.enabled:
            return

        from shared.entities import EntityType

        # Map entity type -> sound type
        machine_sounds = {
            EntityType.MINER: SoundType.MACHINE_MINER,
            EntityType.FURNACE: SoundType.MACHINE_FURNACE,
            EntityType.ASSEMBLER: SoundType.MACHINE_ASSEMBLER,
            EntityType.CONVEYOR: SoundType.MACHINE_CONVEYOR,
            EntityType.INSERTER: SoundType.MACHINE_INSERTER,
        }

        # Trouve les machines actives proches
        active_machines = {}

        for entity_id, entity in entities.items():
            entity_type = EntityType(entity['type'])
            if entity_type not in machine_sounds:
                continue

            # Distance au joueur
            dx = entity['x'] - player_x
            dy = entity['y'] - player_y
            distance = (dx * dx + dy * dy) ** 0.5

            if distance > max_distance:
                continue

            # Vérifie si la machine est active
            data = entity.get('data', {})
            is_active = False

            if entity_type == EntityType.MINER:
                is_active = len(data.get('output', [])) > 0 or data.get('cooldown', 0) > 0
            elif entity_type == EntityType.FURNACE:
                is_active = len(data.get('input', [])) > 0 or data.get('cooldown', 0) > 0
            elif entity_type == EntityType.ASSEMBLER:
                is_active = data.get('recipe') is not None and (len(data.get('input', [])) > 0 or data.get('cooldown', 0) > 0)
            elif entity_type == EntityType.CONVEYOR:
                is_active = len(data.get('items', [])) > 0
            elif entity_type == EntityType.INSERTER:
                is_active = data.get('held_item') is not None

            if is_active:
                # Volume basé sur la distance, multiplié par le master volume
                volume = max(0.05, (1 - distance / max_distance) * 0.3) * self.master_volume
                active_machines[entity_id] = (machine_sounds[entity_type], volume)

        # Arrête les sons des machines qui ne sont plus actives/proches
        to_stop = []
        for entity_id, channel in self._playing_machines.items():
            if entity_id not in active_machines:
                channel.stop()
                to_stop.append(entity_id)

        for entity_id in to_stop:
            del self._playing_machines[entity_id]

        # Limite le nombre de machines sonores simultanées
        max_simultaneous = 5
        if len(active_machines) > max_simultaneous:
            # Garde les plus proches (volume le plus élevé)
            sorted_machines = sorted(active_machines.items(), key=lambda x: x[1][1], reverse=True)
            active_machines = dict(sorted_machines[:max_simultaneous])

        # Démarre/met à jour les sons des nouvelles machines
        for entity_id, (sound_type, volume) in active_machines.items():
            if entity_id not in self._playing_machines:
                sound = self.sounds.get(sound_type)
                if sound:
                    channel = pygame.mixer.find_channel()
                    if channel:
                        # Ne pas modifier sound.set_volume() - utiliser uniquement le channel
                        channel.set_volume(volume)
                        channel.play(sound, loops=-1)
                        self._playing_machines[entity_id] = channel
            else:
                # Met à jour le volume via le channel uniquement
                channel = self._playing_machines[entity_id]
                channel.set_volume(volume)

    def cleanup(self):
        """Nettoie les ressources audio."""
        if self.enabled:
            pygame.mixer.stop()
            pygame.mixer.music.stop()
            pygame.mixer.quit()


# Fonction globale
def get_audio() -> AudioManager:
    """Retourne l'instance singleton du gestionnaire audio."""
    return AudioManager.get_instance()