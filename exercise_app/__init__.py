from flask import Blueprint

exercise_bp = Blueprint(
    "exercise",
    __name__,
    template_folder="../templates/exercise",
    static_folder="../static",
)

from . import routes  # noqa



