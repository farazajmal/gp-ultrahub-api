from fastapi import APIRouter, Query
from services.doctor_service import search_doctors

router = APIRouter()


@router.get("/search")
def search(
    doctor: str | None = Query(None),
    clinic: str | None = Query(None),
    day: str | None = Query(None),
    provider_type: str | None = Query(None),
):
    results = search_doctors(
        doctor=doctor,
        clinic=clinic,
        day=day,
        provider_type=provider_type,
    )

    return {
        "total": len(results),
        "results": results,
    }