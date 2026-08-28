"""
Input Scenario Router & Brand/Technical Specification Engine for Vertex Quote System
Handles 3 Flexible Business Input Scenarios:
- SCENARIO_1_CAD_TAKEOFF: Automated drawing takeoff from .dwg / .dxf / architectural drawings.
- SCENARIO_2_SPECIFIED_BRAND: Client BOQ with explicit brand requirements (Ebara, Viking, Hochiki, etc.) & pump/technical parameters (Q, H, P, K).
- SCENARIO_3_STANDARD_CATALOG: Pure/generic BOQ without brand specifications -> resolves optimal Vertex Standard Catalog brands.
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path


class InputScenarioRouter:
    """
    Classifies BOQ input into 3 flexible scenarios and extracts technical specifications / brand designations.
    """
    SCENARIO_1 = "SCENARIO_1_CAD_TAKEOFF"
    SCENARIO_2 = "SCENARIO_2_SPECIFIED_BRAND"
    SCENARIO_3 = "SCENARIO_3_STANDARD_CATALOG"

    # Known Engineering & Equipment Brands Whitelist
    KNOWN_BRANDS = [
        # Pumps & Motors
        {"brand": "Ebara", "aliases": ["ebara", "e-bara"], "category": "Máy bơm"},
        {"brand": "Grundfos", "aliases": ["grundfos", "grund-fos"], "category": "Máy bơm"},
        {"brand": "Pentax", "aliases": ["pentax"], "category": "Máy bơm"},
        {"brand": "CNP", "aliases": ["cnp"], "category": "Máy bơm"},
        {"brand": "Hyundai", "aliases": ["hyundai"], "category": "Động cơ diesel"},
        {"brand": "Tohatsu", "aliases": ["tohatsu"], "category": "Bơm khiêng tay"},
        
        # Fire Sprinklers & Valves
        {"brand": "Viking", "aliases": ["viking", "vi-king"], "category": "Sprinkler & Van"},
        {"brand": "Tyco", "aliases": ["tyco", "ty-co"], "category": "Sprinkler & Van"},
        {"brand": "Reliable", "aliases": ["reliable", "rasco"], "category": "Sprinkler"},
        {"brand": "HD Fire", "aliases": ["hd fire", "hdfire"], "category": "Sprinkler"},
        {"brand": "Shinyi", "aliases": ["shinyi", "shin yi"], "category": "Van PCCC"},
        {"brand": "ARV", "aliases": ["arv", "arv valve"], "category": "Van PCCC"},
        {"brand": "Tozen", "aliases": ["tozen"], "category": "Khớp nối mềm"},
        
        # Fire Alarm & Detection
        {"brand": "Hochiki", "aliases": ["hochiki", "ho-chiki"], "category": "Báo cháy"},
        {"brand": "Notifier", "aliases": ["notifier", "honeywell notifier"], "category": "Báo cháy"},
        {"brand": "Siemens", "aliases": ["siemens"], "category": "Báo cháy & Điều khiển"},
        {"brand": "Chungmei", "aliases": ["chungmei", "chung mei"], "category": "Báo cháy"},
        {"brand": "Horing Lih", "aliases": ["horing", "horing lih"], "category": "Báo cháy"},
        {"brand": "GST", "aliases": ["gst"], "category": "Báo cháy"},
        {"brand": "Unipos", "aliases": ["unipos"], "category": "Báo cháy"},
        
        # Emergency & Exit Lights
        {"brand": "Paragon", "aliases": ["paragon"], "category": "Đèn Exit/Sự cố"},
        {"brand": "Kentom", "aliases": ["kentom", "ken-tom"], "category": "Đèn Exit/Sự cố"},
        {"brand": "Rạng Đông", "aliases": ["rang dong", "rạng đông"], "category": "Chiếu sáng"},
        
        # Pipes & Steel
        {"brand": "Hòa Phát", "aliases": ["hoa phat", "hòa phát", "hp"], "category": "Ống thép"},
        {"brand": "Hoa Sen", "aliases": ["hoa sen", "hsg"], "category": "Ống thép / Tôn"},
        {"brand": "SeAH", "aliases": ["seah", "se-ah"], "category": "Ống thép Sch40"},
        {"brand": "Vingal", "aliases": ["vingal"], "category": "Ống mạ kẽm nhúng nóng"},
        {"brand": "Tiền Phong", "aliases": ["tien phong", "tiền phong"], "category": "Ống nhựa"},
        
        # HVAC & Fans
        {"brand": "Kruger", "aliases": ["kruger"], "category": "Quạt thông gió"},
        {"brand": "Phương Linh", "aliases": ["phuong linh", "phương linh"], "category": "Quạt thông gió"},
        {"brand": "Systemair", "aliases": ["systemair"], "category": "Quạt & Thiết bị gió"},
        {"brand": "Daikin", "aliases": ["daikin"], "category": "Điều hòa"},
        {"brand": "Trane", "aliases": ["trane"], "category": "Chiller"},
        {"brand": "Vertex Duct", "aliases": ["vertex duct", "vertex z80", "vertex"], "category": "Ống gió & Phụ kiện"}
    ]

    # Default Optimal Recommended Brands for Scenario 3 (Pure BOQ)
    DEFAULT_RECOMMENDED_BRANDS = {
        "SPRINKLER": "Viking (Mỹ / SX Đài Loan)",
        "FIRE_ALARM": "Hochiki (Nhật Bản)",
        "FIRE_PIPE": "Hòa Phát (Tiêu chuẩn ASTM A53 Sch40)",
        "EXIT_LIGHT": "Paragon (Tiêu chuẩn PCCC)",
        "EXTINGUISHER": "Vertex PCCC (Có tem BCA)",
        "STANDARD_DUCT": "Vertex Z80 (Tôn Hoa Sen bích TDC)",
        "EI_DUCT": "Vertex EI (Chống cháy đạt kiểm định QCVN 06:2022)",
        "VALVES": "Shinyi (Đài Loan)",
        "PUMP": "Ebara (Ý / SX Indonesia)",
        "HOSE_CABINET": "Vertex Standard (Sơn tĩnh điện đỏ PCCC)",
        "DIFFUSER": "Vertex Louver (Nhôm định hình sơn tĩnh điện)"
    }

    @classmethod
    def detect_scenario(
        cls,
        file_path: str,
        raw_items_texts: List[str]
    ) -> Tuple[str, str]:
        """
        Determines the appropriate scenario (1, 2, or 3) for the quotation request.
        Returns: (scenario_type, scenario_description)
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        # 1. Check Scenario 1: Drawing Takeoff (.dwg, .dxf)
        if ext in [".dwg", ".dxf"]:
            return cls.SCENARIO_1, "Luồng 1: Tự động bóc tách khối lượng từ bản vẽ CAD (.dwg / .dxf)"

        # 2. Check Scenario 2: Explicit Client Brands or Pump/Technical Specifications
        has_explicit_brands = False
        brand_hits = set()
        param_hits = 0

        for text in raw_items_texts:
            b_name, _ = cls.extract_brand_from_text(text)
            if b_name:
                has_explicit_brands = True
                brand_hits.add(b_name)
            
            # Check technical pump parameters: Q=..., H=..., P=..., K=...
            if re.search(r"(?:Q\s*[:=]\s*[0-9]+|H\s*[:=]\s*[0-9]+|P\s*[:=]\s*[0-9]+|K\s*[:=]\s*[0-9.]+|kW|HP|m3/h|l/s|bar|Sch40|EI\s*[0-9]+)", text, re.IGNORECASE):
                param_hits += 1

        if has_explicit_brands or param_hits >= 2:
            brands_str = ", ".join(list(brand_hits)[:4]) if brand_hits else "Thông số kỹ thuật chi tiết"
            return cls.SCENARIO_2, f"Luồng 2: CĐT cung cấp BOQ kèm chỉ dẫn kỹ thuật/hãng ({brands_str})"

        # 3. Scenario 3: Pure Standard BOQ
        return cls.SCENARIO_3, "Luồng 3: CĐT cung cấp BOQ thuần -> Tự động tra cứu Vertex Standard Catalog & đề xuất hãng tối ưu"

    @classmethod
    def extract_brand_from_text(cls, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Scans text for explicit brand names.
        Returns: (brand_name, brand_category) or (None, None)
        """
        t_clean = f" {text.lower()} "
        for b_info in cls.KNOWN_BRANDS:
            for alias in b_info["aliases"]:
                pattern = r"\b" + re.escape(alias) + r"\b"
                if re.search(pattern, t_clean):
                    return b_info["brand"], b_info["category"]
        return None, None

    @classmethod
    def extract_technical_parameters(cls, text: str, spec: str = "") -> Dict[str, Any]:
        """
        Extracts pump parameters (Q, H, P, KW), Sprinkler K-factor, fire rating (EI), pressure (PN).
        """
        combined = f"{text} {spec}"
        params = {}

        # Flow rate Q (m3/h or l/s)
        q_match = re.search(r"Q\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m3/h|m³/h|l/s|l/p|gpm)?", combined, re.IGNORECASE)
        if q_match:
            params["flow_q"] = q_match.group(0).strip()

        # Head H (m or bar)
        h_match = re.search(r"H\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|met|bar|psi)?", combined, re.IGNORECASE)
        if h_match:
            params["head_h"] = h_match.group(0).strip()

        # Power P (kW or HP)
        p_match = re.search(r"(?:P\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:kW|HP)|([0-9]+(?:\.[0-9]+)?)\s*(?:kW|HP))", combined, re.IGNORECASE)
        if p_match:
            params["power"] = p_match.group(0).strip()

        # K-factor (Sprinkler)
        k_match = re.search(r"K\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)", combined, re.IGNORECASE)
        if k_match:
            params["k_factor"] = f"K={k_match.group(1)}"

        # Fire rating (EI)
        ei_match = re.search(r"EI\s*([0-9]{2,3})", combined, re.IGNORECASE)
        if ei_match:
            params["fire_rating"] = f"EI{ei_match.group(1)}"

        # Pressure rating (PN)
        pn_match = re.search(r"PN\s*([0-9]{1,2})", combined, re.IGNORECASE)
        if pn_match:
            params["pressure_rating"] = f"PN{pn_match.group(1)}"

        return params

    @classmethod
    def resolve_item_brand(
        cls,
        item_name: str,
        spec: str = "",
        category: str = "",
        scenario_type: str = "SCENARIO_3_STANDARD_CATALOG"
    ) -> Tuple[str, str]:
        """
        Determines the final brand name and brand source for a quote line item.
        Returns: (brand_name, brand_source)
        """
        combined = f"{item_name} {spec} {category}".lower()

        # 1. If explicit brand found in item text -> Client Specified
        detected_brand, _ = cls.extract_brand_from_text(f"{item_name} {spec}")
        if detected_brand:
            return detected_brand, "CLIENT_SPECIFIED"

        # 2. For Scenario 1 (CAD Takeoff) -> CAD Default Technical Brands
        if scenario_type == cls.SCENARIO_1:
            if any(k in combined for k in ["sprinkler", "đầu phun"]):
                return "Viking / Tyco", "CAD_TAKEOFF"
            elif any(k in combined for k in ["ống thép", "pipe", "sch40", "dn100", "dn65", "dn50"]):
                return "Hòa Phát Sch40", "CAD_TAKEOFF"
            elif any(k in combined for k in ["ống gió", "duct", "ogv"]):
                return "Vertex Z80 TDC", "CAD_TAKEOFF"
            elif any(k in combined for k in ["báo cháy", "đầu báo", "smoke"]):
                return "Hochiki", "CAD_TAKEOFF"
            elif any(k in combined for k in ["đèn exit", "sự cố"]):
                return "Paragon", "CAD_TAKEOFF"
            return "Vertex Standard", "CAD_TAKEOFF"

        # 3. For Scenario 3 (Pure BOQ) -> Propose Optimal Vertex Standard Brands
        if any(k in combined for k in ["sprinkler", "đầu phun"]):
            return cls.DEFAULT_RECOMMENDED_BRANDS["SPRINKLER"], "VERTEX_STANDARD"
        elif any(k in combined for k in ["báo cháy", "đầu báo", "báo khói", "báo nhiệt", "chuông", "nút ấn"]):
            return cls.DEFAULT_RECOMMENDED_BRANDS["FIRE_ALARM"], "VERTEX_STANDARD"
        elif any(k in combined for k in ["đèn exit", "exit", "thoát hiểm", "sự cố", "emergency"]):
            return cls.DEFAULT_RECOMMENDED_BRANDS["EXIT_LIGHT"], "VERTEX_STANDARD"
        elif any(k in combined for k in ["bình chữa cháy", "bình bột", "bình co2", "mfzl", "mt3"]):
            return cls.DEFAULT_RECOMMENDED_BRANDS["EXTINGUISHER"], "VERTEX_STANDARD"
        elif any(k in combined for k in ["ống thép", "ống chữa cháy", "sch40", "dn25", "dn50", "dn100"]):
            return cls.DEFAULT_RECOMMENDED_BRANDS["FIRE_PIPE"], "VERTEX_STANDARD"
        elif any(k in combined for k in ["ei 120", "ei 60", "ei 45", "ei 30", "chống cháy"]):
            return cls.DEFAULT_RECOMMENDED_BRANDS["EI_DUCT"], "VERTEX_STANDARD"
        elif any(k in combined for k in ["ống gió", "duct", "ogv", "ogt"]):
            return cls.DEFAULT_RECOMMENDED_BRANDS["STANDARD_DUCT"], "VERTEX_STANDARD"
        elif any(k in combined for k in ["van", "valve", "fd", "vcd"]):
            return cls.DEFAULT_RECOMMENDED_BRANDS["VALVES"], "VERTEX_STANDARD"
        elif any(k in combined for k in ["máy bơm", "bơm chữa cháy"]):
            return cls.DEFAULT_RECOMMENDED_BRANDS["PUMP"], "VERTEX_STANDARD"
        elif any(k in combined for k in ["tủ", "hộp", "cuộn vòi"]):
            return cls.DEFAULT_RECOMMENDED_BRANDS["HOSE_CABINET"], "VERTEX_STANDARD"
        elif any(k in combined for k in ["miệng gió", "cửa gió", "diffuser"]):
            return cls.DEFAULT_RECOMMENDED_BRANDS["DIFFUSER"], "VERTEX_STANDARD"

        return "Vertex Standard (Việt Nam)", "VERTEX_STANDARD"
