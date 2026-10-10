from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.schemas.ingestion import DataIngestionResponse, ValidationResult
import csv
import io

router = APIRouter()

@router.post("/population", response_model=DataIngestionResponse)
async def ingest_population_data(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    
    content = await file.read()
    text = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(text))
    
    total = 0
    valid = 0
    invalid = 0
    errors = []
    
    for row in reader:
        total += 1
        if "resident_count" not in row or not row["resident_count"].isdigit():
            invalid += 1
            errors.append(f"Row {total}: Invalid or missing resident_count")
            continue
            
        valid += 1
        # In a real app, we would resolve area_id by area name and insert into db
        # e.g., result = await db.execute(select(Area).where(Area.name == row['area_name']))
        
    return DataIngestionResponse(
        status="Success",
        message="File processed",
        validation=ValidationResult(
            total_records=total,
            valid_records=valid,
            invalid_records=invalid,
            errors=errors[:10] # Return top 10 errors
        )
    )
