from fastapi import FastAPI

from services.data_service import load_data

from routes.clinics import router as clinic_router
from routes.doctors import router as doctor_router
from routes.search import router as search_router
from routes.chat import router as chat_router


app = FastAPI(
    title="GP UltraHub API",
    version="1.0.0"
)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://gp.neomedicalcenter.pk"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


app.include_router(clinic_router)
app.include_router(doctor_router)
app.include_router(search_router)
app.include_router(chat_router)


@app.get("/")
def home():
    return {
        "status": "online",
        "project": "GP UltraHub API"
    }


@app.get("/data")
def get_data():
    return load_data()
