"""Widgets used to preview selected images in the UI."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import customtkinter as ctk
from PIL import Image, UnidentifiedImageError

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
