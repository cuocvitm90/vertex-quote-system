"""
Tool 2: Price Lookup & Specification Parser
Matches raw extracted items with Vertex Price Catalog using fuzzy/semantic scoring.
"""
import re
import unicodedata
from typing import List, Optional, Tuple, Dict, Any
from app.database.db import db
from app.database.models import PriceCatalogItem


def remove_accents(input_str: str) -> str:
    """Removes Vietnamese accents for robust keyword matching"""
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()


class ParsedSpec:
    def __init__(self):
        self.category: str = "Ống gió & Phụ kiện"
        self.material: str = "Tôn mạ kẽm"
        self.thickness: float = 0.75
        self.width: Optional[float] = None
        self.height: Optional[float] = None
        self.diameter: Optional[float] = None
        self.length: Optional[float] = None
        self.is_fitting: bool = False
        self.fitting_type: Optional[str] = None
        self.is_damper: bool = False
        self.is_diffuser: bool = False


class PriceLookupTool:
    """Tra cứu đơn giá vật tư từ Catalog Vertex"""

    @classmethod
    def parse_item_text(cls, text: str, spec_text: str = "", raw_thickness: Optional[float] = None) -> ParsedSpec:
        """Extracts dimensions, thickness, material and type from text"""
        combined = f"{text} {spec_text}".strip()
        clean = remove_accents(combined)
        spec = ParsedSpec()

        # 1. Detect Material
        if "inox 304" in clean or "sus 304" in clean or "inox" in clean:
            spec.material = "Inox SUS 304"
        elif "inox 201" in clean:
            spec.material = "Inox SUS 201"
        else:
            spec.material = "Tôn mạ kẽm"

        # 2. Detect Thickness
        if raw_thickness:
            spec.thickness = float(raw_thickness)
        else:
            th_match = re.search(r"(?:d|day|t|thick(?:ness)?)\s*[:=]?\s*(0\.[0-9]{1,2}|1\.[0-9]{1,2})", clean)
            if th_match:
                spec.thickness = float(th_match.group(1))
            else:
                # Direct thickness number matching
                if "0.48" in clean or "0,48" in clean:
                    spec.thickness = 0.48
                elif "0.58" in clean or "0,58" in clean:
                    spec.thickness = 0.58
                elif "0.75" in clean or "0,75" in clean:
                    spec.thickness = 0.75
                elif "0.95" in clean or "0,95" in clean:
                    spec.thickness = 0.95
                elif "1.15" in clean or "1,15" in clean:
                    spec.thickness = 1.15
                else:
                    spec.thickness = 0.75  # Standard default

        # 3. Detect Dimensions (WxH or D)
        # Square: 500x300 or 500*300 or 500 x 300 x 1200
        sq_match = re.search(r"([1-9][0-9]{1,3})\s*[xX*]\s*([1-9][0-9]{1,3})(?:\s*[xX*]\s*([1-9][0-9]{1,3}))?", combined)
        if sq_match:
            spec.width = float(sq_match.group(1))
            spec.height = float(sq_match.group(2))
            if sq_match.group(3):
                spec.length = float(sq_match.group(3)) / 1000.0  # Convert mm to m
            else:
                spec.length = 1.18  # Standard TDC section length in meters

        # Round: D250 or Phi 250 or Ø250
        rd_match = re.search(r"(?:d|phi|ø|diam(?:eter)?)\s*[:=]?\s*([1-9][0-9]{1,3})", clean)
        if rd_match:
            spec.diameter = float(rd_match.group(1))
            spec.length = 3.0  # Standard round duct length in meters

        # 4. Detect Category & Item Type (PCCC & HVAC)
        if any(k in clean for k in ["binh chua chay", "binh bot", "mfzl", "binh co2", "mt3", "mt5", "mftz"]):
            spec.category = "Bình chữa cháy"
        elif any(k in clean for k in ["dau bao khoi", "bao khoi", "smoke detector", "dau bao nhiet", "heat detector", "nut an bao chay", "chuong bao chay"]):
            spec.category = "Báo cháy"
        elif any(k in clean for k in ["den exit", "exit led", "den thoat hiem", "den su co", "emergency light"]):
            spec.category = "Đèn Exit & Sự cố"
        elif any(k in clean for k in ["sprinkler", "dau phun", "tru chua chay", "tru cuu hoa", "cuon voi", "voi chua chay"]):
            spec.category = "Chữa cháy nước"
        elif any(k in clean for k in ["van ngan chay", "van dap lua", "van cau chi", "fire damper", "van fd"]):
            spec.category = "Van ngăn cháy"
            spec.is_damper = True
        elif any(k in clean for k in ["ong gio chong chay", "ei60", "ei 60", "ei120", "ei30"]):
            spec.category = "Ống gió PCCC"
        elif any(k in clean for k in ["cut 90", "co 90", "elbow 90"]):
            spec.category = "Phụ kiện ống gió vuông"
            spec.is_fitting = True
            spec.fitting_type = "cut_90"
        elif any(k in clean for k in ["cut 45", "co 45", "elbow 45"]):
            spec.category = "Phụ kiện ống gió vuông"
            spec.is_fitting = True
            spec.fitting_type = "cut_45"
        elif any(k in clean for k in ["con thu", "con giam", "reducer"]):
            spec.category = "Phụ kiện ống gió vuông"
            spec.is_fitting = True
            spec.fitting_type = "con_thu"
        elif any(k in clean for k in ["te vuong", "chac 3", "tee"]):
            spec.category = "Phụ kiện ống gió vuông"
            spec.is_fitting = True
            spec.fitting_type = "te"
        elif any(k in clean for k in ["chan re", "take off", "collar"]):
            spec.category = "Phụ kiện ống gió vuông"
            spec.is_fitting = True
            spec.fitting_type = "chan_re"
        elif any(k in clean for k in ["van vcd", "vcd", "van tay gat", "van luu luong"]):
            spec.category = "Van gió"
            spec.is_damper = True
        elif any(k in clean for k in ["van mot chieu", "nrd", "non return"]):
            spec.category = "Van gió"
            spec.is_damper = True
        elif any(k in clean for k in ["van dien", "van dong co", "md", "motorized"]):
            spec.category = "Van gió"
            spec.is_damper = True
        elif any(k in clean for k in ["diffuser 600", "mieng gio 600", "cua gio khuech tan 600", "khuech tan 600"]):
            spec.category = "Cửa gió / Miệng gió"
            spec.is_diffuser = True
        elif any(k in clean for k in ["diffuser 300", "mieng gio 300", "khuech tan 300"]):
            spec.category = "Cửa gió / Miệng gió"
            spec.is_diffuser = True
        elif any(k in clean for k in ["louver", "nan z", "cua ngoai troi"]):
            spec.category = "Cửa gió / Miệng gió"
            spec.is_diffuser = True
        elif any(k in clean for k in ["slot", "linear slot"]):
            spec.category = "Cửa gió / Miệng gió"
            spec.is_diffuser = True
        elif any(k in clean for k in ["hop gio", "plenum"]):
            spec.category = "Hộp gió"
        elif any(k in clean for k in ["ty ren", "ty treo"]):
            spec.category = "Vật tư phụ"
        elif any(k in clean for k in ["bang dinh bac", "bang keo bac"]):
            spec.category = "Vật tư phụ"
        elif any(k in clean for k in ["keo a500", "silicon"]):
            spec.category = "Vật tư phụ"
        elif spec.diameter or "ong gio tron" in clean or "ogt" in clean:
            spec.category = "Ống gió tròn xoắn"
        else:
            if "inox" in clean:
                spec.category = "Ống gió Inox"
            else:
                spec.category = "Ống gió vuông"


        return spec

    @classmethod
    def lookup_price(
        cls,
        raw_name: str,
        raw_spec: str = "",
        raw_unit: str = "m2",
        raw_thickness: Optional[float] = None
    ) -> Dict[str, Any]:
        """Looks up or calculates standard unit price from Vertex Catalog"""
        parsed = cls.parse_item_text(raw_name, raw_spec, raw_thickness)
        catalog = db.get_catalog()

        clean_query = remove_accents(f"{raw_name} {raw_spec}")

        # 1. Match score calculation against catalog items
        best_item: Optional[PriceCatalogItem] = None
        best_score = 0.0

        for item in catalog:
            score = 0.0
            clean_item_name = remove_accents(item.name)
            clean_category = remove_accents(item.category)

            # Match category
            if clean_category in clean_query or remove_accents(parsed.category) == clean_category:
                score += 25.0

            # Match keywords (Highest weight for exact specific model/type keyword)
            for kw in item.keywords:
                clean_kw = remove_accents(kw)
                if clean_kw in clean_query:
                    score += 35.0

            # Match thickness
            if parsed.thickness > 0 and abs(item.thickness - parsed.thickness) < 0.05:
                score += 20.0

            # Match material
            if remove_accents(item.material) in clean_query:
                score += 15.0
            elif item.material == parsed.material:
                score += 10.0

            if score > best_score:
                best_score = score
                best_item = item

        # 2. Decision Logic
        if best_item and best_score >= 30.0:
            confidence = min(0.99, best_score / 100.0)
            return {
                "item_code": best_item.code,
                "standard_name": best_item.name,
                "category": best_item.category,
                "material": best_item.material,
                "thickness": best_item.thickness,
                "unit": best_item.unit,
                "unit_price": best_item.unit_price,
                "confidence_score": confidence,
                "parsed_spec": parsed,
                "notes": best_item.notes
            }


        # 3. Fallback standard price calculation based on category & thickness
        fallback_unit_price = 195000.0  # default 0.75mm standard
        item_code = f"GEN-{parsed.category[:3].upper()}"
        standard_name = raw_name

        if parsed.category == "Ống gió vuông":
            if parsed.thickness <= 0.48:
                fallback_unit_price = 145000.0
            elif parsed.thickness <= 0.58:
                fallback_unit_price = 165000.0
            elif parsed.thickness <= 0.75:
                fallback_unit_price = 195000.0
            elif parsed.thickness <= 0.95:
                fallback_unit_price = 245000.0
            else:
                fallback_unit_price = 295000.0
            item_code = f"OGV-TMK-{int(parsed.thickness*100):03d}"
            standard_name = f"Ống gió vuông tôn mạ kẽm dày {parsed.thickness}mm bích TDC"
            unit = "m2"

        elif parsed.category == "Ống gió Inox":
            fallback_unit_price = 460000.0
            item_code = "OGV-IN304-080"
            standard_name = f"Ống gió vuông Inox 304 dày {parsed.thickness}mm"
            unit = "m2"

        elif parsed.category == "Ống gió tròn xoắn":
            fallback_unit_price = 155000.0
            item_code = f"OGT-TMK-D{int(parsed.diameter) if parsed.diameter else 250}"
            standard_name = f"Ống gió tròn xoắn mạ kẽm D{int(parsed.diameter) if parsed.diameter else 250}"
            unit = "m"

        elif parsed.category == "Phụ kiện ống gió vuông":
            fallback_unit_price = 235000.0
            item_code = "PK-FITTING-V"
            standard_name = f"Phụ kiện ống gió vuông dày {parsed.thickness}mm"
            unit = "m2"

        elif parsed.category == "Van gió":
            fallback_unit_price = 350000.0
            item_code = "VAN-STANDARD"
            standard_name = f"Van gió Vertex tiêu chuẩn"
            unit = "cái"

        else:
            fallback_unit_price = 200000.0
            unit = raw_unit or "m2"

        return {
            "item_code": item_code,
            "standard_name": standard_name,
            "category": parsed.category,
            "material": parsed.material,
            "thickness": parsed.thickness,
            "unit": unit,
            "unit_price": fallback_unit_price,
            "confidence_score": 0.80,
            "parsed_spec": parsed,
            "notes": "Đơn giá theo bảng giá định mức chuẩn Vertex"
        }
