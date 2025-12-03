"""
Interface web d'administration pour le jeu Factorio-like.
Permet de gérer les données MongoDB visuellement.

Lancement: python -m admin.web
Interface: http://localhost:8080
"""

import os
import sys
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

try:
    from fastapi import FastAPI, Request, Form, HTTPException
    from fastapi.responses import HTMLResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import uvicorn
except ImportError:
    print("Dépendances manquantes. Installez avec:")
    print("  pip install fastapi uvicorn jinja2 python-multipart")
    sys.exit(1)

from admin.database import AdminDB

# === CONFIGURATION ===

MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017')
HOST = "0.0.0.0"
PORT = 8000


# === LIFESPAN ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gère le cycle de vie de l'application."""
    # Startup
    app.state.db = AdminDB(MONGO_URI)
    print(f"Connecté à MongoDB: {MONGO_URI}")
    yield
    # Shutdown
    app.state.db.close()


# === APPLICATION ===

app = FastAPI(
    title="Factorio-like Admin",
    description="Interface d'administration du jeu",
    lifespan=lifespan
)

# === TEMPLATES HTML INLINE ===

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - Admin Factorio-like</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .color-preview {
            width: 24px;
            height: 24px;
            border-radius: 4px;
            border: 1px solid #374151;
            display: inline-block;
            vertical-align: middle;
        }
    </style>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen">
    <nav class="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div class="flex items-center justify-between max-w-7xl mx-auto">
            <h1 class="text-xl font-bold text-orange-500">🏭 Factorio-like Admin</h1>
            <div class="flex gap-4">
                <a href="/" class="hover:text-orange-400 {{ 'text-orange-400' if active == 'home' else '' }}">Accueil</a>
                <a href="/tiles" class="hover:text-orange-400 {{ 'text-orange-400' if active == 'tiles' else '' }}">Tiles</a>
                <a href="/entities" class="hover:text-orange-400 {{ 'text-orange-400' if active == 'entities' else '' }}">Entités</a>
                <a href="/items" class="hover:text-orange-400 {{ 'text-orange-400' if active == 'items' else '' }}">Items</a>
                <a href="/furnace-recipes" class="hover:text-orange-400 {{ 'text-orange-400' if active == 'furnace' else '' }}">Recettes Four</a>
                <a href="/assembler-recipes" class="hover:text-orange-400 {{ 'text-orange-400' if active == 'assembler' else '' }}">Recettes Assembleur</a>
                <a href="/placement-rules" class="hover:text-orange-400 {{ 'text-orange-400' if active == 'placement' else '' }}">Placement</a>
                <a href="/constants" class="hover:text-orange-400 {{ 'text-orange-400' if active == 'constants' else '' }}">Constantes</a>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        {% if message %}
        <div class="mb-6 p-4 rounded-lg {{ 'bg-green-800' if message_type == 'success' else 'bg-red-800' }}">
            {{ message }}
        </div>
        {% endif %}

        {{ content }}
    </main>

    <footer class="border-t border-gray-700 mt-12 py-6 text-center text-gray-500">
        <p>Factorio-like Admin Interface • MongoDB: {{ mongo_status }}</p>
    </footer>
</body>
</html>
"""

HOME_CONTENT = """
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
    <a href="/tiles" class="block p-6 bg-gray-800 rounded-lg hover:bg-gray-750 border border-gray-700 hover:border-orange-500 transition">
        <h2 class="text-xl font-semibold text-orange-400 mb-2">🗺️ Tiles</h2>
        <p class="text-gray-400">{{ stats.tiles }} types de terrain</p>
    </a>

    <a href="/entities" class="block p-6 bg-gray-800 rounded-lg hover:bg-gray-750 border border-gray-700 hover:border-orange-500 transition">
        <h2 class="text-xl font-semibold text-orange-400 mb-2">⚙️ Entités</h2>
        <p class="text-gray-400">{{ stats.entities }} types d'entités</p>
    </a>

    <a href="/items" class="block p-6 bg-gray-800 rounded-lg hover:bg-gray-750 border border-gray-700 hover:border-orange-500 transition">
        <h2 class="text-xl font-semibold text-orange-400 mb-2">📦 Items</h2>
        <p class="text-gray-400">{{ stats.items }} items</p>
    </a>

    <a href="/furnace-recipes" class="block p-6 bg-gray-800 rounded-lg hover:bg-gray-750 border border-gray-700 hover:border-orange-500 transition">
        <h2 class="text-xl font-semibold text-orange-400 mb-2">🔥 Recettes Four</h2>
        <p class="text-gray-400">{{ stats.furnace_recipes }} recettes</p>
    </a>

    <a href="/assembler-recipes" class="block p-6 bg-gray-800 rounded-lg hover:bg-gray-750 border border-gray-700 hover:border-orange-500 transition">
        <h2 class="text-xl font-semibold text-orange-400 mb-2">🔧 Recettes Assembleur</h2>
        <p class="text-gray-400">{{ stats.assembler_recipes }} recettes</p>
    </a>

    <a href="/placement-rules" class="block p-6 bg-gray-800 rounded-lg hover:bg-gray-750 border border-gray-700 hover:border-orange-500 transition">
        <h2 class="text-xl font-semibold text-orange-400 mb-2">📍 Règles Placement</h2>
        <p class="text-gray-400">{{ stats.placement_rules }} règles</p>
    </a>

    <a href="/constants" class="block p-6 bg-gray-800 rounded-lg hover:bg-gray-750 border border-gray-700 hover:border-orange-500 transition">
        <h2 class="text-xl font-semibold text-orange-400 mb-2">⚡ Constantes</h2>
        <p class="text-gray-400">{{ stats.constants }} paramètres</p>
    </a>
</div>

<div class="mt-12 p-6 bg-gray-800 rounded-lg border border-gray-700">
    <h2 class="text-xl font-semibold mb-4">📋 Instructions</h2>
    <ul class="list-disc list-inside text-gray-400 space-y-2">
        <li>Modifiez les données ici, elles seront chargées au prochain démarrage du serveur de jeu</li>
        <li>Pour appliquer les changements immédiatement, redémarrez le serveur</li>
        <li>Les couleurs sont au format RGB (0-255)</li>
    </ul>
</div>
"""

TILES_CONTENT = """
<div class="flex justify-between items-center mb-6">
    <h2 class="text-2xl font-bold">🗺️ Types de Tiles</h2>
</div>

<div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
    <table class="w-full">
        <thead class="bg-gray-750">
            <tr>
                <th class="px-4 py-3 text-left">ID</th>
                <th class="px-4 py-3 text-left">Nom</th>
                <th class="px-4 py-3 text-left">Couleur</th>
                <th class="px-4 py-3 text-left">Walkable</th>
                <th class="px-4 py-3 text-left">Resource</th>
                <th class="px-4 py-3 text-left">Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for tile in tiles %}
            <tr class="border-t border-gray-700 hover:bg-gray-750">
                <form method="POST" action="/tiles/{{ tile.id }}/update">
                    <td class="px-4 py-3">{{ tile.id }}</td>
                    <td class="px-4 py-3">
                        <input type="text" name="name" value="{{ tile.name }}" 
                               class="bg-gray-700 px-2 py-1 rounded w-32">
                    </td>
                    <td class="px-4 py-3">
                        <div class="flex items-center gap-2">
                            <span class="color-preview" style="background-color: rgb({{ tile.color[0] }}, {{ tile.color[1] }}, {{ tile.color[2] }})"></span>
                            <input type="number" name="color_r" value="{{ tile.color[0] }}" min="0" max="255" class="bg-gray-700 px-2 py-1 rounded w-16">
                            <input type="number" name="color_g" value="{{ tile.color[1] }}" min="0" max="255" class="bg-gray-700 px-2 py-1 rounded w-16">
                            <input type="number" name="color_b" value="{{ tile.color[2] }}" min="0" max="255" class="bg-gray-700 px-2 py-1 rounded w-16">
                        </div>
                    </td>
                    <td class="px-4 py-3">
                        <input type="checkbox" name="walkable" {{ 'checked' if tile.walkable else '' }} class="w-5 h-5">
                    </td>
                    <td class="px-4 py-3">
                        <input type="text" name="resource" value="{{ tile.resource or '' }}" 
                               class="bg-gray-700 px-2 py-1 rounded w-24" placeholder="aucune">
                    </td>
                    <td class="px-4 py-3">
                        <button type="submit" class="bg-orange-600 hover:bg-orange-500 px-3 py-1 rounded text-sm">
                            Sauver
                        </button>
                    </td>
                </form>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
"""

ENTITIES_CONTENT = """
<div class="flex justify-between items-center mb-6">
    <h2 class="text-2xl font-bold">⚙️ Types d'Entités</h2>
</div>

<div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
    <table class="w-full text-sm">
        <thead class="bg-gray-750">
            <tr>
                <th class="px-3 py-3 text-left">ID</th>
                <th class="px-3 py-3 text-left">Nom</th>
                <th class="px-3 py-3 text-left">Display</th>
                <th class="px-3 py-3 text-left">Couleur</th>
                <th class="px-3 py-3 text-left">Buffer</th>
                <th class="px-3 py-3 text-left">In/Out</th>
                <th class="px-3 py-3 text-left">Cooldown</th>
                <th class="px-3 py-3 text-left">Speed</th>
                <th class="px-3 py-3 text-left">Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for entity in entities %}
            <tr class="border-t border-gray-700 hover:bg-gray-750">
                <form method="POST" action="/entities/{{ entity.id }}/update">
                    <td class="px-3 py-3">{{ entity.id }}</td>
                    <td class="px-3 py-3">
                        <input type="text" name="name" value="{{ entity.name }}" 
                               class="bg-gray-700 px-2 py-1 rounded w-24">
                    </td>
                    <td class="px-3 py-3">
                        <input type="text" name="display_name" value="{{ entity.display_name }}" 
                               class="bg-gray-700 px-2 py-1 rounded w-24">
                    </td>
                    <td class="px-3 py-3">
                        <div class="flex items-center gap-1">
                            <span class="color-preview" style="background-color: rgb({{ entity.color[0] }}, {{ entity.color[1] }}, {{ entity.color[2] }})"></span>
                            <input type="number" name="color_r" value="{{ entity.color[0] }}" min="0" max="255" class="bg-gray-700 px-1 py-1 rounded w-12">
                            <input type="number" name="color_g" value="{{ entity.color[1] }}" min="0" max="255" class="bg-gray-700 px-1 py-1 rounded w-12">
                            <input type="number" name="color_b" value="{{ entity.color[2] }}" min="0" max="255" class="bg-gray-700 px-1 py-1 rounded w-12">
                        </div>
                    </td>
                    <td class="px-3 py-3">
                        <input type="number" name="buffer_size" value="{{ entity.buffer_size }}" min="0" 
                               class="bg-gray-700 px-1 py-1 rounded w-14">
                    </td>
                    <td class="px-3 py-3">
                        <input type="number" name="input_buffer_size" value="{{ entity.input_buffer_size }}" min="0" 
                               class="bg-gray-700 px-1 py-1 rounded w-10">
                        <input type="number" name="output_buffer_size" value="{{ entity.output_buffer_size }}" min="0" 
                               class="bg-gray-700 px-1 py-1 rounded w-10">
                    </td>
                    <td class="px-3 py-3">
                        <input type="number" name="cooldown" value="{{ entity.cooldown }}" min="0" 
                               class="bg-gray-700 px-1 py-1 rounded w-14">
                    </td>
                    <td class="px-3 py-3">
                        <input type="number" name="speed" value="{{ entity.speed }}" min="0" step="0.01"
                               class="bg-gray-700 px-1 py-1 rounded w-16">
                    </td>
                    <td class="px-3 py-3">
                        <button type="submit" class="bg-orange-600 hover:bg-orange-500 px-2 py-1 rounded text-xs">
                            Sauver
                        </button>
                    </td>
                </form>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
"""

ITEMS_CONTENT = """
<div class="flex justify-between items-center mb-6">
    <h2 class="text-2xl font-bold">📦 Items</h2>
    <button onclick="document.getElementById('add-form').classList.toggle('hidden')" 
            class="bg-green-600 hover:bg-green-500 px-4 py-2 rounded">
        + Ajouter Item
    </button>
</div>

<div id="add-form" class="hidden mb-6 p-4 bg-gray-800 rounded-lg border border-gray-700">
    <form method="POST" action="/items/add" class="flex gap-4 items-end">
        <div>
            <label class="block text-sm text-gray-400 mb-1">Nom (code)</label>
            <input type="text" name="name" required placeholder="new_item"
                   class="bg-gray-700 px-3 py-2 rounded">
        </div>
        <div>
            <label class="block text-sm text-gray-400 mb-1">Nom affiché</label>
            <input type="text" name="display_name" required placeholder="Nouvel Item"
                   class="bg-gray-700 px-3 py-2 rounded">
        </div>
        <div>
            <label class="block text-sm text-gray-400 mb-1">Couleur RGB</label>
            <div class="flex gap-1">
                <input type="number" name="color_r" value="128" min="0" max="255" class="bg-gray-700 px-2 py-2 rounded w-16">
                <input type="number" name="color_g" value="128" min="0" max="255" class="bg-gray-700 px-2 py-2 rounded w-16">
                <input type="number" name="color_b" value="128" min="0" max="255" class="bg-gray-700 px-2 py-2 rounded w-16">
            </div>
        </div>
        <div>
            <label class="block text-sm text-gray-400 mb-1">Catégorie</label>
            <select name="category" class="bg-gray-700 px-3 py-2 rounded">
                <option value="raw">raw</option>
                <option value="plate">plate</option>
                <option value="intermediate">intermediate</option>
                <option value="science">science</option>
            </select>
        </div>
        <button type="submit" class="bg-green-600 hover:bg-green-500 px-4 py-2 rounded">
            Ajouter
        </button>
    </form>
</div>

<div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
    <table class="w-full">
        <thead class="bg-gray-750">
            <tr>
                <th class="px-4 py-3 text-left">Nom</th>
                <th class="px-4 py-3 text-left">Nom affiché</th>
                <th class="px-4 py-3 text-left">Couleur</th>
                <th class="px-4 py-3 text-left">Catégorie</th>
                <th class="px-4 py-3 text-left">Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for item in items %}
            <tr class="border-t border-gray-700 hover:bg-gray-750">
                <form method="POST" action="/items/{{ item.name }}/update">
                    <td class="px-4 py-3">
                        <code class="bg-gray-700 px-2 py-1 rounded">{{ item.name }}</code>
                    </td>
                    <td class="px-4 py-3">
                        <input type="text" name="display_name" value="{{ item.display_name }}" 
                               class="bg-gray-700 px-2 py-1 rounded w-40">
                    </td>
                    <td class="px-4 py-3">
                        <div class="flex items-center gap-2">
                            <span class="color-preview" style="background-color: rgb({{ item.color[0] }}, {{ item.color[1] }}, {{ item.color[2] }})"></span>
                            <input type="number" name="color_r" value="{{ item.color[0] }}" min="0" max="255" class="bg-gray-700 px-2 py-1 rounded w-16">
                            <input type="number" name="color_g" value="{{ item.color[1] }}" min="0" max="255" class="bg-gray-700 px-2 py-1 rounded w-16">
                            <input type="number" name="color_b" value="{{ item.color[2] }}" min="0" max="255" class="bg-gray-700 px-2 py-1 rounded w-16">
                        </div>
                    </td>
                    <td class="px-4 py-3">
                        <select name="category" class="bg-gray-700 px-2 py-1 rounded">
                            <option value="raw" {{ 'selected' if item.category == 'raw' else '' }}>raw</option>
                            <option value="plate" {{ 'selected' if item.category == 'plate' else '' }}>plate</option>
                            <option value="intermediate" {{ 'selected' if item.category == 'intermediate' else '' }}>intermediate</option>
                            <option value="science" {{ 'selected' if item.category == 'science' else '' }}>science</option>
                        </select>
                    </td>
                    <td class="px-4 py-3 flex gap-2">
                        <button type="submit" class="bg-orange-600 hover:bg-orange-500 px-3 py-1 rounded text-sm">
                            Sauver
                        </button>
                        <a href="/items/{{ item.name }}/delete" 
                           onclick="return confirm('Supprimer cet item ?')"
                           class="bg-red-600 hover:bg-red-500 px-3 py-1 rounded text-sm">
                            Suppr
                        </a>
                    </td>
                </form>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
"""

FURNACE_RECIPES_CONTENT = """
<div class="flex justify-between items-center mb-6">
    <h2 class="text-2xl font-bold">🔥 Recettes Four</h2>
    <button onclick="document.getElementById('add-form').classList.toggle('hidden')" 
            class="bg-green-600 hover:bg-green-500 px-4 py-2 rounded">
        + Ajouter Recette
    </button>
</div>

<div id="add-form" class="hidden mb-6 p-4 bg-gray-800 rounded-lg border border-gray-700">
    <form method="POST" action="/furnace-recipes/add" class="flex gap-4 items-end">
        <div>
            <label class="block text-sm text-gray-400 mb-1">Input</label>
            <input type="text" name="input" required placeholder="iron_ore"
                   class="bg-gray-700 px-3 py-2 rounded">
        </div>
        <div>
            <label class="block text-sm text-gray-400 mb-1">Output</label>
            <input type="text" name="output" required placeholder="iron_plate"
                   class="bg-gray-700 px-3 py-2 rounded">
        </div>
        <div>
            <label class="block text-sm text-gray-400 mb-1">Quantité</label>
            <input type="number" name="count" value="1" min="1"
                   class="bg-gray-700 px-3 py-2 rounded w-20">
        </div>
        <div>
            <label class="block text-sm text-gray-400 mb-1">Temps (ticks)</label>
            <input type="number" name="time" value="120" min="1"
                   class="bg-gray-700 px-3 py-2 rounded w-24">
        </div>
        <button type="submit" class="bg-green-600 hover:bg-green-500 px-4 py-2 rounded">
            Ajouter
        </button>
    </form>
</div>

<div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
    <table class="w-full">
        <thead class="bg-gray-750">
            <tr>
                <th class="px-4 py-3 text-left">Input</th>
                <th class="px-4 py-3 text-left">→</th>
                <th class="px-4 py-3 text-left">Output</th>
                <th class="px-4 py-3 text-left">Quantité</th>
                <th class="px-4 py-3 text-left">Temps (ticks)</th>
                <th class="px-4 py-3 text-left">Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for recipe in recipes %}
            <tr class="border-t border-gray-700 hover:bg-gray-750">
                <form method="POST" action="/furnace-recipes/{{ recipe.input }}/update">
                    <td class="px-4 py-3">
                        <code class="bg-gray-700 px-2 py-1 rounded">{{ recipe.input }}</code>
                    </td>
                    <td class="px-4 py-3 text-2xl text-orange-500">→</td>
                    <td class="px-4 py-3">
                        <input type="text" name="output" value="{{ recipe.output }}" 
                               class="bg-gray-700 px-2 py-1 rounded w-32">
                    </td>
                    <td class="px-4 py-3">
                        <input type="number" name="count" value="{{ recipe.count }}" min="1"
                               class="bg-gray-700 px-2 py-1 rounded w-16">
                    </td>
                    <td class="px-4 py-3">
                        <input type="number" name="time" value="{{ recipe.time }}" min="1"
                               class="bg-gray-700 px-2 py-1 rounded w-20">
                        <span class="text-gray-500 text-sm">({{ "%.1f"|format(recipe.time / 60) }}s)</span>
                    </td>
                    <td class="px-4 py-3 flex gap-2">
                        <button type="submit" class="bg-orange-600 hover:bg-orange-500 px-3 py-1 rounded text-sm">
                            Sauver
                        </button>
                        <a href="/furnace-recipes/{{ recipe.input }}/delete" 
                           onclick="return confirm('Supprimer cette recette ?')"
                           class="bg-red-600 hover:bg-red-500 px-3 py-1 rounded text-sm">
                            Suppr
                        </a>
                    </td>
                </form>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
"""

ASSEMBLER_RECIPES_CONTENT = """
<div class="flex justify-between items-center mb-6">
    <h2 class="text-2xl font-bold">🔧 Recettes Assembleur</h2>
    <button onclick="document.getElementById('add-form').classList.toggle('hidden')" 
            class="bg-green-600 hover:bg-green-500 px-4 py-2 rounded">
        + Ajouter Recette
    </button>
</div>

<div id="add-form" class="hidden mb-6 p-4 bg-gray-800 rounded-lg border border-gray-700">
    <form method="POST" action="/assembler-recipes/add" class="flex flex-wrap gap-4 items-end">
        <div>
            <label class="block text-sm text-gray-400 mb-1">Nom (code)</label>
            <input type="text" name="name" required placeholder="new_recipe"
                   class="bg-gray-700 px-3 py-2 rounded">
        </div>
        <div>
            <label class="block text-sm text-gray-400 mb-1">Nom affiché</label>
            <input type="text" name="display_name" required placeholder="Nouvelle Recette"
                   class="bg-gray-700 px-3 py-2 rounded">
        </div>
        <div>
            <label class="block text-sm text-gray-400 mb-1">Ingrédients (JSON)</label>
            <input type="text" name="ingredients" required placeholder='{"iron_plate": 2}'
                   class="bg-gray-700 px-3 py-2 rounded w-48">
        </div>
        <div>
            <label class="block text-sm text-gray-400 mb-1">Résultat</label>
            <input type="text" name="result" required placeholder="output_item"
                   class="bg-gray-700 px-3 py-2 rounded">
        </div>
        <div>
            <label class="block text-sm text-gray-400 mb-1">Quantité</label>
            <input type="number" name="count" value="1" min="1"
                   class="bg-gray-700 px-3 py-2 rounded w-20">
        </div>
        <div>
            <label class="block text-sm text-gray-400 mb-1">Temps</label>
            <input type="number" name="time" value="60" min="1"
                   class="bg-gray-700 px-3 py-2 rounded w-20">
        </div>
        <button type="submit" class="bg-green-600 hover:bg-green-500 px-4 py-2 rounded">
            Ajouter
        </button>
    </form>
</div>

<div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
    <table class="w-full">
        <thead class="bg-gray-750">
            <tr>
                <th class="px-4 py-3 text-left">Nom</th>
                <th class="px-4 py-3 text-left">Display</th>
                <th class="px-4 py-3 text-left">Ingrédients</th>
                <th class="px-4 py-3 text-left">Résultat</th>
                <th class="px-4 py-3 text-left">Qté</th>
                <th class="px-4 py-3 text-left">Temps</th>
                <th class="px-4 py-3 text-left">Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for recipe in recipes %}
            <tr class="border-t border-gray-700 hover:bg-gray-750">
                <form method="POST" action="/assembler-recipes/{{ recipe.name }}/update">
                    <td class="px-4 py-3">
                        <code class="bg-gray-700 px-2 py-1 rounded text-sm">{{ recipe.name }}</code>
                    </td>
                    <td class="px-4 py-3">
                        <input type="text" name="display_name" value="{{ recipe.display_name }}" 
                               class="bg-gray-700 px-2 py-1 rounded w-28">
                    </td>
                    <td class="px-4 py-3">
                        <input type="text" name="ingredients" value="{{ recipe.ingredients | tojson }}" 
                               class="bg-gray-700 px-2 py-1 rounded w-40 text-sm">
                    </td>
                    <td class="px-4 py-3">
                        <input type="text" name="result" value="{{ recipe.result }}" 
                               class="bg-gray-700 px-2 py-1 rounded w-28">
                    </td>
                    <td class="px-4 py-3">
                        <input type="number" name="count" value="{{ recipe.count }}" min="1"
                               class="bg-gray-700 px-2 py-1 rounded w-14">
                    </td>
                    <td class="px-4 py-3">
                        <input type="number" name="time" value="{{ recipe.time }}" min="1"
                               class="bg-gray-700 px-2 py-1 rounded w-16">
                    </td>
                    <td class="px-4 py-3 flex gap-2">
                        <button type="submit" class="bg-orange-600 hover:bg-orange-500 px-2 py-1 rounded text-xs">
                            Sauver
                        </button>
                        <a href="/assembler-recipes/{{ recipe.name }}/delete" 
                           onclick="return confirm('Supprimer ?')"
                           class="bg-red-600 hover:bg-red-500 px-2 py-1 rounded text-xs">
                            Suppr
                        </a>
                    </td>
                </form>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
"""

PLACEMENT_RULES_CONTENT = """
<div class="flex justify-between items-center mb-6">
    <h2 class="text-2xl font-bold">📍 Règles de Placement</h2>
</div>

<div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
    <table class="w-full">
        <thead class="bg-gray-750">
            <tr>
                <th class="px-4 py-3 text-left">Entité</th>
                <th class="px-4 py-3 text-left">Tiles autorisées</th>
                <th class="px-4 py-3 text-left">Tiles interdites</th>
                <th class="px-4 py-3 text-left">Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for rule in rules %}
            <tr class="border-t border-gray-700 hover:bg-gray-750">
                <form method="POST" action="/placement-rules/{{ rule.entity }}/update">
                    <td class="px-4 py-3">
                        <code class="bg-gray-700 px-2 py-1 rounded">{{ rule.entity }}</code>
                    </td>
                    <td class="px-4 py-3">
                        <input type="text" name="allowed_tiles" 
                               value="{{ rule.allowed_tiles | join(', ') }}" 
                               class="bg-gray-700 px-2 py-1 rounded w-64"
                               placeholder="GRASS, DIRT, STONE">
                    </td>
                    <td class="px-4 py-3">
                        <input type="text" name="forbidden_tiles" 
                               value="{{ rule.forbidden_tiles | join(', ') }}" 
                               class="bg-gray-700 px-2 py-1 rounded w-48"
                               placeholder="WATER, VOID">
                    </td>
                    <td class="px-4 py-3">
                        <button type="submit" class="bg-orange-600 hover:bg-orange-500 px-3 py-1 rounded text-sm">
                            Sauver
                        </button>
                    </td>
                </form>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<div class="mt-6 p-4 bg-gray-800 rounded-lg border border-gray-700">
    <p class="text-gray-400 text-sm">
        <strong>Format:</strong> Séparez les tiles par des virgules. 
        Laissez vide pour aucune restriction.
    </p>
</div>
"""

CONSTANTS_CONTENT = """
<div class="flex justify-between items-center mb-6">
    <h2 class="text-2xl font-bold">⚡ Constantes du Jeu</h2>
    <button onclick="document.getElementById('add-form').classList.toggle('hidden')" 
            class="bg-green-600 hover:bg-green-500 px-4 py-2 rounded">
        + Ajouter Constante
    </button>
</div>

<div id="add-form" class="hidden mb-6 p-4 bg-gray-800 rounded-lg border border-gray-700">
    <form method="POST" action="/constants/add" class="flex gap-4 items-end">
        <div>
            <label class="block text-sm text-gray-400 mb-1">Clé</label>
            <input type="text" name="key" required placeholder="NEW_CONSTANT"
                   class="bg-gray-700 px-3 py-2 rounded">
        </div>
        <div>
            <label class="block text-sm text-gray-400 mb-1">Valeur</label>
            <input type="text" name="value" required placeholder="100"
                   class="bg-gray-700 px-3 py-2 rounded">
        </div>
        <button type="submit" class="bg-green-600 hover:bg-green-500 px-4 py-2 rounded">
            Ajouter
        </button>
    </form>
</div>

<div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
    <table class="w-full">
        <thead class="bg-gray-750">
            <tr>
                <th class="px-4 py-3 text-left">Clé</th>
                <th class="px-4 py-3 text-left">Valeur</th>
                <th class="px-4 py-3 text-left">Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for const in constants %}
            <tr class="border-t border-gray-700 hover:bg-gray-750">
                <form method="POST" action="/constants/{{ const.key }}/update">
                    <td class="px-4 py-3">
                        <code class="bg-gray-700 px-2 py-1 rounded">{{ const.key }}</code>
                    </td>
                    <td class="px-4 py-3">
                        <input type="text" name="value" value="{{ const.value }}" 
                               class="bg-gray-700 px-2 py-1 rounded w-40">
                    </td>
                    <td class="px-4 py-3 flex gap-2">
                        <button type="submit" class="bg-orange-600 hover:bg-orange-500 px-3 py-1 rounded text-sm">
                            Sauver
                        </button>
                        <a href="/constants/{{ const.key }}/delete" 
                           onclick="return confirm('Supprimer cette constante ?')"
                           class="bg-red-600 hover:bg-red-500 px-3 py-1 rounded text-sm">
                            Suppr
                        </a>
                    </td>
                </form>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
"""

# === TEMPLATE ENGINE ===

from jinja2 import Environment, BaseLoader


class StringLoader(BaseLoader):
    def get_source(self, environment, template):
        return template, None, lambda: True


jinja_env = Environment(loader=StringLoader())


def render_page(content: str, title: str, active: str, request: Request, **kwargs) -> HTMLResponse:
    """Rend une page complète."""
    db: AdminDB = request.app.state.db

    # Vérifie la connexion MongoDB
    try:
        db.db.command('ping')
        mongo_status = "Connecté ✓"
    except:
        mongo_status = "Déconnecté ✗"

    # Rend le contenu
    content_template = jinja_env.from_string(content)
    rendered_content = content_template.render(**kwargs)

    # Rend la page complète
    page_template = jinja_env.from_string(BASE_TEMPLATE)
    html = page_template.render(
        title=title,
        active=active,
        content=rendered_content,
        mongo_status=mongo_status,
        message=kwargs.get('message'),
        message_type=kwargs.get('message_type', 'success')
    )

    return HTMLResponse(content=html)


# === ROUTES ===

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    db: AdminDB = request.app.state.db

    stats = {
        'tiles': db.tiles.count_documents({}),
        'entities': db.entities.count_documents({}),
        'items': db.items.count_documents({}),
        'furnace_recipes': db.furnace_recipes.count_documents({}),
        'assembler_recipes': db.assembler_recipes.count_documents({}),
        'placement_rules': db.placement_rules.count_documents({}),
        'constants': db.constants.count_documents({}),
    }

    return render_page(HOME_CONTENT, "Accueil", "home", request, stats=stats)


# --- TILES ---

@app.get("/tiles", response_class=HTMLResponse)
async def tiles_list(request: Request):
    db: AdminDB = request.app.state.db
    tiles = list(db.tiles.find().sort('id', 1))
    return render_page(TILES_CONTENT, "Tiles", "tiles", request, tiles=tiles)


@app.post("/tiles/{tile_id}/update")
async def tiles_update(request: Request, tile_id: int,
                       name: str = Form(...),
                       color_r: int = Form(...),
                       color_g: int = Form(...),
                       color_b: int = Form(...),
                       walkable: bool = Form(False),
                       resource: str = Form("")):
    db: AdminDB = request.app.state.db

    db.tiles.update_one(
        {'id': tile_id},
        {'$set': {
            'name': name,
            'color': [color_r, color_g, color_b],
            'walkable': walkable,
            'resource': resource if resource else None
        }}
    )

    return RedirectResponse(url="/tiles", status_code=303)


# --- ENTITIES ---

@app.get("/entities", response_class=HTMLResponse)
async def entities_list(request: Request):
    db: AdminDB = request.app.state.db
    entities = list(db.entities.find().sort('id', 1))
    return render_page(ENTITIES_CONTENT, "Entités", "entities", request, entities=entities)


@app.post("/entities/{entity_id}/update")
async def entities_update(request: Request, entity_id: int,
                          name: str = Form(...),
                          display_name: str = Form(...),
                          color_r: int = Form(...),
                          color_g: int = Form(...),
                          color_b: int = Form(...),
                          buffer_size: int = Form(0),
                          input_buffer_size: int = Form(0),
                          output_buffer_size: int = Form(0),
                          cooldown: int = Form(0),
                          speed: float = Form(0.0)):
    db: AdminDB = request.app.state.db

    db.entities.update_one(
        {'id': entity_id},
        {'$set': {
            'name': name,
            'display_name': display_name,
            'color': [color_r, color_g, color_b],
            'buffer_size': buffer_size,
            'input_buffer_size': input_buffer_size,
            'output_buffer_size': output_buffer_size,
            'cooldown': cooldown,
            'speed': speed
        }}
    )

    return RedirectResponse(url="/entities", status_code=303)


# --- ITEMS ---

@app.get("/items", response_class=HTMLResponse)
async def items_list(request: Request):
    db: AdminDB = request.app.state.db
    items = list(db.items.find().sort('name', 1))
    return render_page(ITEMS_CONTENT, "Items", "items", request, items=items)


@app.post("/items/add")
async def items_add(request: Request,
                    name: str = Form(...),
                    display_name: str = Form(...),
                    color_r: int = Form(...),
                    color_g: int = Form(...),
                    color_b: int = Form(...),
                    category: str = Form(...)):
    db: AdminDB = request.app.state.db

    db.items.insert_one({
        'name': name,
        'display_name': display_name,
        'color': [color_r, color_g, color_b],
        'category': category
    })

    return RedirectResponse(url="/items", status_code=303)


@app.post("/items/{item_name}/update")
async def items_update(request: Request, item_name: str,
                       display_name: str = Form(...),
                       color_r: int = Form(...),
                       color_g: int = Form(...),
                       color_b: int = Form(...),
                       category: str = Form(...)):
    db: AdminDB = request.app.state.db

    db.items.update_one(
        {'name': item_name},
        {'$set': {
            'display_name': display_name,
            'color': [color_r, color_g, color_b],
            'category': category
        }}
    )

    return RedirectResponse(url="/items", status_code=303)


@app.get("/items/{item_name}/delete")
async def items_delete(request: Request, item_name: str):
    db: AdminDB = request.app.state.db
    db.items.delete_one({'name': item_name})
    return RedirectResponse(url="/items", status_code=303)


# --- FURNACE RECIPES ---

@app.get("/furnace-recipes", response_class=HTMLResponse)
async def furnace_recipes_list(request: Request):
    db: AdminDB = request.app.state.db
    recipes = list(db.furnace_recipes.find().sort('input', 1))
    return render_page(FURNACE_RECIPES_CONTENT, "Recettes Four", "furnace", request, recipes=recipes)


@app.post("/furnace-recipes/add")
async def furnace_recipes_add(request: Request,
                              input: str = Form(...),
                              output: str = Form(...),
                              count: int = Form(1),
                              time: int = Form(120)):
    db: AdminDB = request.app.state.db

    db.furnace_recipes.insert_one({
        'input': input,
        'output': output,
        'count': count,
        'time': time
    })

    return RedirectResponse(url="/furnace-recipes", status_code=303)


@app.post("/furnace-recipes/{recipe_input}/update")
async def furnace_recipes_update(request: Request, recipe_input: str,
                                 output: str = Form(...),
                                 count: int = Form(1),
                                 time: int = Form(120)):
    db: AdminDB = request.app.state.db

    db.furnace_recipes.update_one(
        {'input': recipe_input},
        {'$set': {
            'output': output,
            'count': count,
            'time': time
        }}
    )

    return RedirectResponse(url="/furnace-recipes", status_code=303)


@app.get("/furnace-recipes/{recipe_input}/delete")
async def furnace_recipes_delete(request: Request, recipe_input: str):
    db: AdminDB = request.app.state.db
    db.furnace_recipes.delete_one({'input': recipe_input})
    return RedirectResponse(url="/furnace-recipes", status_code=303)


# --- ASSEMBLER RECIPES ---

@app.get("/assembler-recipes", response_class=HTMLResponse)
async def assembler_recipes_list(request: Request):
    db: AdminDB = request.app.state.db
    recipes = list(db.assembler_recipes.find().sort('name', 1))
    return render_page(ASSEMBLER_RECIPES_CONTENT, "Recettes Assembleur", "assembler", request, recipes=recipes)


@app.post("/assembler-recipes/add")
async def assembler_recipes_add(request: Request,
                                name: str = Form(...),
                                display_name: str = Form(...),
                                ingredients: str = Form(...),
                                result: str = Form(...),
                                count: int = Form(1),
                                time: int = Form(60)):
    import json
    db: AdminDB = request.app.state.db

    try:
        ingredients_dict = json.loads(ingredients)
    except:
        ingredients_dict = {}

    db.assembler_recipes.insert_one({
        'name': name,
        'display_name': display_name,
        'ingredients': ingredients_dict,
        'result': result,
        'count': count,
        'time': time
    })

    return RedirectResponse(url="/assembler-recipes", status_code=303)


@app.post("/assembler-recipes/{recipe_name}/update")
async def assembler_recipes_update(request: Request, recipe_name: str,
                                   display_name: str = Form(...),
                                   ingredients: str = Form(...),
                                   result: str = Form(...),
                                   count: int = Form(1),
                                   time: int = Form(60)):
    import json
    db: AdminDB = request.app.state.db

    try:
        ingredients_dict = json.loads(ingredients)
    except:
        ingredients_dict = {}

    db.assembler_recipes.update_one(
        {'name': recipe_name},
        {'$set': {
            'display_name': display_name,
            'ingredients': ingredients_dict,
            'result': result,
            'count': count,
            'time': time
        }}
    )

    return RedirectResponse(url="/assembler-recipes", status_code=303)


@app.get("/assembler-recipes/{recipe_name}/delete")
async def assembler_recipes_delete(request: Request, recipe_name: str):
    db: AdminDB = request.app.state.db
    db.assembler_recipes.delete_one({'name': recipe_name})
    return RedirectResponse(url="/assembler-recipes", status_code=303)


# --- PLACEMENT RULES ---

@app.get("/placement-rules", response_class=HTMLResponse)
async def placement_rules_list(request: Request):
    db: AdminDB = request.app.state.db
    rules = list(db.placement_rules.find().sort('entity', 1))
    return render_page(PLACEMENT_RULES_CONTENT, "Règles Placement", "placement", request, rules=rules)


@app.post("/placement-rules/{entity}/update")
async def placement_rules_update(request: Request, entity: str,
                                 allowed_tiles: str = Form(""),
                                 forbidden_tiles: str = Form("")):
    db: AdminDB = request.app.state.db

    allowed = [t.strip() for t in allowed_tiles.split(',') if t.strip()]
    forbidden = [t.strip() for t in forbidden_tiles.split(',') if t.strip()]

    db.placement_rules.update_one(
        {'entity': entity},
        {'$set': {
            'allowed_tiles': allowed,
            'forbidden_tiles': forbidden
        }}
    )

    return RedirectResponse(url="/placement-rules", status_code=303)


# --- CONSTANTS ---

@app.get("/constants", response_class=HTMLResponse)
async def constants_list(request: Request):
    db: AdminDB = request.app.state.db
    constants = list(db.constants.find().sort('key', 1))
    return render_page(CONSTANTS_CONTENT, "Constantes", "constants", request, constants=constants)


@app.post("/constants/add")
async def constants_add(request: Request,
                        key: str = Form(...),
                        value: str = Form(...)):
    db: AdminDB = request.app.state.db

    # Essaie de convertir en nombre
    try:
        if '.' in value:
            typed_value = float(value)
        else:
            typed_value = int(value)
    except:
        typed_value = value

    db.constants.insert_one({
        'key': key,
        'value': typed_value
    })

    return RedirectResponse(url="/constants", status_code=303)


@app.post("/constants/{key}/update")
async def constants_update(request: Request, key: str,
                           value: str = Form(...)):
    db: AdminDB = request.app.state.db

    # Essaie de convertir en nombre
    try:
        if '.' in value:
            typed_value = float(value)
        else:
            typed_value = int(value)
    except:
        typed_value = value

    db.constants.update_one(
        {'key': key},
        {'$set': {'value': typed_value}}
    )

    return RedirectResponse(url="/constants", status_code=303)


@app.get("/constants/{key}/delete")
async def constants_delete(request: Request, key: str):
    db: AdminDB = request.app.state.db
    db.constants.delete_one({'key': key})
    return RedirectResponse(url="/constants", status_code=303)


# === MAIN ===

def main():
    print(f"""
╔══════════════════════════════════════════════════════════╗
║         🏭 Factorio-like Admin Interface                 ║
╠══════════════════════════════════════════════════════════╣
║  Interface web: http://localhost:{PORT}                   ║
║  MongoDB: {MONGO_URI:<40} ║
╚══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()