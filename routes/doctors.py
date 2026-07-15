from fastapi import APIRouter, HTTPException, Query

from services.data_service import load_data
from services.doctor_service import (
    find_earliest,
    find_available_today,
    recommend_doctor,
)

router = APIRouter()


@router.get("/recommend")
def recommend(
    clinic: str | None = Query(None),
    day: str | None = Query(None),
    provider_type: str | None = Query(None),
):

    doctor = recommend_doctor(
        clinic=clinic,
        day=day,
        provider_type=provider_type,
    )

    if doctor is None:
        raise HTTPException(
            status_code=404,
            detail="No matching appointments found."
        )

    return doctor


@router.get("/doctor/{doctor_name}")
def get_doctor(doctor_name: str):

    data = load_data()

    for doctors in data["clinics"].values():

        for doctor in doctors:

            if doctor["doctor"].lower() == doctor_name.lower():
                return doctor

    raise HTTPException(
        status_code=404,
        detail="Doctor not found"
    )


@router.get("/earliest")
def get_earliest():
    return find_earliest()


@router.get("/available-today")
def available_today():

    doctors = find_available_today()

    return {
        "total": len(doctors),
        "doctors": doctors
    }