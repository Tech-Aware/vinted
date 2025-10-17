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

"""Listing templates and prompts for the Vinted assistant."""

from dataclasses import dataclass
from textwrap import dedent
from typing import Dict, List, Optional, Tuple

from app.backend.defect_catalog import get_defect_descriptions
from app.backend.listing_fields import ListingFields
from app.backend.sizing import NormalizedSizes, normalize_sizes
from app.backend.text_normalization import normalize_fit_terms


def _ensure_percent(value: Optional[str]) -> str:
    if not value:
        return "0%"
    stripped = value.strip()
    if stripped.endswith("%"):
        return stripped
    return f"{stripped}%"


def _clean(value: Optional[str], fallback: str = "NC") -> str:
    text = (value or "").strip()
    return text if text else fallback


@dataclass
class ListingTemplate:
    name: str
    description: str
    prompt: str

    def render(self, fields: ListingFields) -> Tuple[str, str]:
        fit_title, fit_description, fit_hashtag = normalize_fit_terms(fields.fit_leg)
        normalized_sizes: NormalizedSizes = normalize_sizes(fields.us_w, fields.fr_size, fields.has_elastane)

        fr_display = normalized_sizes.fr_size or (fields.fr_size or "")
        us_display = normalized_sizes.us_size
        size_note = normalized_sizes.note

        model = _clean(fields.model, "Levi's")
        gender = _clean(fields.gender, "femme")
        color = _clean(fields.color_main, "bleu")
        rise = _clean(fields.rise_class, "moyenne")
        cotton = _ensure_percent(fields.cotton_pct)
        polyester_pct = fields.polyester_pct
        elastane_pct = fields.elastane_pct
        composition_parts = [f"{cotton} coton"]
        if fields.has_polyester:
            composition_parts.append(f"{_ensure_percent(polyester_pct)} polyester")
        if fields.has_elastane:
            composition_parts.append(f"{_ensure_percent(elastane_pct)} élasthanne")
        composition = ", ".join(composition_parts)
        defect_texts = get_defect_descriptions(fields.defect_tags)
        raw_defects = (fields.defects or "").strip()

        positive_state_aliases = {
            "très bon état",
            "très bon état général",
        }
        positive_state_aliases_casefold = {alias.casefold() for alias in positive_state_aliases}
        if raw_defects.casefold() in positive_state_aliases_casefold:
            raw_defects = ""

        if defect_texts:
            defects = "; ".join(defect_texts)
        else:
            defects = raw_defects if raw_defects else ""
        sku = _clean(fields.sku, "SKU")
        fit_title_text = fit_title or _clean(fields.fit_leg)
        fit_description_text = fit_description or _clean(fields.fit_leg)
        fit_hashtag_text = fit_hashtag or _clean(fields.fit_leg).lower().replace(" ", "")

        title_parts = [
            f"Jean Levi’s {model}",
            f"FR{fr_display}" if fr_display else "",
            f"W{us_display}" if us_display else "",
            f"L{fields.us_l}" if fields.us_l else "",
            "coupe",
            fit_title_text,
            f"{cotton} coton",
            gender,
            color,
            "-",
            sku,
        ]
        title = " ".join(part for part in title_parts if part).replace("  ", " ").strip()

        if us_display:
            size_sentence = f"Taille {us_display} US (équivalent {fr_display} FR), coupe {fit_description_text} à taille {rise}, pour une silhouette ajustée et confortable."
        elif fr_display:
            size_sentence = f"Taille {fr_display} FR, coupe {fit_description_text} à taille {rise}, pour une silhouette ajustée et confortable."
        else:
            size_sentence = f"Coupe {fit_description_text} à taille {rise}, pour une silhouette ajustée et confortable."

        first_paragraph_lines = [
            f"Jean Levi’s modèle {model} pour {gender}.",
            size_sentence,
        ]
        if size_note:
            first_paragraph_lines.append(size_note)

        second_paragraph_lines = [
            f"Coloris {color} légèrement délavé, très polyvalent et facile à assortir.",
            f"Composition : {composition} pour une touche de stretch et plus de confort.",
            "Fermeture zippée + bouton gravé Levi’s.",
        ]

        third_paragraph_lines: List[str] = []
        if defects:
            third_paragraph_lines.append(f"Très bon état {defects} (voir photos)")
        else:
            third_paragraph_lines.append("Très bon état")

        if not fields.size_label_visible and not fields.fabric_label_visible:
            third_paragraph_lines.append(
                "Étiquettes composition/taille coupées pour plus de confort."
            )
        elif not fields.size_label_visible:
            third_paragraph_lines.append(
                "Étiquette taille coupée pour plus de confort."
            )
        elif not fields.fabric_label_visible:
            third_paragraph_lines.append(
                "Étiquette composition coupée pour plus de confort."
            )

        third_paragraph_lines.extend(
            [
                "📏 Mesures précises visibles en photo.",
                "📦 Envoi rapide et soigné",
            ]
        )

        fourth_paragraph_lines = [
            f"✨ Retrouvez tous mes articles Levi’s à votre taille ici 👉 #durin31fr{fr_display or 'nc'}",
            "💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !",
        ]

        hashtags_paragraph_lines = [
            "#levis #jeanlevis "
            f"#levis{gender.lower()} #{fit_hashtag_text}jean #jeandenim #{rise} #jean{color.lower().replace(' ', '')} #vintedfr "
            f"#durin31fr{fr_display or 'nc'}",
        ]

        description = "\n\n".join(
            [
                "\n".join(first_paragraph_lines),
                "\n".join(second_paragraph_lines),
                "\n".join(third_paragraph_lines),
                "\n".join(fourth_paragraph_lines),
                "\n".join(hashtags_paragraph_lines),
            ]
        ).strip()

        return title, description


class ListingTemplateRegistry:
    """Registry holding available listing templates."""

    def __init__(self) -> None:
        self._templates: Dict[str, ListingTemplate] = {
            "template-jean-levis-femme": ListingTemplate(
                name="template-jean-levis-femme",
                description="Template Levi's femme",
                prompt=dedent(
                    """
                    Prend en considération cette légende : 
                    - Taille FR = taille française en cm, au format FR{{fr_size}}
                    - Modèle = code numérique du jean (ex: 501). Ajoute uniquement le mot "Premium" si et seulement si indiqué sur l'étiquette.
                    - Wn Ln = valeurs d’étiquette, {{w}} et {{l}}
                    - Coupe = {{fit_leg}} (insère la hauteur de taille {{rise_class}} dans la description uniquement, jamais dans le titre)
                    - Matière = {{cotton_pct}}% coton (+ {{polyester_pct}}% polyester si présent, + {{elastane_pct}}% élasthanne si présent)
                    - Genre = {{gender}}  (valeurs attendues : femme, homme, mix)
                    - Tâches et défauts = Ce qui doit impérativement apparaître dans l'annonce si identifié sur photos ou fournit en commentaire {{defects}}
                    - SKU = {{sku}} (utilise JLF + numéro (1 à 3 chiffres) si jean femme, JLH + numéro si jean homme ;
                      reprends exactement le numéro présent sur l’étiquette blanche visible sur le jean)

                    Utilise ce format :
                    TITRE
                    Jean Levi’s {{model}} FR{{fr_size}} W{{w}} L{{l}} coupe {{fit_leg}} {{cotton_pct}}% coton {{gender}} {{color_main}} - {{sku}}
                    
                    DESCRIPTION + HASHTAG
                    Jean Levi’s modèle {{model}} pour {{gender}}.
                    Taille {{w}} US (équivalent {{fr_size}} FR), coupe {{fit_leg}} à taille {{rise_class}}, pour une silhouette ajustée et confortable.
                    Coloris {{color_main}} légèrement délavé, très polyvalent et facile à assortir.
                    Composition : {{cotton_pct}}% coton{{#if polyester_pct}}, {{polyester_pct}}% polyester{{/if}}{{#if elastane_pct}}, {{elastane_pct}}% élasthanne{{/if}} pour une touche de stretch et plus de confort.
                    Fermeture zippée + bouton gravé Levi’s.
                    
                    Très bon état général {{defects}} (voir photos). S'il n'y a aucun défaut à signaler, écris simplement « Très bon état ».
                    📏 Mesures précises visibles en photo.
                    📦 Envoi rapide et soigné
                    
                    ✨ Retrouvez tous mes articles Levi’s à votre taille ici 👉 #durin31fr{{fr_size}}
                    💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !
                    
                    #levis #jeanlevis #levis{{gender}} #{{fit_leg}}jean #jeandenim #{{rise_class}} #jean{{color_main}} #vintedfr #durin31fr{{fr_size}}

                    Remplis les champs entre accolades en analysant les photos et en utilisant les commentaires.
                    """
                ).strip(),
            )
        }
        self.default_template = "template-jean-levis-femme"

    @property
    def available_templates(self) -> List[str]:
        return list(self._templates)

    def get_prompt(self, name: str) -> str:
        if name not in self._templates:
            raise KeyError(f"Template inconnu: {name}")
        return self._templates[name].prompt

    def get_template(self, name: str) -> ListingTemplate:
        if name not in self._templates:
            raise KeyError(f"Template inconnu: {name}")
        return self._templates[name]
