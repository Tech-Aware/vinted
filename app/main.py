"""Interface CustomTkinter pour générer des annonces Vinted."""
from __future__ import annotations

import base64
import threading
from pathlib import Path
from typing import Iterable, List

from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageTk, UnidentifiedImageError

from app.backend.gpt_client import ListingGenerator, ListingResult
from app.backend.templates import ListingTemplateRegistry


class ImagePreview(ctk.CTkFrame):
    """Widget showing thumbnails for the selected images."""

    def __init__(self, master: ctk.CTkBaseClass, width: int = 320, height: int = 240) -> None:
        super().__init__(master)
        self._width = width
        self._height = height
        self._preview_images: List[ImageTk.PhotoImage] = []
        self._labels: List[ctk.CTkLabel] = []
        self._empty_label = ctk.CTkLabel(self, text="Aucune image sélectionnée")
        self._empty_label.pack(expand=True, fill="both")

    def update_images(self, paths: Iterable[Path]) -> None:
        for label in self._labels:
            label.destroy()
        self._labels.clear()
        self._preview_images.clear()

        if hasattr(self, "_empty_label"):
            self._empty_label.pack_forget()
            self._empty_label.destroy()

        image_paths = list(paths)
        if not image_paths:
            self._empty_label = ctk.CTkLabel(self, text="Aucune image sélectionnée")
            self._empty_label.pack(expand=True, fill="both")
            return

        displayed = 0
        for path in image_paths:
            try:
                with Image.open(path) as pil_img:
                    pil_img.thumbnail((self._width, self._height))
                    tk_img = ImageTk.PhotoImage(pil_img)
            except (UnidentifiedImageError, OSError):
                continue
            label = ctk.CTkLabel(self, image=tk_img, text="")
            label.pack(side="left", padx=6, pady=6)
            self._preview_images.append(tk_img)
            self._labels.append(label)
            displayed += 1

        if not displayed:
            self._empty_label = ctk.CTkLabel(self, text="Impossible de lire les images sélectionnées")
            self._empty_label.pack(expand=True, fill="both")


def encode_images_to_base64(paths: Iterable[Path]) -> List[str]:
    encoded = []
    for path in paths:
        with Path(path).open("rb") as fh:
            encoded.append(base64.b64encode(fh.read()).decode("utf-8"))
    return encoded


class VintedListingApp(ctk.CTk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Assistant Listing Vinted")
        self.geometry("1024x720")
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
        file_paths = filedialog.askopenfilenames(
            title="Sélectionnez les photos de l'article",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")],
        )
        self.selected_images = [Path(path) for path in file_paths]
        self.preview_frame.update_images(self.selected_images)
        self.status_label.configure(text=f"{len(self.selected_images)} photo(s) chargée(s)")

    def generate_listing(self) -> None:
        if not self.selected_images:
            self.status_label.configure(text="Ajoutez au moins une image avant d'analyser")
            return

        comment = self.comment_box.get("1.0", "end").strip()
        template_name = self.template_var.get()
        try:
            template_prompt = self.template_registry.get_prompt(template_name)
        except KeyError as exc:
            self.status_label.configure(text=str(exc))
            return
        self.status_label.configure(text="Analyse en cours...")

        def worker() -> None:
            try:
                encoded_images = encode_images_to_base64(self.selected_images)
                result = self.generator.generate_listing(encoded_images, comment, template_prompt)
                self.after(0, lambda: self.display_result(result))
            except Exception as exc:  # pragma: no cover - UI feedback
                self.after(0, lambda: self.status_label.configure(text=f"Erreur: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def display_result(self, result: ListingResult) -> None:
        self.title_box.delete("1.0", "end")
        self.title_box.insert("1.0", result.title)

        self.description_box.delete("1.0", "end")
        self.description_box.insert("1.0", result.description)

        self.status_label.configure(text="Titre et description générés")

    def reset(self) -> None:
        self.selected_images.clear()
        self.preview_frame.update_images([])
        self.comment_box.delete("1.0", "end")
        self.title_box.delete("1.0", "end")
        self.description_box.delete("1.0", "end")
        self.comment_box.insert("1.0", "Décrivez tâches et défauts...")
        self.status_label.configure(text="Prêt à analyser")


def main() -> None:
    app = VintedListingApp()
    app.mainloop()


if __name__ == "__main__":
    main()
