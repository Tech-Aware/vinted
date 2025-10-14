"""
Copyright 2025 Kevin Andreazza
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy at http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

"""Main Tkinter application used to orchestrate the listing generation workflow."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import List

from tkinter import filedialog

import customtkinter as ctk

from app.backend.api_key_manager import ensure_api_key
from app.backend.gpt_client import ListingGenerator, ListingResult
from app.backend.image_encoding import encode_images_to_base64
from app.backend.templates import ListingTemplateRegistry
from app.logger import get_logger
from app.ui.image_preview import ImagePreview


logger = get_logger(__name__)


class VintedListingApp(ctk.CTk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        logger.step("Initialisation de l'application VintedListingApp")
        self.title("Assistant Listing Vinted")
        self.geometry("1024x720")
        self.resizable(True, True)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        try:
            ensure_api_key(self)
        except RuntimeError:
            logger.error("Fermeture de l'application faute de clé API")
            self.destroy()
            raise

        self.generator = ListingGenerator()
        self.template_registry = ListingTemplateRegistry()
        self.selected_images: List[Path] = []

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.preview_frame = ImagePreview(self)
        self.preview_frame.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")

        right_panel = ctk.CTkFrame(self)
        right_panel.grid(row=0, column=1, padx=16, pady=16, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(7, weight=1)

        self.template_var = ctk.StringVar(value=self.template_registry.default_template)
        template_label = ctk.CTkLabel(right_panel, text="Modèle d'annonce")
        template_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self.template_combo = ctk.CTkComboBox(
            right_panel, values=self.template_registry.available_templates, variable=self.template_var
        )
        self.template_combo.grid(row=1, column=0, sticky="ew", padx=12)

        self.comment_box = ctk.CTkTextbox(right_panel, height=100)
        self.comment_box.insert("1.0", "Décrivez tâches et défauts...")
        self.comment_box.grid(row=2, column=0, sticky="ew", padx=12, pady=(12, 4))

        button_frame = ctk.CTkFrame(right_panel)
        button_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 4))
        button_frame.columnconfigure((0, 1, 2), weight=1)

        self.select_button = ctk.CTkButton(button_frame, text="Ajouter des photos", command=self.select_images)
        self.select_button.grid(row=0, column=0, padx=4, pady=4, sticky="ew")

        self.generate_button = ctk.CTkButton(button_frame, text="Analyser", command=self.generate_listing)
        self.generate_button.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        self.clear_button = ctk.CTkButton(button_frame, text="Réinitialiser", command=self.reset)
        self.clear_button.grid(row=0, column=2, padx=4, pady=4, sticky="ew")

        self.title_box = ctk.CTkTextbox(right_panel, height=80)
        self.title_box.grid(row=4, column=0, sticky="nsew", padx=12, pady=(12, 4))

        self.description_box = ctk.CTkTextbox(right_panel, height=220)
        self.description_box.grid(row=5, column=0, sticky="nsew", padx=12, pady=(4, 4))

        self.status_label = ctk.CTkLabel(right_panel, text="Prêt à analyser")
        self.status_label.grid(row=6, column=0, sticky="w", padx=12, pady=(8, 12))

    def select_images(self) -> None:
        logger.step("Ouverture de la boîte de dialogue de sélection d'images")
        file_paths = filedialog.askopenfilenames(
            title="Sélectionnez les photos de l'article",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")],
        )
        if not file_paths:
            logger.info("Aucune image sélectionnée")
            return

        for path in file_paths:
            path_obj = Path(path)
            if path_obj not in self.selected_images:
                self.selected_images.append(path_obj)
                logger.success("Image ajoutée: %s", path_obj)

        self.preview_frame.update_images(self.selected_images)
        self.status_label.configure(text=f"{len(self.selected_images)} photo(s) chargée(s)")
        logger.info("%d image(s) actuellement sélectionnée(s)", len(self.selected_images))

    def generate_listing(self) -> None:
        if not self.selected_images:
            self.status_label.configure(text="Ajoutez au moins une image avant d'analyser")
            logger.error("Analyse annulée: aucune image sélectionnée")
            return

        comment = self.comment_box.get("1.0", "end").strip()
        template_name = self.template_var.get()
        logger.step("Récupération du template: %s", template_name)
        try:
            template = self.template_registry.get_template(template_name)
        except KeyError as exc:
            self.status_label.configure(text=str(exc))
            logger.error("Template introuvable: %s", template_name, exc_info=exc)
            return
        logger.success("Template '%s' récupéré", template_name)
        self.status_label.configure(text="Analyse en cours...")
        logger.info(
            "Lancement de l'analyse (%d image(s), %d caractère(s) de commentaire)",
            len(self.selected_images),
            len(comment),
        )

        def worker() -> None:
            try:
                logger.step("Thread d'analyse démarré")
                encoded_images = encode_images_to_base64(self.selected_images)
                result = self.generator.generate_listing(encoded_images, comment, template)
                logger.success("Analyse terminée avec succès")
                self.after(0, lambda: self.display_result(result))
            except Exception as exc:  # pragma: no cover - UI feedback
                logger.exception("Erreur lors de la génération de l'annonce")
                self.after(0, lambda err=exc: self.status_label.configure(text=f"Erreur: {err}"))

        threading.Thread(target=worker, daemon=True).start()
        logger.step("Thread d'analyse lancé")

    def display_result(self, result: ListingResult) -> None:
        self.title_box.delete("1.0", "end")
        self.title_box.insert("1.0", result.title)

        self.description_box.delete("1.0", "end")
        self.description_box.insert("1.0", result.description)

        self.status_label.configure(text="Titre et description générés")
        logger.success("Résultat affiché à l'utilisateur")

    def reset(self) -> None:
        self.selected_images.clear()
        self.preview_frame.update_images([])
        self.comment_box.delete("1.0", "end")
        self.title_box.delete("1.0", "end")
        self.description_box.delete("1.0", "end")
        self.comment_box.insert("1.0", "Décrivez tâches et défauts...")
        self.status_label.configure(text="Prêt à analyser")
        logger.step("Application réinitialisée")
