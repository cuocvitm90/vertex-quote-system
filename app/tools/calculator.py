"""
Tool 3: Pricing, Duct Area & Financial Calculator
Calculates duct surface area (m2), fittings, subtotal, discount, VAT,
applies Master Template coefficients (% waste, transport, labor, margin) strictly via pure Python arithmetic,
and generates Vietnamese number-to-words.
"""
import math
from typing import List, Tuple, Dict, Any, Optional
from app.database.models import QuoteItem, Quote, MasterTemplate
from app.config import settings


def number_to_vietnamese_words(n: float) -> str:
    """Converts a monetary number into Vietnamese words for quotations"""
    num = int(round(n))
    if num == 0:
        return "Không đồng"

    digits = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
    units = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]

    def read_three_digits(c, b, a, is_highest_group):
        res = []
        if not is_highest_group or c > 0:
            res.append(digits[c] + " trăm")
        
        if b == 0:
            if not (not is_highest_group or c > 0) and a == 0:
                pass
            elif a > 0:
                if not is_highest_group or c > 0:
                    res.append("lẻ")
        elif b == 1:
            res.append("mười")
        else:
            res.append(digits[b] + " mươi")

        if b > 0 and a == 1:
            if b == 1:
                res.append("một")
            else:
                res.append("mốt")
        elif b > 0 and a == 5:
            res.append("lăm")
        elif a > 0:
            res.append(digits[a])

        return " ".join(res)

    groups = []
    temp = num
    while temp > 0:
        groups.append(temp % 1000)
        temp //= 1000

    words = []
    num_groups = len(groups)
    for i in range(num_groups - 1, -1, -1):
        g = groups[i]
        if g > 0:
            c = g // 100
            b = (g % 100) // 10
            a = g % 10
            is_highest = (i == num_groups - 1)
            group_words = read_three_digits(c, b, a, is_highest)
            if group_words:
                words.append(group_words + " " + units[i])

    result = " ".join(words).strip()
    # Normalize multiple spaces
    result = " ".join(result.split())
    # Capitalize first letter and append "đồng chẵn."
    result = result[0].upper() + result[1:] + " đồng chẵn."
    return result


from app.tools.labor_cost import LaborCostMatrix


class QuoteCalculator:
    """Calculates duct areas and quote financials using 100% pure Python math and Output Pricing Formula"""

    @classmethod
    def apply_commercial_pricing_formula(
        cls,
        material_unit_cost: float,
        labor_unit_cost: float,
        template: Optional[MasterTemplate] = None
    ) -> Tuple[float, float, Dict[str, float]]:
        """
        Output Pricing Formula (Cơ chế tính giá đầu ra):
        1. Giá gốc đầu vào (Base Unit Cost) = Giá vật tư thiết bị + Chi phí nhân công khoán theo định mức.
        2. Đơn giá chào bán (Final Unit Price) = Giá gốc đầu vào * Hệ số thương mại / chào bán (1 + waste + transport + margin).
        Returns: (final_unit_price, base_unit_cost, breakdown_dict)
        """
        waste = template.waste_ratio if template else 0.05
        transport = template.transport_ratio if template else 0.03
        margin = template.margin_ratio if template else 0.12

        base_unit_cost = round(float(material_unit_cost) + float(labor_unit_cost), 0)
        commercial_multiplier = 1.0 + waste + transport + margin
        final_unit_price = round(base_unit_cost * commercial_multiplier, 0)

        breakdown = {
            "material_unit_cost": round(float(material_unit_cost), 0),
            "labor_unit_cost": round(float(labor_unit_cost), 0),
            "base_unit_cost": base_unit_cost,
            "waste_ratio": waste,
            "transport_ratio": transport,
            "margin_ratio": margin,
            "total_markup_percent": round((commercial_multiplier - 1.0) * 100, 1),
            "multiplier": round(commercial_multiplier, 4),
            "final_unit_price": final_unit_price
        }

        return final_unit_price, base_unit_cost, breakdown

    @classmethod
    def apply_template_coefficients(
        cls,
        raw_price: float,
        template: Optional[MasterTemplate] = None
    ) -> Tuple[float, Dict[str, float]]:
        """
        Applies Master Template pricing coefficients to raw market base price:
        Multiplier = 1 + waste_ratio + transport_ratio + labor_ratio + margin_ratio
        Final Unit Price = round(raw_price * Multiplier, 0)
        """
        waste = template.waste_ratio if template else 0.05
        transport = template.transport_ratio if template else 0.03
        labor = template.labor_ratio if template else 0.15
        margin = template.margin_ratio if template else 0.12

        multiplier = 1.0 + waste + transport + labor + margin
        final_price = round(float(raw_price) * multiplier, 0)

        breakdown = {
            "raw_base_price": round(float(raw_price), 0),
            "waste_ratio": waste,
            "transport_ratio": transport,
            "labor_ratio": labor,
            "margin_ratio": margin,
            "total_markup_percent": round((multiplier - 1.0) * 100, 1),
            "multiplier": round(multiplier, 4),
            "final_unit_price": final_price
        }

        return final_price, breakdown

    @classmethod
    def calculate_duct_area_m2(
        cls,
        width: Optional[float],
        height: Optional[float],
        diameter: Optional[float],
        length_m: Optional[float] = 1.18,
        quantity: float = 1.0,
        category: str = "Ống gió vuông"
    ) -> float:
        """
        Calculates sheet metal area in m2:
        - Square duct: 2 * (W + H) * L / 1000 (W, H in mm, L in m)
        - Round duct: pi * D * L / 1000 (D in mm, L in m)
        """
        length = length_m if length_m and length_m > 0 else 1.18

        if width and height and width > 0 and height > 0:
            # 2 * (W_m + H_m) * L_m
            single_area = 2.0 * ((width + height) / 1000.0) * length
            return round(single_area * quantity, 2)

        elif diameter and diameter > 0:
            # pi * D_m * L_m
            single_area = math.pi * (diameter / 1000.0) * length
            return round(single_area * quantity, 2)

        # Fallback to given quantity if area cannot be calculated geometrically
        return round(quantity, 2)

    @classmethod
    def process_item_pricing(
        cls,
        stt: int,
        raw_name: str,
        raw_spec: str,
        unit: str,
        quantity: float,
        price_info: Dict[str, Any],
        price_source: str = "CATALOG",
        raw_market_price: float = 0.0,
        applied_coefficients: Optional[Dict[str, float]] = None,
        brand: str = "Vertex Standard",
        brand_source: str = "VERTEX_STANDARD",
        template: Optional[MasterTemplate] = None
    ) -> QuoteItem:
        """
        Builds a finalized QuoteItem with calculated unit price, labor cost matrix rate, area, total, and price source tracking
        """
        parsed_spec = price_info.get("parsed_spec")
        standard_unit = price_info.get("unit", unit)
        category = price_info.get("category", "Thiết bị PCCC & Cơ điện")

        width = parsed_spec.width if parsed_spec else None
        height = parsed_spec.height if parsed_spec else None
        diameter = parsed_spec.diameter if parsed_spec else None
        length = parsed_spec.length if parsed_spec else None
        thickness = parsed_spec.thickness if parsed_spec else 0.75
        material = parsed_spec.material if parsed_spec else "Tiêu chuẩn PCCC"

        # Determine calculation unit & area
        area_m2 = 0.0
        if standard_unit == "m2" or unit.lower() in ["m2", "m²", "mét vuông"]:
            if width and height:
                area_m2 = cls.calculate_duct_area_m2(width, height, None, length, quantity, category)
            else:
                area_m2 = float(quantity)
        elif standard_unit in ["m", "mét"]:
            area_m2 = float(quantity)
        else:
            area_m2 = float(quantity)

        # 1. Determine Labor Cost from LaborCostMatrix
        labor_unit_cost, labor_desc = LaborCostMatrix.get_labor_rate_and_description(
            item_name=raw_name,
            spec=raw_spec,
            category=category,
            unit=standard_unit
        )

        # 2. Material Cost
        material_unit_cost = float(price_info.get("material_unit_cost", 0.0))
        if material_unit_cost <= 0:
            material_unit_cost = float(price_info.get("unit_price", raw_market_price))

        # 3. Apply Output Pricing Formula if labor rate is active
        if labor_unit_cost > 0:
            final_unit_price, base_unit_cost, breakdown = cls.apply_commercial_pricing_formula(
                material_unit_cost=material_unit_cost,
                labor_unit_cost=labor_unit_cost,
                template=template
            )
            if applied_coefficients is None:
                applied_coefficients = breakdown
        else:
            base_unit_cost = material_unit_cost
            final_unit_price = float(price_info.get("unit_price", 0.0))
            if final_unit_price <= 0:
                final_unit_price = material_unit_cost

        # 4. Calculate line total
        if standard_unit == "m2" or unit.lower() in ["m2", "m²", "mét vuông"]:
            total_price = area_m2 * final_unit_price
        else:
            total_price = quantity * final_unit_price

        # Build clean specification string
        spec_parts = []
        if width and height:
            spec_parts.append(f"{int(width)}x{int(height)}mm")
        elif diameter:
            spec_parts.append(f"D{int(diameter)}mm")
        if thickness:
            spec_parts.append(f"d={thickness}mm")
        if material:
            spec_parts.append(material)
        if raw_spec:
            spec_parts.append(raw_spec)

        spec_str = ", ".join(list(dict.fromkeys(spec_parts)))

        return QuoteItem(
            stt=stt,
            category=category,
            item_code=price_info.get("item_code", f"VTX-{stt:03d}"),
            item_name=price_info.get("standard_name", raw_name),
            brand=brand,
            brand_source=brand_source,
            spec=spec_str,
            unit=standard_unit,
            width=width,
            height=height,
            diameter=diameter,
            length=length,
            thickness=thickness,
            material=material,
            quantity=round(quantity, 2),
            area_m2=round(area_m2, 2),
            material_unit_cost=round(material_unit_cost, 0),
            labor_unit_cost=round(labor_unit_cost, 0),
            base_unit_cost=round(base_unit_cost, 0),
            labor_description=labor_desc,
            unit_price=round(final_unit_price, 0),
            total_price=round(total_price, 0),
            price_source=price_source,
            raw_market_price=round(raw_market_price, 0),
            applied_coefficients=applied_coefficients,
            confidence_score=round(price_info.get("confidence_score", 1.0), 2),
            notes=price_info.get("notes", "")
        )

    @classmethod
    def calculate_quote_totals(
        cls,
        items: List[QuoteItem],
        discount_rate: Optional[float] = None,
        vat_rate: Optional[float] = None
    ) -> Dict[str, Any]:
        """Calculates subtotal, material total, labor total, discount, VAT, total amount, and words representation"""
        disc_rate = discount_rate if discount_rate is not None else settings.DEFAULT_DISCOUNT_RATE
        v_rate = vat_rate if vat_rate is not None else settings.DEFAULT_VAT_RATE

        subtotal = sum(item.total_price for item in items)
        
        # Calculate separate material and labor cost totals
        total_material_cost = sum(
            item.material_unit_cost * (item.area_m2 if item.unit in ["m2", "m²", "mét vuông"] else item.quantity)
            for item in items
        )
        total_labor_cost = sum(
            item.labor_unit_cost * (item.area_m2 if item.unit in ["m2", "m²", "mét vuông"] else item.quantity)
            for item in items
        )

        discount_amount = round(subtotal * disc_rate, 0)
        subtotal_after_discount = subtotal - discount_amount
        vat_amount = round(subtotal_after_discount * v_rate, 0)
        total_amount = subtotal_after_discount + vat_amount
        words = number_to_vietnamese_words(total_amount)

        return {
            "subtotal": subtotal,
            "total_material_cost": round(total_material_cost, 0),
            "total_labor_cost": round(total_labor_cost, 0),
            "discount_rate": disc_rate,
            "discount_amount": discount_amount,
            "subtotal_after_discount": subtotal_after_discount,
            "vat_rate": v_rate,
            "vat_amount": vat_amount,
            "total_amount": total_amount,
            "total_amount_in_words": words
        }

