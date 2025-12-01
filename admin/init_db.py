#!/usr/bin/env python3
"""
Script d'initialisation de la base de données MongoDB.
Lance ce script une fois pour créer les collections et les données par défaut.

Usage:
    python -m admin.init_db [--uri mongodb://localhost:27017] [--reset]
"""

import argparse
from admin.database import AdminDB


def main():
    parser = argparse.ArgumentParser(description='Initialise la base de données admin MongoDB')
    parser.add_argument('--uri', default='mongodb://localhost:27017',
                        help='URI de connexion MongoDB')
    parser.add_argument('--reset', action='store_true',
                        help='Supprime les données existantes avant initialisation')

    args = parser.parse_args()

    print(f"Connexion à MongoDB: {args.uri}")

    db = AdminDB(args.uri)

    if args.reset:
        print("Suppression des données existantes...")
        db.tiles.delete_many({})
        db.entities.delete_many({})
        db.items.delete_many({})
        db.furnace_recipes.delete_many({})
        db.assembler_recipes.delete_many({})
        db.placement_rules.delete_many({})
        db.constants.delete_many({})
        print("Données supprimées.")

    print("Initialisation des données par défaut...")
    db.init_default_data()

    # Affiche un résumé
    print("\n=== Résumé ===")
    print(f"Tiles: {db.tiles.count_documents({})}")
    print(f"Entités: {db.entities.count_documents({})}")
    print(f"Items: {db.items.count_documents({})}")
    print(f"Recettes four: {db.furnace_recipes.count_documents({})}")
    print(f"Recettes assembleur: {db.assembler_recipes.count_documents({})}")
    print(f"Règles placement: {db.placement_rules.count_documents({})}")
    print(f"Constantes: {db.constants.count_documents({})}")

    print("\n✓ Base de données initialisée avec succès!")

    db.close()


if __name__ == '__main__':
    main()