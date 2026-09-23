from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI(title="SpecPulse demo target")


class Pet(BaseModel):
    name: str


@app.get("/pets")
def list_pets() -> list[Pet]:
    return [{"name": "Milo"}]


@app.post("/pets", status_code=status.HTTP_201_CREATED)
def create_pet(pet: Pet) -> Pet:
    return pet
