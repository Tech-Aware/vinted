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
from app.backend.sizing import (
    NormalizedSizes,
    fr_size_from_waist_measurement,
    normalize_sizes,
)
from app.backend.text_normalization import normalize_fit_terms, translate_color_to_french


def _ensure_percent(value: Optional[str]) -> str:
    if not value:
        return ""
    stripped = value.strip()
    if stripped.endswith("%"):
        return stripped
    return f"{stripped}%"


def _clean(value: Optional[str]) -> str:
    return (value or "").strip()


def _join_fibers(parts: List[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} et {parts[1]}"
    return f"{', '.join(parts[:-1])} et {parts[-1]}"


@dataclass
class ListingTemplate:
    name: str
    description: str
    prompt: str

    def render(self, fields: ListingFields) -> Tuple[str, str]:
        fit_title, fit_description, fit_hashtag = normalize_fit_terms(fields.fit_leg)
        measurement_fr = fr_size_from_waist_measurement(
            fields.waist_measurement_cm, ensure_even=True
        )

        if fields.size_label_visible:
            normalized_sizes: NormalizedSizes = normalize_sizes(
                fields.us_w,
                fields.fr_size,
                fields.has_elastane,
                ensure_even_fr=True,
                waist_measurement_cm=fields.waist_measurement_cm,
            )
            fr_display = normalized_sizes.fr_size or _clean(fields.fr_size)
            us_display = normalized_sizes.us_size
            size_note = normalized_sizes.note
        else:
            fr_candidate = _clean(fields.fr_size)
            us_candidate = _clean(fields.us_w)
            size_note = None
            if not fr_candidate and not us_candidate and measurement_fr:
                fr_display = measurement_fr
                us_display = None
                measurement_value = fields.waist_measurement_cm
                if measurement_value is not None:
                    size_note = (
                        "Taille estimée à partir d'un tour de taille mesuré à environ "
                        f"{int(round(measurement_value))} cm."
                    )
                else:
                    size_note = (
                        "Taille estimée à partir du tour de taille mesuré visuellement sur les photos."
                    )
            else:
                fr_display = fr_candidate
                us_display = None

        model = (fields.model or "").strip()
        gender = _clean(fields.gender)
        gender_value = gender
        color = translate_color_to_french(fields.color_main)
        color = _clean(color)
        rise = _clean(fields.resolved_rise_class)
        cotton = _ensure_percent(fields.cotton_pct) if fields.fabric_label_visible else ""
        polyester_value = (
            _ensure_percent(fields.polyester_pct) if fields.fabric_label_visible else ""
        )
        viscose_value = (
            _ensure_percent(fields.viscose_pct) if fields.fabric_label_visible else ""
        )
        elastane_value = (
            _ensure_percent(fields.elastane_pct) if fields.fabric_label_visible else ""
        )

        composition_parts: List[str] = []
        if fields.fabric_label_visible:
            if cotton:
                composition_parts.append(f"{cotton} coton")
            if fields.has_viscose and viscose_value:
                composition_parts.append(f"{viscose_value} viscose")
            if fields.has_polyester and polyester_value:
                composition_parts.append(f"{polyester_value} polyester")
            if fields.has_elastane and elastane_value:
                composition_parts.append(f"{elastane_value} élasthanne")
            if composition_parts:
                composition_sentence = (
                    f"Composition : {_join_fibers(composition_parts)}."
                )
            else:
                composition_sentence = (
                    "Composition indiquée sur l'étiquette (voir photos pour les détails)."
                )
        else:
            composition_sentence = (
                "Composition non visible sur les photos (étiquette absente ou illisible)."
            )

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
            defects = ", ".join(defect_texts)
        else:
            defects = raw_defects if raw_defects else ""
        sku = (fields.sku or "").strip()
        fit_title_text = fit_title or _clean(fields.fit_leg)
        fit_description_text = fit_description or _clean(fields.fit_leg)
        fit_hashtag_source = fit_hashtag or _clean(fields.fit_leg)
        fit_hashtag_text = (
            fit_hashtag_source.lower().replace(" ", "") if fit_hashtag_source else ""
        )

        title_intro = "Jean Levi’s"
        if model:
            title_intro = f"{title_intro} {model}"

        cotton_title_segment = f"{cotton} coton" if cotton else ""
        title_parts: List[str] = [title_intro]
        if fr_display:
            title_parts.append(f"FR{fr_display}")
        if fields.size_label_visible and us_display:
            title_parts.append(f"W{us_display}")
        if fields.size_label_visible and fields.us_l:
            title_parts.append(f"L{fields.us_l}")
        if fit_title_text:
            title_parts.extend(["coupe", fit_title_text])
        if cotton_title_segment:
            title_parts.append(cotton_title_segment)
        if gender_value:
            title_parts.append(gender_value)
        if color:
            title_parts.append(color)
        if sku:
            title_parts.extend(["-", sku])
        title = " ".join(part for part in title_parts if part).replace("  ", " ").strip()

        size_fragments: List[str] = []
        if us_display and fr_display:
            size_fragments.append(f"Taille {us_display} US (équivalent {fr_display} FR)")
        elif us_display:
            size_fragments.append(f"Taille {us_display} US")
        elif fr_display:
            size_fragments.append(f"Taille {fr_display} FR")
        else:
            size_fragments.append("Taille non précisée")
        fit_phrase = fit_description_text or "non précisée"
        rise_phrase = rise or "non précisée"
        size_fragments.append(f"coupe {fit_phrase}")
        size_fragments.append(f"à taille {rise_phrase}")
        size_sentence = ", ".join(size_fragments) + ", pour une silhouette ajustée et confortable."

        if model and gender_value:
            first_sentence = f"Jean Levi’s modèle {model} pour {gender_value}."
        elif model:
            first_sentence = f"Jean Levi’s modèle {model}."
        elif gender_value:
            first_sentence = f"Jean Levi’s pour {gender_value}."
        else:
            first_sentence = "Jean Levi’s."

        first_paragraph_lines = [
            first_sentence,
            size_sentence,
        ]
        if size_note:
            first_paragraph_lines.append(size_note)

        if color:
            color_sentence = (
                f"Coloris {color} légèrement délavé, très polyvalent et facile à assortir."
            )
        else:
            color_sentence = "Coloris non précisé, se référer aux photos pour les nuances."

        second_paragraph_lines = [
            color_sentence,
            composition_sentence,
            "Fermeture zippée + bouton gravé Levi’s.",
        ]

        third_paragraph_lines: List[str] = []
        if defects:
            third_paragraph_lines.append(f"Très bon état : {defects} (voir photos)")
        else:
            third_paragraph_lines.append("Très bon état")

        if not fields.size_label_visible and not fields.fabric_label_visible:
            third_paragraph_lines.append(
                "Étiquettes taille et composition non visibles sur les photos."
            )
        elif not fields.size_label_visible:
            third_paragraph_lines.append("Étiquette taille non visible sur les photos.")
        elif not fields.fabric_label_visible:
            third_paragraph_lines.append("Étiquette composition non visible sur les photos.")

        third_paragraph_lines.extend(
            [
                "📏 Mesures précises visibles en photo.",
                "📦 Envoi rapide et soigné",
            ]
        )

        fr_tag = (fr_display or "nc").lower()
        fourth_paragraph_lines = [
            f"✨ Retrouvez tous mes articles Levi’s à votre taille ici 👉 #durin31fr{fr_tag}",
            "💡 Pensez à faire un lot pour profiter d’une réduction supplémentaire et économiser des frais d’envoi !",
        ]

        hashtags_tokens: List[str] = []
        for token in [
            "#levis",
            "#jeanlevis",
            "#jeandenim",
            f"#levis{gender_value.lower().replace(' ', '')}" if gender_value else "",
            f"#{fit_hashtag_text}jean" if fit_hashtag_text else "",
            f"#{rise.lower().replace(' ', '')}" if rise else "",
            f"#jean{color.lower().replace(' ', '')}" if color else "",
            f"#durin31fr{fr_tag}",
        ]:
            token_clean = token.strip()
            if token_clean and token_clean not in hashtags_tokens:
                hashtags_tokens.append(token_clean)
        hashtags_paragraph_lines = [" ".join(hashtags_tokens)]

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
