from datetime import datetime, timedelta
import random

try:
    from sklearn.ensemble import RandomForestRegressor
    import pandas as pd
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class ForecastEngine:
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100) if SKLEARN_AVAILABLE else None
        
    def generate_features(self, timestamp: datetime, base_demand: int, has_event: bool = False):
        # Time-based features
        hour = timestamp.hour
        is_weekend = 1 if timestamp.weekday() >= 5 else 0
        
        # Simple engineered features
        peak_morning = 1 if 7 <= hour <= 9 else 0
        peak_evening = 1 if 17 <= hour <= 19 else 0
        
        return {
            "hour": hour,
            "is_weekend": is_weekend,
            "peak_morning": peak_morning,
            "peak_evening": peak_evening,
            "has_event": 1 if has_event else 0,
            "base_demand": base_demand
        }
        
    def predict_demand(self, base_demand: int, timestamp: datetime, has_event: bool = False) -> int:
        features = self.generate_features(timestamp, base_demand, has_event)
        
        if SKLEARN_AVAILABLE:
            # In a real scenario, this would use a pre-trained model on historical data.
            # Here we simulate prediction logic by returning a mathematically modified value.
            # (To truly run predict(), the model needs to be fitted).
            multiplier = 1.0
            if features["peak_morning"] or features["peak_evening"]:
                multiplier += 0.5
            if features["is_weekend"]:
                multiplier -= 0.2
            if features["has_event"]:
                multiplier += 0.8
                
            return int(base_demand * multiplier)
        else:
            # Fallback if scikit-learn is not installed (e.g. network timeout during setup)
            multiplier = 1.0
            if features["peak_morning"] or features["peak_evening"]:
                multiplier += 0.5
            if features["is_weekend"]:
                multiplier -= 0.2
            if features["has_event"]:
                multiplier += 0.8
                
            return int(base_demand * multiplier)

forecast_engine = ForecastEngine()
