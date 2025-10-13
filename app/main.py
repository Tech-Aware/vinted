"""Application entry point for the Vinted listing assistant."""
from __future__ import annotations

from app.logger import get_logger
from app.ui.listing_app import VintedListingApp


logger = get_logger(__name__)


def main() -> None:
    """Start the Tkinter event loop."""

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
