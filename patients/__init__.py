from flask import Blueprint, current_app
from datetime import datetime

patients_bp = Blueprint(
    "patients", 
    __name__, 
    template_folder="templates/patients",  # corrected
    url_prefix="/patients"
)

# Inject clinic and current year into all blueprint templates
@patients_bp.app_context_processor
def inject_clinic():
    return {
        "clinic": current_app.config.get("CLINIC"),
        "current_year": datetime.now().year
    }

from . import routes
