from __future__ import annotations

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

import threading
from pathlib import Path
from typing import List, Optional, Set

from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.backend.api_key_manager import ensure_api_key
from app.backend.gpt_client import ListingGenerator, ListingResult
from app.backend.image_encoding import encode_images_to_base64
from app.backend.templates import ListingTemplateRegistry
from app.logger import get_logger
from app.ui.image_preview import ImagePreview

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


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
        self._image_directories: Set[Path] = set()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        content_frame = ctk.CTkFrame(self)
        content_frame.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="nsew")
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)

        self.preview_frame = ImagePreview(content_frame, on_remove=self._remove_image)
        self.preview_frame.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        form_frame = ctk.CTkFrame(self)
        form_frame.grid(row=1, column=0, padx=16, pady=(8, 16), sticky="nsew")
        form_frame.columnconfigure(0, weight=1)
        form_frame.rowconfigure(5, weight=1)

        self.template_var = ctk.StringVar(value=self.template_registry.default_template)
        template_label = ctk.CTkLabel(form_frame, text="Modèle d'annonce")
        template_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self.template_combo = ctk.CTkComboBox(
            form_frame, values=self.template_registry.available_templates, variable=self.template_var
        )
        self.template_combo.grid(row=1, column=0, sticky="ew", padx=12)

        self.comment_box = ctk.CTkTextbox(form_frame, height=28)
        self.comment_box.insert("1.0", "Décrivez tâches et défauts...")
        self.comment_box.grid(row=2, column=0, sticky="ew", padx=12, pady=(12, 4))

        button_frame = ctk.CTkFrame(form_frame)
        button_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 4))
        button_frame.columnconfigure((0, 1, 2), weight=1)

        self.select_button = ctk.CTkButton(button_frame, text="Ajouter des photos", command=self.select_images)
        self.select_button.grid(row=0, column=0, padx=4, pady=4, sticky="ew")

        self.generate_button = ctk.CTkButton(button_frame, text="Analyser", command=self.generate_listing)
        self.generate_button.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        self.clear_button = ctk.CTkButton(button_frame, text="Réinitialiser", command=self.reset)
        self.clear_button.grid(row=0, column=2, padx=4, pady=4, sticky="ew")

        title_container = ctk.CTkFrame(form_frame)
        title_container.grid(row=4, column=0, sticky="nsew", padx=12, pady=(12, 4))
        title_container.columnconfigure(0, weight=1)
        title_container.rowconfigure(0, weight=1)

        self.title_box = ctk.CTkTextbox(title_container, height=40)
        self.title_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)
        self._enable_select_all(self.title_box)

        title_copy_button = ctk.CTkButton(
            title_container,
            text="Copier",
            width=90,
            command=lambda: self._copy_to_clipboard(self.title_box),
        )
        title_copy_button.grid(row=0, column=1, padx=(8, 0), pady=4, sticky="ns")

        description_container = ctk.CTkFrame(form_frame)
        description_container.grid(row=5, column=0, sticky="nsew", padx=12, pady=(4, 12))
        description_container.columnconfigure(0, weight=1)
        description_container.rowconfigure(0, weight=1)

        self.description_box = ctk.CTkTextbox(description_container, height=220)
        self.description_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)
        self._enable_select_all(self.description_box)

        description_copy_button = ctk.CTkButton(
            description_container,
            text="Copier",
            width=90,
            command=lambda: self._copy_to_clipboard(self.description_box),
        )
        description_copy_button.grid(row=0, column=1, padx=(8, 0), pady=4, sticky="ns")

        self._loading_after_id: Optional[str] = None
        self._loading_step = 0

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
                self._image_directories.add(path_obj.parent)

        self.preview_frame.update_images(self.selected_images)
        logger.info("%d image(s) actuellement sélectionnée(s)", len(self.selected_images))

    def generate_listing(self) -> None:
        if not self.selected_images:
            self._show_error_popup("Ajoutez au moins une image avant d'analyser")
            logger.error("Analyse annulée: aucune image sélectionnée")
            return

        comment = self.comment_box.get("1.0", "end").strip()
        template_name = self.template_var.get()
        logger.step("Récupération du template: %s", template_name)
        try:
            template = self.template_registry.get_template(template_name)
        except KeyError as exc:
            self._show_error_popup(str(exc))
            logger.error("Template introuvable: %s", template_name, exc_info=exc)
            return
        logger.success("Template '%s' récupéré", template_name)
        logger.info(
            "Lancement de l'analyse (%d image(s), %d caractère(s) de commentaire)",
            len(self.selected_images),
            len(comment),
        )

        self._start_loading_state()

        def worker() -> None:
            try:
                logger.step("Thread d'analyse démarré")
                encoded_images = encode_images_to_base64(self.selected_images)
                result = self.generator.generate_listing(encoded_images, comment, template)
                logger.success("Analyse terminée avec succès")
                self.after(0, lambda: self.display_result(result))
            except Exception as exc:  # pragma: no cover - UI feedback
                logger.exception("Erreur lors de la génération de l'annonce")
                self.after(0, lambda err=exc: self._handle_error(err))

        threading.Thread(target=worker, daemon=True).start()
        logger.step("Thread d'analyse lancé")

    def display_result(self, result: ListingResult) -> None:
        self._stop_loading_state()
        self.title_box.delete("1.0", "end")
        self.title_box.insert("1.0", result.title)

        self.description_box.delete("1.0", "end")
        self.description_box.insert("1.0", result.description)
        logger.success("Résultat affiché à l'utilisateur")

    def reset(self) -> None:
        self._stop_loading_state()
        self._cleanup_image_directories()
        self.selected_images.clear()
        self._image_directories.clear()
        self.preview_frame.update_images([])
        self.comment_box.delete("1.0", "end")
        self.title_box.delete("1.0", "end")
        self.description_box.delete("1.0", "end")
        self.comment_box.insert("1.0", "Décrivez tâches et défauts...")
        logger.step("Application réinitialisée")

    def _remove_image(self, path: Path) -> None:
        try:
            self.selected_images.remove(path)
        except ValueError:
            logger.warning("Impossible de supprimer %s: image inconnue", path)
            return

        logger.info("Image retirée avant analyse: %s", path)
        remaining_directories = {p.parent for p in self.selected_images}
        self._image_directories.intersection_update(remaining_directories)
        self.preview_frame.update_images(self.selected_images)

    def _cleanup_image_directories(self) -> None:
        if not self.selected_images or not self._image_directories:
            return

        for directory in list(self._image_directories):
            try:
                image_files = [
                    file
                    for file in directory.iterdir()
                    if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS
                ]
            except OSError as exc:
                logger.error("Impossible de lister le dossier %s", directory, exc_info=exc)
                continue

            for file in image_files:
                try:
                    file.unlink()
                    logger.info("Suppression du fichier %s", file)
                except FileNotFoundError:
                    logger.warning("Fichier déjà supprimé: %s", file)
                except OSError as exc:
                    logger.error("Suppression impossible pour %s", file, exc_info=exc)

    def _start_loading_state(self) -> None:
        self._stop_loading_state()
        self.generate_button.configure(state="disabled")
        self._loading_step = 0
        self._animate_loading_button()

    def _animate_loading_button(self) -> None:
        dots = "." * self._loading_step
        self.generate_button.configure(text=f"Analyser{dots}")
        self._loading_step = (self._loading_step + 1) % 4
        self._loading_after_id = self.after(350, self._animate_loading_button)

    def _stop_loading_state(self) -> None:
        if self._loading_after_id is not None:
            self.after_cancel(self._loading_after_id)
            self._loading_after_id = None
        self.generate_button.configure(text="Analyser", state="normal")

    def _handle_error(self, error: Exception) -> None:
        self._stop_loading_state()
        self._show_error_popup(f"Erreur: {error}")

    def _show_error_popup(self, message: str) -> None:
        messagebox.showerror("Erreur", message)

    def _enable_select_all(self, textbox: ctk.CTkTextbox) -> None:
        def handler(event: object) -> str:
            textbox.event_generate("<<SelectAll>>")
            return "break"

        textbox.bind("<Control-a>", handler)
        textbox.bind("<Control-A>", handler)

    def _copy_to_clipboard(self, textbox: ctk.CTkTextbox) -> None:
        content = textbox.get("1.0", "end-1c")
        if not content:
            return

        self.clipboard_clear()
        self.clipboard_append(content)
        logger.info("Contenu copié dans le presse-papiers")
