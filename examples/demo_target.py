from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="SpecPulse demo target")
app.state.flaky_calls = 0


class Pet(BaseModel):
    name: str


@app.get("/pets")
def list_pets() -> list[Pet]:
    return [{"name": "Milo"}]


@app.post("/pets", status_code=status.HTTP_201_CREATED)
def create_pet(pet: Pet) -> Pet:
    return pet


@app.get("/flaky", response_model=None)
def flaky_endpoint() -> dict[str, str] | JSONResponse:
    app.state.flaky_calls += 1
    if app.state.flaky_calls % 2 == 0:
        return JSONResponse(status_code=503, content={"detail": "Temporary failure"})
    return {"status": "ok"}
