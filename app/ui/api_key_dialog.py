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

"""Modal dialog prompting the user to configure the OpenAI API key."""
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from app.backend.api_key_manager import save_api_key
from app.logger import get_logger


logger = get_logger(__name__)


class APIKeyDialog(ctk.CTkToplevel):
    """Dialog window shown when no OpenAI API key is configured."""

    def __init__(self, master) -> None:
        super().__init__(master)
        self.title("Configuration de l'API OpenAI")
        self.geometry("420x220")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.focus_force()

        self.columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        description = (
            "Aucune clé API OpenAI n'a été trouvée. \n"
            "Veuillez saisir votre clé personnelle pour continuer."
        )
        ctk.CTkLabel(self, text=description, wraplength=360, justify="left").grid(
            row=0, column=0, padx=24, pady=(24, 12), sticky="w"
        )

        self._api_key_var = ctk.StringVar()
        entry = ctk.CTkEntry(self, textvariable=self._api_key_var, show="*")
        entry.grid(row=1, column=0, padx=24, sticky="ew")
        entry.focus_set()

        button_frame = ctk.CTkFrame(self)
        button_frame.grid(row=2, column=0, padx=24, pady=(18, 24), sticky="e")
        button_frame.columnconfigure((0, 1), weight=1)

        save_button = ctk.CTkButton(button_frame, text="Enregistrer", command=self._save)
        save_button.grid(row=0, column=0, padx=(0, 8))

        cancel_button = ctk.CTkButton(button_frame, text="Annuler", command=self._cancel)
        cancel_button.grid(row=0, column=1)

        self.bind("<Return>", lambda _event: self._save())
        self.bind("<Escape>", lambda _event: self._cancel())

    def _save(self) -> None:
        api_key = self._api_key_var.get()
        try:
            save_api_key(api_key)
        except ValueError:
            logger.warning("Tentative de sauvegarde d'une clé API vide")
            messagebox.showerror("Erreur", "La clé API est obligatoire.")
            return
        except RuntimeError:
            logger.exception("Impossible de sauvegarder la clé API")
            messagebox.showerror(
                "Erreur", "Impossible de sauvegarder la clé API. Merci de réessayer."
            )
            return
        logger.success("Clé API fournie par l'utilisateur")
        self.grab_release()
        self.destroy()

    def _cancel(self) -> None:
        logger.info("L'utilisateur a annulé la configuration de la clé API")
        self.grab_release()
        self.destroy()
