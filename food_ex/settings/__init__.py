"""Default Django settings for Food_Ex.

This package keeps the project settings organized by environment while still allowing
legacy imports such as ``food_ex.settings`` to work by defaulting to the development
configuration.
"""

from .dev import *  # noqa: F401,F403
