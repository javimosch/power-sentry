#!/usr/bin/env python3
from datetime import datetime
from typing import Optional

# French electricity pricing (EDF Tarif Bleu)
# Heures pleines (peak hours): 22h-6h (10pm-6am)
# Heures creuses (off-peak hours): 6h-22h (6am-10pm)
# Prices as of 2024 (approximate)

class FrenchPricing:
    peak_price: float = 0.2795  # € per kWh during peak hours
    off_peak_price: float = 0.2068  # € per kWh during off-peak hours
    peak_hours_start: int = 22  # 22h
    peak_hours_end: int = 6  # 6h

def get_current_price(timestamp: Optional[float] = None) -> float:
    """Get current electricity price based on time."""
    date = datetime.fromtimestamp(timestamp if timestamp else datetime.now().timestamp())
    hour = date.hour
    
    # Peak hours: 22h-6h (wraps around midnight)
    is_peak = hour >= 22 or hour < 6
    
    return FrenchPricing.peak_price if is_peak else FrenchPricing.off_peak_price

def get_price_period(timestamp: Optional[float] = None) -> str:
    """Get current price period ('peak' or 'off-peak')."""
    date = datetime.fromtimestamp(timestamp if timestamp else datetime.now().timestamp())
    hour = date.hour
    
    return 'peak' if (hour >= 22 or hour < 6) else 'off-peak'

def format_price(cents: float) -> str:
    """Format price in euros."""
    return f'€{cents:.4f}'
