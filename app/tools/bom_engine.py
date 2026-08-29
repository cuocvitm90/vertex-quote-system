"""
Manufacturing Costing, BOM & Multi-Tier Pricing Engine
Vertex Construction & PCCC Quoting System
Calculates real factory cost bases from raw materials, scrap waste, labor, and overhead,
and determines tier-based commercial pricing and gross margins.
"""
from typing import Dict, List, Any, Optional, Tuple
from app.database.models import CustomerTier, WarehouseType, BOMComponent, BOMBreakdown


# Density constants (kg/m3 and kg/m2/mm)
DENSITY_STEEL = 7850.0       # kg/m3 (approx 7.85 kg / m2 per mm thickness)
DENSITY_ALUMINUM = 2700.0    # kg/m3 (approx 2.70 kg / m2 per mm thickness)
DENSITY_STAINLESS = 7930.0   # kg/m3 (approx 7.93 kg / m2 per mm thickness)


def calculate_bom_cost(
    raw_materials: List[Dict[str, Any]],
    scrap_waste_ratio: float = 0.05,
    labor_cost: float = 0.0,
    overhead_cost: float = 0.0,
    margin_retail: float = 0.30,
    margin_dealer: float = 0.15
) -> Dict[str, Any]:
    """
    Aggregates bill of materials components to compute real factory cost:
    Real Cost Price = Raw Material Cost * (1 + Scrap Waste %) + Labor Cost + Overhead Cost
    """
    components: List[Dict[str, Any]] = []
    raw_material_cost = 0.0

    for rm in raw_materials:
        qty = float(rm.get("quantity", 0.0))
        unit_cost = float(rm.get("unit_cost", 0.0))
        total_cost = round(qty * unit_cost, 2)
        raw_material_cost += total_cost
        components.append({
            "material_name": rm.get("material_name", ""),
            "spec": rm.get("spec", ""),
            "unit": rm.get("unit", "kg"),
            "quantity": qty,
            "unit_cost": unit_cost,
            "total_cost": total_cost
        })

    raw_material_cost = round(raw_material_cost, 2)
    scrap_waste_cost = round(raw_material_cost * scrap_waste_ratio, 2)
    labor_cost = round(float(labor_cost), 2)
    overhead_cost = round(float(overhead_cost), 2)

    calculated_cost_price = round(raw_material_cost + scrap_waste_cost + labor_cost + overhead_cost, 2)

    # Calculate recommended retail & dealer price based on margin targets
    suggested_retail_price = round(calculated_cost_price / (1.0 - margin_retail), -3) if margin_retail < 1.0 else calculated_cost_price * 1.4
    suggested_dealer_price = round(calculated_cost_price / (1.0 - margin_dealer), -3) if margin_dealer < 1.0 else calculated_cost_price * 1.2

    return {
        "raw_materials": components,
        "raw_material_cost": raw_material_cost,
        "scrap_waste_ratio": scrap_waste_ratio,
        "scrap_waste_cost": scrap_waste_cost,
        "labor_cost": labor_cost,
        "overhead_cost": overhead_cost,
        "calculated_cost_price": calculated_cost_price,
        "suggested_retail_price": suggested_retail_price,
        "suggested_dealer_price": suggested_dealer_price,
        "margin_retail": margin_retail,
        "margin_dealer": margin_dealer
    }


def calculate_manufacturing_dimensions(
    category: str,
    material_type: Optional[str],
    length_mm: float,
    width_mm: float,
    height_mm: Optional[float] = None,
    thickness_mm: Optional[float] = None,
    base_cost_price: float = 0.0,
    base_retail_price: float = 0.0,
    base_dealer_price: float = 0.0,
    project_discount_rate: float = 0.0,
    quantity: float = 1.0
) -> Dict[str, Any]:
    """
    Dynamically computes surface area (m2) and estimated weight (kg) for custom manufacturing items:
    - Rectangular Ducts: Area = 2 * (W + H) * L / 1,000,000
    - Flat Plate / EV Skid Plates: Area = (W * L) / 1,000,000
    - Enclosures / Boxes: Area = 2 * (L*W + L*H + W*H) / 1,000,000
    """
    length_mm = max(1.0, float(length_mm or 1000.0))
    width_mm = max(1.0, float(width_mm or 1000.0))
    h_mm = float(height_mm or 0.0)
    thk_mm = float(thickness_mm or 1.0)
    qty = max(0.01, float(quantity or 1.0))

    cat_lower = category.lower()

    if "ống gió" in cat_lower or "duct" in cat_lower:
        # Duct surface area = Perimeter * Length = 2 * (W + H) * L (if rectangular) or W * L (if flat sheet)
        if h_mm > 0:
            area_per_unit_m2 = round((2.0 * (width_mm + h_mm) * length_mm) / 1_000_000.0, 4)
        else:
            area_per_unit_m2 = round((width_mm * length_mm) / 1_000_000.0, 4)
    elif "tủ" in cat_lower or "enclosure" in cat_lower or "hộp" in cat_lower:
        if h_mm > 0:
            area_per_unit_m2 = round((2.0 * (length_mm * width_mm + length_mm * h_mm + width_mm * h_mm)) / 1_000_000.0, 4)
        else:
            area_per_unit_m2 = round((width_mm * length_mm) / 1_000_000.0, 4)
    else:
        # Flat plate / VinFast EV protection plate
        area_per_unit_m2 = round((width_mm * length_mm) / 1_000_000.0, 4)

    total_area_m2 = round(area_per_unit_m2 * qty, 4)

    # Estimate weight
    mat_type = (material_type or "THÉP_MẠ_KẼM").upper()
    if "NHÔM" in mat_type or "AL" in mat_type:
        density_factor = 2.70  # kg/m2 per mm
    elif "INOX" in mat_type:
        density_factor = 7.93
    else:
        density_factor = 7.85  # Standard galvanized steel

    weight_per_unit_kg = round(area_per_unit_m2 * thk_mm * density_factor, 2)
    total_weight_kg = round(weight_per_unit_kg * qty, 2)

    # Calculate item unit pricing based on area multiplier if base prices are per m2
    # If base price was configured per m2 (standard for ducts):
    if "ống gió" in cat_lower or base_cost_price < 1_000_000:
        cost_unit = round(base_cost_price * area_per_unit_m2, 0)
        retail_unit = round(base_retail_price * area_per_unit_m2, 0)
        dealer_unit = round(base_dealer_price * area_per_unit_m2, 0)
    else:
        # Fixed piece base price
        cost_unit = base_cost_price
        retail_unit = base_retail_price
        dealer_unit = base_dealer_price

    return {
        "area_per_unit_m2": area_per_unit_m2,
        "total_area_m2": total_area_m2,
        "weight_per_unit_kg": weight_per_unit_kg,
        "total_weight_kg": total_weight_kg,
        "unit_cost_price": cost_unit,
        "unit_retail_price": retail_unit,
        "unit_dealer_price": dealer_unit,
        "project_discount_rate": project_discount_rate
    }


def resolve_tier_price(
    cost_price: float,
    retail_price: float,
    dealer_price: float,
    project_discount_rate: float,
    customer_tier: CustomerTier = CustomerTier.RETAIL,
    total_quote_value: float = 0.0
) -> Tuple[float, float, float]:
    """
    Resolves active unit price according to customer tier:
    - RETAIL -> Retail price
    - DEALER -> Dealer price
    - PROJECT -> Retail price discounted by project discount rate (with scaling for large packages)
    Returns: (unit_price, cost_price, discount_applied_pct)
    """
    if customer_tier == CustomerTier.DEALER:
        unit_price = dealer_price if dealer_price > 0 else retail_price * 0.85
        discount_pct = round(((retail_price - unit_price) / retail_price * 100.0), 1) if retail_price > 0 else 15.0
    elif customer_tier == CustomerTier.PROJECT:
        # Project tier discount
        base_disc = project_discount_rate if project_discount_rate > 0 else 8.0
        # Additional scaling discount for large contracts (>500M or >1B VND)
        if total_quote_value >= 1_000_000_000:
            base_disc += 4.0
        elif total_quote_value >= 500_000_000:
            base_disc += 2.0
        base_disc = min(base_disc, 25.0)  # Max safety project discount limit

        unit_price = round(retail_price * (1.0 - base_disc / 100.0), 0)
        discount_pct = base_disc
    else:
        # Default RETAIL
        unit_price = retail_price
        discount_pct = 0.0

    return (float(unit_price), float(cost_price), float(discount_pct))


def calculate_gross_margin(selling_price: float, cost_price: float) -> Dict[str, Any]:
    """
    Computes financial gross margin and safety classification
    """
    margin_amount = round(selling_price - cost_price, 2)
    margin_percent = round((margin_amount / selling_price * 100.0), 2) if selling_price > 0 else 0.0

    if margin_percent >= 25.0:
        status = "HEALTHY"
        label = "Biên lợi nhuận rất tốt (≥25%)"
        color = "#10B981"  # Green
    elif margin_percent >= 15.0:
        status = "ACCEPTABLE"
        label = "Biên lợi nhuận đạt chuẩn (15-24%)"
        color = "#3B82F6"  # Blue
    elif margin_percent >= 8.0:
        status = "WARNING_LOW"
        label = "Biên lợi nhuận mỏng (8-14%)"
        color = "#F59E0B"  # Orange/Yellow
    else:
        status = "CRITICAL_LOW"
        label = "Cảnh báo biên độ thấp / Cận giá vốn (<8%)"
        color = "#EF4444"  # Red

    return {
        "margin_amount": margin_amount,
        "margin_percent": margin_percent,
        "status": status,
        "label": label,
        "color": color
    }
