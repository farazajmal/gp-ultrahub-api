from fastapi import APIRouter, HTTPException
from services.data_service import load_data

router = APIRouter()


@router.get("/clinics")
def get_clinics():
    data = load_data()

    return {
        "total": len(data["clinics"]),
        "clinics": list(data["clinics"].keys())
    }


@router.get("/clinic/{clinic_name}")
def get_clinic(clinic_name: str):
    data = load_data()

    clinics = data["clinics"]

    raise HTTPException(
    status_code=404,
    detail="Clinic not found"
    )

    return {
        "clinic": clinic_name,
        "total_doctors": len(clinics[clinic_name]),
        "doctors": clinics[clinic_name]
    }