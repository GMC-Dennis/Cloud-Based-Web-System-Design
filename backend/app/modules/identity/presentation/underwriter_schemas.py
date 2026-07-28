from pydantic import BaseModel


class BorrowerSearchOut(BaseModel):
    id: str
    full_name: str
    phone_number: str
    role: str
