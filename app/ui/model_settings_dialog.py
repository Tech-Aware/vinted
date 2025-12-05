"""Boîte de dialogue pour visualiser et ajouter des modèles API."""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from app.backend.model_settings import add_model, mask_api_key, save_model_settings
from app.backend.model_settings import apply_current_model, load_model_settings, ModelSettings
from app.logger import get_logger


logger = get_logger(__name__)


class ModelSettingsDialog(ctk.CTkToplevel):
    """Fenêtre modale permettant d'ajouter ou d'afficher un modèle API."""

    def __init__(self, master, settings: ModelSettings) -> None:
        super().__init__(master)
        self.title("Paramètres API")
        self.geometry("520x360")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.focus_force()

        self.settings = settings
        self.result_settings: ModelSettings | None = None

        self.columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._build_current_section()
        self._build_add_section()

    def _build_current_section(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, padx=20, pady=(18, 12), sticky="nsew")
        frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Modèle actif", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(4, 8)
        )

        ctk.CTkLabel(frame, text="Nom :").grid(row=1, column=0, sticky="w", padx=(0, 8))
        self._model_label = ctk.CTkLabel(frame, text=self.settings.current_entry.name)
        self._model_label.grid(row=1, column=1, sticky="w")

        ctk.CTkLabel(frame, text="Fournisseur :").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        self._provider_label = ctk.CTkLabel(frame, text=self.settings.current_entry.provider)
        self._provider_label.grid(row=2, column=1, sticky="w", pady=(6, 0))

        ctk.CTkLabel(frame, text="Clé API :").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        self._api_label = ctk.CTkLabel(frame, text=mask_api_key(self.settings.current_entry.api_key))
        self._api_label.grid(row=3, column=1, sticky="w", pady=(6, 0))

    def _build_add_section(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.grid(row=1, column=0, padx=20, pady=(8, 16), sticky="nsew")
        frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Ajouter un modèle", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(8, 4)
        )

        self._new_model_var = ctk.StringVar()
        model_entry = ctk.CTkEntry(frame, textvariable=self._new_model_var, placeholder_text="Nom exact du modèle")
        model_entry.grid(row=1, column=0, sticky="ew", pady=(4, 4))

        self._new_provider_var = ctk.StringVar(value="openai")
        provider_option = ctk.CTkOptionMenu(
            frame,
            values=["openai", "gemini"],
            variable=self._new_provider_var,
        )
        provider_option.grid(row=2, column=0, sticky="ew", pady=(4, 4))

        self._new_key_var = ctk.StringVar()
        key_entry = ctk.CTkEntry(
            frame,
            textvariable=self._new_key_var,
            placeholder_text="Clé API (sk-...)",
            show="*",
        )
        key_entry.grid(row=3, column=0, sticky="ew", pady=(4, 8))

        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.grid(row=4, column=0, sticky="e", pady=(8, 8))
        button_frame.columnconfigure((0, 1), weight=1)

        add_button = ctk.CTkButton(button_frame, text="+ Ajouter", command=self._add_model)
        add_button.grid(row=0, column=0, padx=(0, 8))

        close_button = ctk.CTkButton(button_frame, text="Fermer", command=self._close)
        close_button.grid(row=0, column=1)

        model_entry.focus_set()

    def _add_model(self) -> None:
        try:
            updated = add_model(
                self.settings,
                name=self._new_model_var.get(),
                api_key=self._new_key_var.get(),
                provider=self._new_provider_var.get(),
            )
        except ValueError as exc:
            messagebox.showerror("Erreur", str(exc))
            return

        try:
            save_model_settings(updated)
        except OSError:
            messagebox.showerror("Erreur", "Impossible d'enregistrer le modèle.")
            logger.exception("Sauvegarde du modèle échouée")
            return

        self.settings = updated
        self.result_settings = updated
        self._refresh_current_model()
        messagebox.showinfo("Succès", f"Le modèle '{updated.current_model}' a été ajouté et activé.")
        apply_current_model(updated)

    def _refresh_current_model(self) -> None:
        current = load_model_settings()
        self.settings = current
        self._model_label.configure(text=current.current_entry.name)
        self._provider_label.configure(text=current.current_entry.provider)
        self._api_label.configure(text=mask_api_key(current.current_entry.api_key))

    def _close(self) -> None:
        self.grab_release()
        self.destroy()
