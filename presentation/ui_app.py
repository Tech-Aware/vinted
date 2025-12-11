from __future__ import annotations

"""Interface de démonstration utilisant l'aperçu d'images."""

from pathlib import Path
from typing import List

from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.backend.api_key_manager import ensure_api_key
from app.backend.gpt_client import ListingGenerator
from app.backend.image_encoding import encode_images_to_base64
from app.backend.templates import ListingTemplateRegistry
from app.logger import get_logger
from app.ui.image_preview import ImagePreview

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

logger = get_logger(__name__)


class PresentationApp(ctk.CTk):
    """Application de présentation avec gestion des images."""

    def __init__(self) -> None:
        super().__init__()
        logger.step("Initialisation de la PresentationApp")
        self.title("Assistant Vinted - Présentation")
        self.geometry("1100x720")
        self.resizable(True, True)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        try:
            ensure_api_key(self)
        except RuntimeError:
            logger.error("Aucune clé API disponible pour la démo")
            self.destroy()
            raise

        self.generator = ListingGenerator()
        self.template_registry = ListingTemplateRegistry()
        self.selected_images: List[Path] = []

        self.provider_var = ctk.StringVar(value="openai")
        self.profile_var = ctk.StringVar(value=self.template_registry.default_template)

        self._build_layout()

    def _build_layout(self) -> None:
        try:
            self.columnconfigure(0, weight=1)
            self.rowconfigure(1, weight=1)
            self.rowconfigure(2, weight=1)

            config_frame = ctk.CTkFrame(self)
            config_frame.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="ew")
            config_frame.columnconfigure((0, 1, 2, 3), weight=1)

            provider_label = ctk.CTkLabel(config_frame, text="Provider")
            provider_label.grid(row=0, column=0, padx=8, pady=8, sticky="w")
            provider_combo = ctk.CTkComboBox(
                config_frame,
                values=["openai"],
                variable=self.provider_var,
                state="readonly",
                width=180,
            )
            provider_combo.grid(row=0, column=1, padx=8, pady=8, sticky="w")

            profile_label = ctk.CTkLabel(config_frame, text="Profil / Template")
            profile_label.grid(row=0, column=2, padx=8, pady=8, sticky="w")
            profile_combo = ctk.CTkComboBox(
                config_frame,
                values=self.template_registry.available_templates,
                variable=self.profile_var,
                state="readonly",
                width=240,
            )
            profile_combo.grid(row=0, column=3, padx=8, pady=8, sticky="w")

            content_frame = ctk.CTkFrame(self)
            content_frame.grid(row=1, column=0, padx=16, pady=(4, 8), sticky="nsew")
            content_frame.columnconfigure(0, weight=1)
            content_frame.rowconfigure(0, weight=1)

            self.preview = ImagePreview(content_frame, on_remove=self._remove_image)
            self.preview.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

            bottom_frame = ctk.CTkFrame(self)
            bottom_frame.grid(row=2, column=0, padx=16, pady=(4, 12), sticky="nsew")
            bottom_frame.columnconfigure(0, weight=1)
            bottom_frame.columnconfigure(1, weight=1)
            bottom_frame.rowconfigure(1, weight=1)

            input_frame = ctk.CTkFrame(bottom_frame)
            input_frame.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
            input_frame.columnconfigure(0, weight=1)
            input_frame.rowconfigure(1, weight=1)

            comment_label = ctk.CTkLabel(input_frame, text="Commentaire")
            comment_label.grid(row=0, column=0, sticky="w")

            self.comment_input = ctk.CTkTextbox(input_frame, height=120)
            self.comment_input.grid(row=1, column=0, sticky="nsew", pady=(6, 12))

            buttons_frame = ctk.CTkFrame(input_frame)
            buttons_frame.grid(row=2, column=0, sticky="ew")
            buttons_frame.columnconfigure((0, 1, 2), weight=1)

            add_button = ctk.CTkButton(buttons_frame, text="Ajouter des photos", command=self.select_images)
            add_button.grid(row=0, column=0, padx=4, pady=4, sticky="ew")

            generate_button = ctk.CTkButton(buttons_frame, text="Générer", command=self.generate)
            generate_button.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

            reset_button = ctk.CTkButton(buttons_frame, text="Réinitialiser", command=self.reset_images)
            reset_button.grid(row=0, column=2, padx=4, pady=4, sticky="ew")

            output_frame = ctk.CTkFrame(bottom_frame)
            output_frame.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")
            output_frame.columnconfigure(0, weight=1)
            output_frame.rowconfigure(3, weight=1)

            title_label = ctk.CTkLabel(output_frame, text="Titre généré")
            title_label.grid(row=0, column=0, sticky="w")

            self.title_output = ctk.CTkTextbox(output_frame, height=60)
            self.title_output.grid(row=1, column=0, sticky="ew", pady=(6, 12))

            description_label = ctk.CTkLabel(output_frame, text="Description générée")
            description_label.grid(row=2, column=0, sticky="w")

            self.description_output = ctk.CTkTextbox(output_frame, height=200)
            self.description_output.grid(row=3, column=0, sticky="nsew", pady=(6, 0))
        except Exception:
            logger.exception("Erreur lors de la construction de l'interface")
            raise

    def select_images(self) -> None:
        logger.step("Sélection de nouvelles images pour la présentation")
        try:
            filenames = filedialog.askopenfilenames(
                parent=self,
                title="Sélectionner des images",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("Tous les fichiers", "*.*")],
            )
            if not filenames:
                logger.info("Aucun fichier sélectionné")
                return

            paths = [Path(name) for name in filenames if Path(name).suffix.lower() in IMAGE_EXTENSIONS]
            if not paths:
                messagebox.showwarning(self.title(), "Aucun fichier image valide sélectionné")
                logger.warning("Sélection sans extension valide: %s", filenames)
                return

            self.selected_images = paths
            self.preview.update_images(self.selected_images)
            logger.success("%d image(s) chargée(s) pour la prévisualisation", len(paths))
        except Exception:
            logger.exception("Erreur lors de la sélection des images")
            messagebox.showerror(self.title(), "Impossible de charger les images sélectionnées")

    def _remove_image(self, path: Path) -> None:
        logger.step("Suppression d'une image de la sélection")
        try:
            self.selected_images = [img for img in self.selected_images if img != path]
            self.preview.update_images(self.selected_images)
            logger.info("Image supprimée: %s", path)
        except Exception:
            logger.exception("Impossible de supprimer l'image %s", path)
            messagebox.showerror(self.title(), "Erreur lors de la suppression de l'image")

    def reset_images(self) -> None:
        logger.step("Réinitialisation de la sélection d'images")
        try:
            self.selected_images = []
            self.preview.update_images([])
            logger.success("Sélection d'images vidée")
        except Exception:
            logger.exception("Impossible de réinitialiser la sélection d'images")
            messagebox.showerror(self.title(), "Erreur lors de la réinitialisation des images")

    def generate(self) -> None:
        logger.step("Génération de contenu pour la présentation")
        if not self.selected_images:
            messagebox.showwarning(self.title(), "Ajoutez d'abord des photos avant de générer")
            logger.warning("Tentative de génération sans images")
            return

        try:
            template = self.template_registry.get_template(self.profile_var.get())
            encoded_images = encode_images_to_base64(self.selected_images)
            comment = self.comment_input.get("1.0", "end").strip()
            result = self.generator.generate_listing(
                encoded_images,
                comment,
                template,
                fr_size_override="",
            )
            self._display_result(result)
            logger.success(
                "Génération terminée avec le provider %s et le profil %s",
                self.provider_var.get(),
                self.profile_var.get(),
            )
        except Exception:
            logger.exception("Échec de la génération depuis la PresentationApp")
            messagebox.showerror(self.title(), "Impossible de générer le contenu pour ces images")

    def _display_result(self, result) -> None:
        try:
            self.title_output.delete("1.0", "end")
            self.title_output.insert("1.0", result.title)
            self.description_output.delete("1.0", "end")
            self.description_output.insert("1.0", result.description)
            if getattr(result, "price_estimate", None):
                logger.info("Estimation de prix: %s", result.price_estimate)
        except Exception:
            logger.exception("Erreur lors de l'affichage des résultats")
            messagebox.showerror(self.title(), "Impossible d'afficher les résultats générés")


def run() -> None:
    """Point d'entrée pratique pour lancer l'UI de présentation."""

    try:
        app = PresentationApp()
        app.mainloop()
    except Exception:
        logger.exception("Erreur critique dans l'interface de présentation")
        raise
