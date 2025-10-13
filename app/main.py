"""Interface CustomTkinter pour générer des annonces Vinted."""
from __future__ import annotations

import base64
import mimetypes
import threading
from pathlib import Path
from typing import Iterable, List

from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, UnidentifiedImageError

from app.backend.gpt_client import ListingGenerator, ListingResult
from app.backend.templates import ListingTemplateRegistry
from app.logger import get_logger


logger = get_logger(__name__)


class ImagePreview(ctk.CTkFrame):
    """Widget showing thumbnails for the selected images in a vertical scrollable list."""

    def __init__(self, master: ctk.CTkBaseClass, width: int = 220, height: int = 320) -> None:
        super().__init__(master)
        self._thumb_width = width
        self._max_height = height
        self._preview_images: List[ctk.CTkImage] = []
        self._labels: List[ctk.CTkLabel] = []

        self._scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll_frame.pack_forget()

        self._gallery_container = ctk.CTkFrame(self._scroll_frame, fg_color="transparent")
        self._gallery_container.grid(row=0, column=0, sticky="nwe")
        self._scroll_frame.grid_columnconfigure(0, weight=1)
        self._gallery_container.grid_columnconfigure(0, weight=1)

        self._empty_label = ctk.CTkLabel(self, text="Aucune image sélectionnée")
        self._empty_label.pack(expand=True, fill="both")

    def _show_empty_state(self, message: str = "Aucune image sélectionnée") -> None:
        self._scroll_frame.pack_forget()
        self._empty_label.configure(text=message)
        self._empty_label.pack(expand=True, fill="both")

    def _show_gallery(self) -> None:
        self._empty_label.pack_forget()
        self._scroll_frame.pack(expand=True, fill="both")

    def update_images(self, paths: Iterable[Path]) -> None:
        for widget in self._gallery_container.winfo_children():
            widget.destroy()
        self._labels.clear()
        self._preview_images.clear()

        image_paths = list(paths)
        if not image_paths:
            self._show_empty_state()
            return

        for path in image_paths:
            try:
                with Image.open(path) as pil_img:
                    pil_img = pil_img.copy()
                    pil_img.thumbnail((self._thumb_width, self._max_height))
                    tk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
            except (UnidentifiedImageError, OSError) as exc:
                logger.error("Impossible de créer la vignette pour %s", path, exc_info=exc)
                continue
            self._preview_images.append(tk_img)
        if not self._preview_images:
            self._show_empty_state("Impossible de lire les images sélectionnées")
            logger.error("Aucune vignette valide n'a pu être générée")
            return

        self._show_gallery()
        for index, image in enumerate(self._preview_images):
            label = ctk.CTkLabel(self._gallery_container, image=image, text="")
            label.grid(row=index, column=0, sticky="ew", padx=8, pady=(8 if index == 0 else 4, 4))
            self._labels.append(label)
        logger.success("%d vignette(s) générée(s)", len(self._preview_images))



def encode_images_to_base64(paths: Iterable[Path]) -> List[str]:
    """Encode image files and return data URLs compatible with the OpenAI API."""

    logger.step("Encodage des images en base64")
    encoded: List[str] = []
    for path in paths:
        file_path = Path(path)
        try:
            with file_path.open("rb") as fh:
                encoded_data = base64.b64encode(fh.read()).decode("utf-8")
        except OSError as exc:
            logger.error("Lecture impossible pour %s", path, exc_info=exc)
            continue

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/jpeg"

        data_url = f"data:{mime_type};base64,{encoded_data}"
        encoded.append(data_url)
        logger.success("Image encodée: %s", path)

    logger.info("%d image(s) encodée(s)", len(encoded))
    return encoded


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
            template_prompt = self.template_registry.get_prompt(template_name)
        except KeyError as exc:
            self.status_label.configure(text=str(exc))
            logger.error("Template introuvable: %s", template_name, exc_info=exc)
            return
        logger.success("Template '%s' récupéré", template_name)
        self.status_label.configure(text="Analyse en cours...")
        logger.info("Lancement de l'analyse (%d image(s), %d caractère(s) de commentaire)", len(self.selected_images), len(comment))

        def worker() -> None:
            try:
                logger.step("Thread d'analyse démarré")
                encoded_images = encode_images_to_base64(self.selected_images)
                result = self.generator.generate_listing(encoded_images, comment, template_prompt)
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


def main() -> None:
    logger.step("Démarrage de l'application principale")
    try:
        app = VintedListingApp()
        app.mainloop()
        logger.success("Application fermée proprement")
    except Exception:
        logger.exception("Erreur critique dans la boucle principale")
        raise


if __name__ == "__main__":
    main()
