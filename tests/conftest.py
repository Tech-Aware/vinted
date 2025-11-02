from __future__ import annotations

import pytest


@pytest.fixture
def simulated_levis_encoded_images() -> list[str]:
    return [
        "data:image/jpeg;base64,LEVIS_LOGO_DENIM",
        "data:image/jpeg;base64,denim_texture_rivets",
    ]


@pytest.fixture
def simulated_tommy_encoded_images() -> list[str]:
    return [
        "data:image/jpeg;base64,tommy_flag_logo",
        "data:image/jpeg;base64,knit_pattern_mariniere",
    ]


@pytest.fixture
def simulated_uncertain_images() -> list[str]:
    return ["data:image/jpeg;base64,generic_fabric"]

