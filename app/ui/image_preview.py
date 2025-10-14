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
        self._image_paths: List[Path] = []

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
        self._image_paths = list(paths)

        if not self._image_paths:
            self._show_empty_state()
            return

        for path in self._image_paths:
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
        for index, (image, path) in enumerate(zip(self._preview_images, self._image_paths)):
            label = ctk.CTkLabel(self._gallery_container, image=image, text="", cursor="hand2")
            label.grid(row=index, column=0, sticky="ew", padx=8, pady=(8 if index == 0 else 4, 4))
            label.bind("<Button-1>", lambda _event, p=path: self._open_full_image(p))
            self._labels.append(label)
        logger.success("%d vignette(s) générée(s)", len(self._preview_images))

    def _open_full_image(self, path: Path) -> None:
        try:
            with Image.open(path) as pil_img:
                display_img = pil_img.copy()
        except (UnidentifiedImageError, OSError) as exc:
            logger.error("Impossible d'ouvrir l'image %s", path, exc_info=exc)
            return

        top = ctk.CTkToplevel(self)
        top.title(path.name)
        top.transient(self.winfo_toplevel())
        top.focus()

        screen_w = top.winfo_screenwidth()
        screen_h = top.winfo_screenheight()
        max_size = (int(screen_w * 0.8), int(screen_h * 0.8))
        display_img.thumbnail(max_size)

        tk_img = ctk.CTkImage(light_image=display_img, dark_image=display_img, size=display_img.size)
        image_label = ctk.CTkLabel(top, image=tk_img, text="")
        image_label.pack(padx=16, pady=16)

        close_button = ctk.CTkButton(top, text="Fermer", command=top.destroy)
        close_button.pack(pady=(0, 16))

        top.bind("<Escape>", lambda _event: top.destroy())
        top._image_ref = tk_img  # type: ignore[attr-defined]
