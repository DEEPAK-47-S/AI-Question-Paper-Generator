from pydantic import BaseModel
from typing import List, Optional

class ValidationResult(BaseModel):
    total_records: int
    valid_records: int
    invalid_records: int
    errors: List[str]

class DataIngestionResponse(BaseModel):
    status: str
    message: str
    validation: ValidationResult
