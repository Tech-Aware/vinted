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
from typing import Dict, List, Optional, Set

from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.backend.customer_responses import (
    ARTICLE_TYPES,
    EXTRA_FIELD_LABELS,
    MESSAGE_TYPE_EXTRA_FIELDS,
    MESSAGE_TYPES,
    SCENARIOS,
    CustomerReplyGenerator,
    CustomerReplyPayload,
    ScenarioConfig,
)
from app.backend.api_key_manager import ensure_api_key
from app.backend.gpt_client import ListingGenerator, ListingResult
from app.backend.image_encoding import encode_images_to_base64
from app.backend.templates import ListingTemplateRegistry
from app.logger import get_logger
from app.ui.image_preview import ImagePreview

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

COMMENT_PLACEHOLDER = "Commentaire prioritaire : séparez vos infos par des virgules (ex : 38FR, évasé, tâche)"


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
        self.reply_generator = CustomerReplyGenerator()
        self.template_registry = ListingTemplateRegistry()
        self.selected_images: List[Path] = []
        self._image_directories: Set[Path] = set()

        self.reply_article_var = ctk.StringVar(value="")
        self.reply_message_type_var = ctk.StringVar(value="")
        self.reply_scenario_var = ctk.StringVar(value="")
        self.reply_client_name_var = ctk.StringVar(value="")
        self.reply_status_var = ctk.StringVar(value="")
        self.reply_field_vars: Dict[str, ctk.StringVar] = {}
        self.reply_message_type_radios: List[ctk.CTkRadioButton] = []
        self.reply_scenario_radios: List[ctk.CTkRadioButton] = []
        self.reply_scenario_frame: Optional[ctk.CTkScrollableFrame] = None
        self.reply_frames_positions: Dict[ctk.CTkFrame, Dict[str, object]] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        self.listing_tab = self.tabview.add("Annonces")
        self.customer_responses_tab = self.tabview.add("Réponses aux clients")

        self._build_listing_tab(self.listing_tab)
        self._build_customer_responses_tab(self.customer_responses_tab)

        self._loading_after_id: Optional[str] = None
        self._loading_step = 0

    def _build_listing_tab(self, parent: ctk.CTkFrame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=1)

        template_frame = ctk.CTkFrame(parent)
        template_frame.grid(row=0, column=0, padx=16, pady=(8, 0), sticky="ew")
        template_frame.columnconfigure(0, weight=1)

        self.template_var = ctk.StringVar(value=self.template_registry.default_template)
        self.template_combo = ctk.CTkComboBox(
            template_frame,
            values=self.template_registry.available_templates,
            variable=self.template_var,
            width=260,
        )
        self.template_combo.grid(row=0, column=0, sticky="w", padx=12, pady=8)
        self._template_combo_default_state = self.template_combo.cget("state") or "normal"

        content_frame = ctk.CTkFrame(parent)
        content_frame.grid(row=1, column=0, padx=16, pady=(8, 8), sticky="nsew")
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)

        self.preview_frame = ImagePreview(content_frame, on_remove=self._remove_image)
        self.preview_frame.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        form_frame = ctk.CTkFrame(parent)
        form_frame.grid(row=2, column=0, padx=16, pady=(8, 8), sticky="nsew")
        form_frame.columnconfigure(0, weight=1)
        form_frame.rowconfigure(4, weight=1)

        self.comment_label = ctk.CTkLabel(
            form_frame,
            text="Commentaire (prioritaire)",
            anchor="w",
            justify="left",
        )
        self.comment_label.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 0))

        self.comment_box = ctk.CTkTextbox(form_frame, height=32)
        self._insert_comment_placeholder()
        self.comment_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        self.comment_box.bind("<FocusIn>", self._on_comment_focus_in)
        self.comment_box.bind("<FocusOut>", self._on_comment_focus_out)

        button_frame = ctk.CTkFrame(form_frame)
        button_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 4))
        button_frame.columnconfigure((0, 1, 2), weight=1)

        self.select_button = ctk.CTkButton(button_frame, text="Ajouter des photos", command=self.select_images)
        self.select_button.grid(row=0, column=0, padx=4, pady=4, sticky="ew")

        self.generate_button = ctk.CTkButton(button_frame, text="Analyser", command=self.generate_listing)
        self.generate_button.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        self.clear_button = ctk.CTkButton(button_frame, text="Réinitialiser", command=self.reset)
        self.clear_button.grid(row=0, column=2, padx=4, pady=4, sticky="ew")

        self._buttons_to_disable = [
            self.select_button,
            self.generate_button,
            self.clear_button,
        ]

        title_container = ctk.CTkFrame(form_frame)
        title_container.grid(row=3, column=0, sticky="nsew", padx=12, pady=(12, 4))
        title_container.columnconfigure(0, weight=1)
        title_container.rowconfigure(0, weight=1)

        self.title_box = ctk.CTkTextbox(title_container, height=48)
        self.title_box.grid(row=0, column=0, sticky="nsew", padx=0, pady=4)
        self._enable_select_all(self.title_box)

        self.title_copy_button = ctk.CTkButton(
            title_container,
            text="📋",
            width=32,
            height=28,
            corner_radius=6,
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            command=lambda: self._copy_to_clipboard(self.title_box),
        )
        self.title_copy_button.place(relx=1.0, rely=0.0, x=-10, y=10, anchor="ne")
        self._buttons_to_disable.append(self.title_copy_button)

        description_container = ctk.CTkFrame(form_frame)
        description_container.grid(row=4, column=0, sticky="nsew", padx=12, pady=(4, 12))
        description_container.columnconfigure(0, weight=1)
        description_container.columnconfigure(1, weight=0)
        description_container.rowconfigure(0, weight=1)
        description_container.rowconfigure(1, weight=0)

        self.price_text = ctk.StringVar(value="Estimation à venir")

        self.description_box = ctk.CTkTextbox(description_container, height=220)
        self.description_box.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=0, pady=4)
        self._enable_select_all(self.description_box)

        self.description_copy_button = ctk.CTkButton(
            description_container,
            text="📋",
            width=32,
            height=28,
            corner_radius=6,
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            command=lambda: self._copy_to_clipboard(self.description_box),
        )
        self.description_copy_button.place(relx=1.0, rely=0.0, x=-10, y=10, anchor="ne")
        self._buttons_to_disable.append(self.description_copy_button)

        self.price_chip = ctk.CTkLabel(
            description_container,
            textvariable=self.price_text,
            anchor="center",
            fg_color=("gray80", "gray25"),
            corner_radius=12,
            padx=10,
            pady=6,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.price_chip.grid(row=1, column=0, columnspan=2, padx=(0, 0), pady=(4, 8), sticky="w")
        description_container.bind("<Configure>", self._update_price_chip_wraplength)
        self.after_idle(self._update_price_chip_wraplength)

    def _build_customer_responses_tab(self, parent: ctk.CTkFrame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        container = ctk.CTkScrollableFrame(parent)
        container.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(3, weight=1)
        container.grid_rowconfigure(5, weight=1)
        self.reply_tab_container = container

        title = ctk.CTkLabel(
            container,
            text="Réponses aux clients",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w", padx=12, pady=(4, 2))

        description = ctk.CTkLabel(
            container,
            text=(
                "Générez des réponses prêtes à coller dans Vinted : choisissez un article, un scénario "
                "et remplissez les champs contextuels si besoin."
            ),
            justify="left",
            anchor="w",
            wraplength=820,
        )
        description.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.reply_description_label = description

        selection_frame = ctk.CTkFrame(container)
        selection_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 8))
        selection_frame.columnconfigure(0, weight=1)
        selection_frame.columnconfigure(1, weight=1)
        selection_frame.columnconfigure(2, weight=2)
        selection_frame.rowconfigure(0, weight=0)
        selection_frame.rowconfigure(1, weight=1)

        identity_frame = ctk.CTkFrame(selection_frame)
        identity_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=8)
        identity_frame.columnconfigure(1, weight=1)

        client_label = ctk.CTkLabel(
            identity_frame,
            text="Nom du client",
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
        )
        client_label.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))

        client_entry = ctk.CTkEntry(
            identity_frame,
            textvariable=self.reply_client_name_var,
            placeholder_text="Saisissez le prénom ou pseudo du client",
        )
        client_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 10))
        client_entry.bind("<KeyRelease>", lambda *_: self._update_reply_visibility())

        article_frame = ctk.CTkFrame(selection_frame)
        article_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=8)
        article_frame.columnconfigure(0, weight=1)

        article_title = ctk.CTkLabel(
            article_frame,
            text="Type d'article",
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
        )
        article_title.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))

        for index, article in enumerate(ARTICLE_TYPES, start=1):
            radio = ctk.CTkRadioButton(
                article_frame,
                text=article.label,
                value=article.id,
                variable=self.reply_article_var,
                command=self._on_reply_article_change,
            )
            radio.grid(row=index, column=0, sticky="w", padx=12, pady=4)

        self.reply_article_frame = article_frame
        self.reply_message_type_frame = ctk.CTkFrame(selection_frame)
        self.reply_message_type_frame.grid(
            row=1, column=1, sticky="nsew", padx=(8, 8), pady=8
        )
        self.reply_message_type_frame.columnconfigure(0, weight=1)

        message_type_title = ctk.CTkLabel(
            self.reply_message_type_frame,
            text="Type de message",
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
        )
        message_type_title.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))

        self.reply_scenario_frame = ctk.CTkScrollableFrame(
            selection_frame, label_text="Scénario de réponse"
        )
        self.reply_scenario_frame.grid(row=1, column=2, sticky="nsew", padx=(8, 0), pady=8)
        self.reply_scenario_frame.columnconfigure(0, weight=1)

        self.reply_extra_container = ctk.CTkFrame(self.reply_scenario_frame)
        self.reply_extra_container.columnconfigure(0, weight=1)

        price_title = ctk.CTkLabel(
            self.reply_extra_container,
            text="Montants de négociation",
            anchor="w",
            font=ctk.CTkFont(weight="bold"),
        )
        price_title.grid(row=0, column=0, sticky="w", padx=6, pady=(8, 4))

        self.reply_inline_price_row = ctk.CTkFrame(self.reply_extra_container)
        for col_index in range(len(EXTRA_FIELD_LABELS)):
            self.reply_inline_price_row.columnconfigure(col_index, weight=1)

        self.reply_extra_field_frames: Dict[str, ctk.CTkFrame] = {}
        self.reply_field_columns: Dict[str, int] = {}
        for index, (field_key, field_label) in enumerate(EXTRA_FIELD_LABELS.items()):
            field_container = ctk.CTkFrame(self.reply_inline_price_row)
            field_container.columnconfigure(0, weight=1)

            label = ctk.CTkLabel(field_container, text=field_label, anchor="w")
            label.grid(row=0, column=0, sticky="w", padx=6, pady=(2, 0))

            entry_var = ctk.StringVar()
            self.reply_field_vars[field_key] = entry_var

            entry = ctk.CTkEntry(field_container, textvariable=entry_var, width=88)
            entry.grid(row=1, column=0, sticky="ew", padx=6, pady=(2, 6))

            field_container.grid(row=0, column=index, sticky="nsew", padx=4, pady=2)

            self.reply_field_columns[field_key] = index
            self.reply_extra_field_frames[field_key] = field_container

        self.reply_inline_price_row.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 8))

        actions_frame = ctk.CTkFrame(container)
        actions_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 8))
        actions_frame.columnconfigure(0, weight=0)
        actions_frame.columnconfigure(1, weight=0)
        actions_frame.columnconfigure(2, weight=1)

        self.reply_generate_button = ctk.CTkButton(
            actions_frame,
            text="Générer la réponse",
            command=self._start_reply_generation,
        )
        self.reply_generate_button.grid(row=0, column=0, padx=8, pady=6, sticky="w")

        self.reply_reset_button = ctk.CTkButton(
            actions_frame,
            text="Réinitialiser",
            command=self.reset_reply,
        )
        self.reply_reset_button.grid(row=0, column=1, padx=8, pady=6, sticky="w")

        status_label = ctk.CTkLabel(actions_frame, textvariable=self.reply_status_var, anchor="w")
        status_label.grid(row=0, column=2, sticky="w", padx=8, pady=6)

        output_frame = ctk.CTkFrame(container)
        output_frame.grid(row=4, column=0, sticky="nsew", padx=12, pady=(4, 8))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)

        output_header = ctk.CTkLabel(
            output_frame,
            text="Réponse générée",
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
        )
        output_header.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))

        output_container = ctk.CTkFrame(output_frame)
        output_container.grid(row=1, column=0, sticky="nsew")
        output_container.columnconfigure(0, weight=1)
        output_container.columnconfigure(1, weight=0)
        output_container.rowconfigure(0, weight=1)

        self.reply_output_box = ctk.CTkTextbox(output_container, height=160)
        self.reply_output_box.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))

        self.reply_copy_button = ctk.CTkButton(
            output_container,
            text="📋",
            width=32,
            height=28,
            corner_radius=6,
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            command=lambda: self._copy_to_clipboard(self.reply_output_box),
        )
        self.reply_copy_button.grid(row=0, column=1, sticky="ne", padx=(4, 8), pady=(0, 8))

        self.reply_context_frame = None
        self.reply_actions_frame = actions_frame
        self.reply_output_frame = output_frame
        self.reply_frames_positions = {
            self.reply_article_frame: dict(
                row=1, column=0, sticky="nsew", padx=(0, 8), pady=8
            ),
            self.reply_message_type_frame: dict(
                row=1, column=1, sticky="nsew", padx=(8, 8), pady=8
            ),
            self.reply_scenario_frame: dict(
                row=1, column=2, sticky="nsew", padx=(8, 0), pady=8
            ),
            self.reply_actions_frame: dict(
                row=3, column=0, sticky="ew", padx=12, pady=(4, 8)
            ),
            self.reply_output_frame: dict(
                row=4, column=0, sticky="nsew", padx=12, pady=(4, 8)
            ),
        }

        self._render_message_types()
        self._render_reply_scenarios()
        self._refresh_extra_fields()
        self._update_reply_visibility()
        parent.bind("<Configure>", self._on_reply_tab_resize)

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

        comment = self._normalize_comment(self.comment_box.get("1.0", "end"))
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
        self.reply_status_var.set("Sélectionnez un type d'article pour commencer.")
        sku_missing = getattr(result, "sku_missing", False)
        placeholder_in_title = "SKU/nc" in (result.title or "")

        if sku_missing or placeholder_in_title:
            logger.warning("SKU manquant détecté dans le résultat, notification utilisateur")
            self._show_error_popup("Sku non visible, merci de le fournir puis recommencer")
            return

        self.title_box.delete("1.0", "end")
        self.title_box.insert("1.0", result.title)

        if result.price_estimate:
            self.price_text.set(result.price_estimate)
        else:
            self.price_text.set("Estimation indisponible")

        self.description_box.delete("1.0", "end")
        self.description_box.insert("1.0", result.description)
        logger.success("Résultat affiché à l'utilisateur")

    def reset(self) -> None:
        self._stop_loading_state()
        self._cleanup_image_directories()
        self.selected_images.clear()
        self._image_directories.clear()
        self.preview_frame.update_images([])
        self.title_box.delete("1.0", "end")
        self.price_text.set("Estimation à venir")
        self.description_box.delete("1.0", "end")
        self._insert_comment_placeholder()
        logger.step("Application réinitialisée")

    def reset_reply(self) -> None:
        self._set_reply_loading_state(False)
        self.reply_client_name_var.set("")
        self.reply_article_var.set("")
        self.reply_message_type_var.set("")
        self.reply_scenario_var.set("")
        for field_var in self.reply_field_vars.values():
            field_var.set("")
        self.reply_output_box.delete("1.0", "end")
        self.reply_inline_price_row.grid_remove()
        self.reply_extra_container.grid_remove()
        self.reply_status_var.set("Renseignez le nom du client pour poursuivre.")
        self._update_reply_visibility()

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
        if self._loading_after_id is not None:
            self.after_cancel(self._loading_after_id)
            self._loading_after_id = None
        self._set_controls_enabled(False)
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
        self.generate_button.configure(text="Analyser")
        self._set_controls_enabled(True)

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self._buttons_to_disable:
            try:
                button.configure(state=state)
            except Exception:
                continue
        combo_state = self._template_combo_default_state if enabled else "disabled"
        try:
            self.template_combo.configure(state=combo_state)
        except Exception:
            pass
        self.preview_frame.set_removal_enabled(enabled)

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

    def _insert_comment_placeholder(self) -> None:
        self.comment_box.delete("1.0", "end")
        self.comment_box.insert("1.0", COMMENT_PLACEHOLDER)

    def _on_comment_focus_in(self, event: object) -> None:
        current_text = self.comment_box.get("1.0", "end").strip()
        if current_text == COMMENT_PLACEHOLDER:
            self.comment_box.delete("1.0", "end")

    def _on_comment_focus_out(self, event: object) -> None:
        current_text = self.comment_box.get("1.0", "end").strip()
        if not current_text:
            self._insert_comment_placeholder()

    @staticmethod
    def _normalize_comment(value: str) -> str:
        cleaned = value.strip()
        if cleaned == COMMENT_PLACEHOLDER:
            return ""
        return cleaned

    def _copy_to_clipboard(self, textbox: ctk.CTkTextbox) -> None:
        content = textbox.get("1.0", "end-1c")
        if not content:
            return

        self.clipboard_clear()
        self.clipboard_append(content)
        logger.info("Contenu copié dans le presse-papiers")

    def _on_reply_tab_resize(self, event: Optional[object] = None) -> None:
        """Ensure reply tab texts wrap within the available width."""

        try:
            available_width = max(int(getattr(event, "width", 0)) - 64, 360)
        except Exception:
            return

        try:
            if hasattr(self, "reply_description_label"):
                self.reply_description_label.configure(wraplength=available_width)
        except Exception:
            pass

    def _render_message_types(self) -> None:
        for radio in self.reply_message_type_radios:
            radio.destroy()
        self.reply_message_type_radios.clear()

        for index, message_type in enumerate(MESSAGE_TYPES, start=1):
            radio = ctk.CTkRadioButton(
                self.reply_message_type_frame,
                text=message_type.label,
                value=message_type.id,
                variable=self.reply_message_type_var,
                command=self._on_reply_message_type_change,
            )
            radio.grid(row=index, column=0, sticky="w", padx=12, pady=4)
            self.reply_message_type_radios.append(radio)

    def _get_visible_reply_scenarios(self) -> List[ScenarioConfig]:
        selected_message_type = self.reply_message_type_var.get()
        selected_article = self.reply_article_var.get()

        scenarios = list(SCENARIOS.values())
        if selected_message_type:
            scenarios = [
                scenario
                for scenario in scenarios
                if scenario.message_type_id == selected_message_type
            ]
        if selected_article:
            scenarios = [
                scenario
                for scenario in scenarios
                if scenario.allowed_articles is None
                or selected_article in scenario.allowed_articles
            ]

        return scenarios

    def _render_reply_scenarios(self) -> None:
        if not self.reply_scenario_frame:
            return

        for radio in self.reply_scenario_radios:
            radio.destroy()
        self.reply_scenario_radios.clear()

        visible_scenarios = self._get_visible_reply_scenarios()
        if self.reply_scenario_var.get() not in {s.id for s in visible_scenarios}:
            self.reply_scenario_var.set("")

        if not visible_scenarios and self.reply_message_type_var.get():
            self.reply_status_var.set("Aucun scénario compatible pour ce couple article / message.")

        for index, scenario in enumerate(visible_scenarios):
            radio = ctk.CTkRadioButton(
                self.reply_scenario_frame,
                text=scenario.label,
                value=scenario.id,
                variable=self.reply_scenario_var,
                command=self._on_reply_scenario_change,
            )
            radio.grid(row=index, column=0, sticky="w", padx=8, pady=4)
            self.reply_scenario_radios.append(radio)

        self.reply_extra_container.grid_remove()
        self.reply_extra_container_row = len(visible_scenarios) + 1

        self._update_reply_visibility()

    def _on_reply_article_change(self) -> None:
        self.reply_message_type_var.set("")
        self.reply_scenario_var.set("")
        self.reply_status_var.set("Sélectionnez un type de message.")
        self._render_reply_scenarios()
        self._refresh_extra_fields()
        self._update_reply_visibility()

    def _on_reply_message_type_change(self) -> None:
        self.reply_scenario_var.set("")
        self.reply_status_var.set("Sélectionnez un scénario adapté.")
        self._render_reply_scenarios()
        self._refresh_extra_fields()
        self._update_reply_visibility()

    def _on_reply_scenario_change(self) -> None:
        self._refresh_extra_fields()
        self._update_reply_visibility()

    def _refresh_extra_fields(self) -> None:
        scenario_id = self.reply_scenario_var.get()
        scenario = SCENARIOS.get(scenario_id)
        message_type_extras = MESSAGE_TYPE_EXTRA_FIELDS.get(
            self.reply_message_type_var.get(), ()
        )

        for frame in self.reply_extra_field_frames.values():
            frame.grid_remove()

        self.reply_inline_price_row.grid_remove()
        self.reply_extra_container.grid_remove()

        if not scenario:
            self.reply_status_var.set(
                "Sélectionnez un article, un type de message puis un scénario compatible."
            )
            return

        merged_fields = list(dict.fromkeys((*message_type_extras, *scenario.extra_fields)))

        if merged_fields:
            self.reply_inline_price_row.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 8))

            for field_key in merged_fields:
                frame = self.reply_extra_field_frames.get(field_key)
                if frame is None:
                    continue
                column = self.reply_field_columns.get(field_key, 0)
                frame.grid(row=0, column=column, sticky="nsew", padx=4, pady=2)

            self.reply_extra_container.grid(
                row=getattr(self, "reply_extra_container_row", 1),
                column=0,
                sticky="ew",
                padx=8,
                pady=(8, 8),
            )

        self.reply_status_var.set("")

    def _update_reply_visibility(self) -> None:
        client_name = self.reply_client_name_var.get().strip()
        has_client = bool(client_name)
        has_article = bool(self.reply_article_var.get())
        has_message_type = bool(self.reply_message_type_var.get())
        has_scenario = bool(self.reply_scenario_var.get())

        def show_frame(frame: Optional[ctk.CTkFrame]) -> None:
            if frame is None:
                return
            grid_kwargs = self.reply_frames_positions.get(frame)
            if grid_kwargs:
                frame.grid(**grid_kwargs)

        def hide_frame(frame: Optional[ctk.CTkFrame]) -> None:
            if frame is None:
                return
            frame.grid_remove()

        if has_client:
            show_frame(self.reply_article_frame)
            if not has_article:
                self.reply_status_var.set("Sélectionnez un type d'article.")
        else:
            hide_frame(self.reply_article_frame)
            self.reply_status_var.set("Renseignez le nom du client pour poursuivre.")

        if has_client and has_article:
            show_frame(self.reply_message_type_frame)
            if not has_message_type:
                self.reply_status_var.set("Choisissez un type de message.")
        else:
            hide_frame(self.reply_message_type_frame)

        if has_client and has_article and has_message_type:
            show_frame(self.reply_scenario_frame)
        else:
            hide_frame(self.reply_scenario_frame)

        if has_client and has_scenario:
            show_frame(self.reply_actions_frame)
            show_frame(self.reply_output_frame)
        else:
            hide_frame(self.reply_actions_frame)
            hide_frame(self.reply_output_frame)

    @staticmethod
    def _parse_float_value(raw_value: str) -> Optional[float]:
        cleaned = raw_value.strip().replace(",", ".")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _build_reply_payload(self) -> Optional[CustomerReplyPayload]:
        client_name = self.reply_client_name_var.get().strip()
        article_type = self.reply_article_var.get()
        message_type = self.reply_message_type_var.get()
        scenario_id = self.reply_scenario_var.get()
        scenario = SCENARIOS.get(scenario_id)
        message_type_extras = MESSAGE_TYPE_EXTRA_FIELDS.get(
            self.reply_message_type_var.get(), ()
        )

        if not client_name:
            self._show_error_popup("Renseignez le nom du client.")
            return None
        if not article_type:
            self._show_error_popup("Sélectionnez un type d'article.")
            return None
        if not message_type:
            self._show_error_popup("Sélectionnez un type de message.")
            return None
        if scenario is None:
            self._show_error_popup("Sélectionnez un scénario de réponse.")
            return None

        missing_fields: List[str] = []
        numeric_fields = {"offre_client", "contre_offre", "prix_ferme"}
        numeric_values: Dict[str, Optional[float]] = {}

        required_fields = list(dict.fromkeys((*message_type_extras, *scenario.extra_fields)))

        for field_key in required_fields:
            raw_value = self.reply_field_vars.get(field_key, ctk.StringVar()).get().strip()
            if not raw_value:
                missing_fields.append(EXTRA_FIELD_LABELS.get(field_key, field_key))
                continue
            if field_key in numeric_fields:
                parsed = self._parse_float_value(raw_value)
                if parsed is None:
                    self._show_error_popup(
                        f"Le champ {EXTRA_FIELD_LABELS.get(field_key, field_key)} doit être un nombre."
                    )
                    return None
                numeric_values[field_key] = parsed

        if missing_fields:
            self._show_error_popup(
                "Complétez les champs requis : " + ", ".join(sorted(set(missing_fields)))
            )
            return None

        payload = CustomerReplyPayload(
            client_name=client_name,
            article_type=article_type,
            scenario_id=scenario_id,
            client_message="",
            offre_client=numeric_values.get("offre_client"),
            contre_offre=numeric_values.get("contre_offre"),
            prix_ferme=numeric_values.get("prix_ferme"),
        )
        return payload

    def _start_reply_generation(self) -> None:
        payload = self._build_reply_payload()
        if payload is None:
            return

        self.reply_status_var.set("Génération en cours...")
        self._set_reply_loading_state(True)
        self.reply_output_box.delete("1.0", "end")

        def worker() -> None:
            try:
                reply = self.reply_generator.generate_reply(payload)
                self.after(0, lambda: self._handle_reply_result(reply))
            except Exception as exc:  # pragma: no cover - UI feedback
                logger.exception("Erreur lors de la génération de la réponse client")
                self.after(0, lambda err=exc: self._handle_reply_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_reply_result(self, reply: str) -> None:
        self._set_reply_loading_state(False)
        self.reply_status_var.set("Réponse prête ✅")
        self.reply_output_box.delete("1.0", "end")
        self.reply_output_box.insert("1.0", reply)

    def _handle_reply_error(self, error: Exception) -> None:
        self._set_reply_loading_state(False)
        self.reply_status_var.set("Erreur lors de la génération")
        self._show_error_popup(f"Erreur: {error}")

    def _set_reply_loading_state(self, loading: bool) -> None:
        state = "disabled" if loading else "normal"
        try:
            self.reply_generate_button.configure(state=state)
        except Exception:
            pass

    def _update_price_chip_wraplength(self, event: Optional[object] = None) -> None:
        try:
            container_width = int(getattr(event, "width", self.price_chip.winfo_width()))
        except Exception:
            return

        usable_width = max(container_width - 24, 120)
        self.price_chip.configure(wraplength=usable_width)
