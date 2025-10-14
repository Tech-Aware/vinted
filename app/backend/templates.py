"""Listing templates and prompts for the Vinted assistant."""
from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import Dict, List


@dataclass
class ListingTemplate:
    name: str
    description: str
    prompt: str


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
                    - Modèle = Modèle du Jean si fournit {{model}}
                    - Wn Ln = valeurs d’étiquette, {{w}} et {{l}}
                    - Coupe + taille = {{fit_leg}} + {{rise_class}} (basse/moyenne/haute)
                    - Matière = {{cotton_pct}}% coton (+ {{elastane_pct}}% élasthanne si présent)
                    - Genre = {{gender}}  (valeurs attendues : femme, homme, mix)
                    - Tâches et défauts = Ce qui doit impérativement apparaître dans l'annonce si identifié sur photos ou fournit en commentaire {{defects}}
                    - SKU = {{sku}} (ex. JLF6)

                    Utilise ce format :
                    TITRE
                    Jean Levi’s {{model}} FR{{fr_size}} W{{w}} L{{l}} coupe {{rise_class}} {{fit_leg}} {{cotton_pct}}% coton {{gender}} {{color_main}} - {{sku}}
                    
                    DESCRIPTION + HASHTAG
                    Jean Levi’s modèle {{model}} pour {{gender}}.
                    Taille {{w}} US (équivalent {{fr_size}} FR), coupe {{fit_leg}} à taille {{rise_class}}, pour une silhouette ajustée et confortable.
                    Coloris {{color_main}} légèrement délavé, très polyvalent et facile à assortir.
                    Composition : {{cotton_pct}}% coton{{#if elastane_pct}}, {{elastane_pct}}% élasthanne{{/if}} pour une touche de stretch et plus de confort.
                    Fermeture zippée + bouton gravé Levi’s.
                    
                    Très bon états général {{defects}} (voir photos)
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
