"""
Labor Cost Matrix (Ma Trận Đơn Giá Nhân Công Cố Định) for Vertex Construction & PCCC Quote System
Provides deterministic, standard labor cost rates:
1. Ống chữa cháy: 220.000 VNĐ / mét ống (m)
2. Thiết bị báo cháy: 350.000 VNĐ / thiết bị (bộ/cái)
3. Đèn Exit / sự cố: 370.000 VNĐ / thiết bị (bộ/cái)
4. Ống gió thường: 100.000 VNĐ / mét vuông (m²)
5. Ống gió chống cháy (EI 30, EI 45, EI 60): 130.000 VNĐ / mét vuông (m²)
6. Ống gió chống cháy (EI 120): 155.000 VNĐ / mét vuông (m²)
"""
import re
from typing import Tuple, Dict, Any


class LaborCostMatrix:
    """
    Fixed Labor Cost Matrix for Technical Quotations & BOQ Estimation
    """
    # 6 Core Mandated Labor Rates (VNĐ)
    RATE_FIRE_PIPE = 220000.0         # 220.000 đ/m
    RATE_FIRE_ALARM_DEVICE = 350000.0 # 350.000 đ/thiết bị
    RATE_EMERGENCY_LIGHT = 370000.0   # 370.000 đ/thiết bị
    RATE_STANDARD_DUCT = 100000.0     # 100.000 đ/m²
    RATE_EI_DUCT_30_60 = 130000.0     # 130.000 đ/m² (EI30, EI45, EI60)
    RATE_EI_DUCT_120 = 155000.0       # 155.000 đ/m² (EI120)

    # Standard Ancillary Equipment Rates (VNĐ)
    RATE_SPRINKLER = 50000.0          # 50.000 đ/đầu phun
    RATE_EXTINGUISHER = 30000.0       # 30.000 đ/bình
    RATE_HOSE_CABINET = 250000.0      # 250.000 đ/hộp tủ vách tường
    RATE_VALVE_DAMPER = 150000.0      # 150.000 đ/van
    RATE_DIFFUSER = 80000.0           # 80.000 đ/miệng gió
    RATE_PUMP_STATION = 5000000.0     # 5.000.000 đ/tổ hợp bơm

    @classmethod
    def get_labor_rate_and_description(
        cls,
        item_name: str,
        spec: str = "",
        category: str = "",
        unit: str = "cái"
    ) -> Tuple[float, str]:
        """
        Determines the fixed labor unit cost and human-readable description for an item.
        Returns: (labor_unit_cost, description)
        """
        combined = f"{item_name} {spec} {category}".lower()

        # 1. Ống gió chống cháy EI 120
        if any(k in combined for k in ["ei 120", "ei120", "120 phút", "120p"]):
            if any(k in combined for k in ["ống gió", "duct", "ogv", "ogt", "hút khói", "thông gió"]):
                return cls.RATE_EI_DUCT_120, "Nhân công bọc & lắp đặt ống gió chống cháy EI 120 (155.000 đ/m²)"

        # 2. Ống gió chống cháy EI 30, EI 45, EI 60
        if any(k in combined for k in ["ei 30", "ei30", "ei 45", "ei45", "ei 60", "ei60", "chống cháy", "bọc vữa", "bọc thạch cao", "bọc bông"]):
            if any(k in combined for k in ["ống gió", "duct", "ogv", "ogt", "hút khói", "thông gió"]):
                return cls.RATE_EI_DUCT_30_60, "Nhân công bọc & lắp đặt ống gió chống cháy EI 30/45/60 (130.000 đ/m²)"

        # 3. Ống gió thường (Tôn mạ kẽm Z80, bích TDC/V)
        if any(k in combined for k in ["ống gió", "duct", "ogv", "ogt", "bích tdc", "bích v", "tiêu âm"]) or any(k in combined for k in ["ống gió vuông", "ống gió tròn"]):
            return cls.RATE_STANDARD_DUCT, "Nhân công gia công & lắp đặt ống gió thường (100.000 đ/m²)"

        # 4. Đèn Exit / Sự cố (Emergency lights)
        if any(k in combined for k in ["đèn exit", "exit", "thoát hiểm", "sự cố", "emergency", "chiếu sáng sự cố"]):
            return cls.RATE_EMERGENCY_LIGHT, "Nhân công lắp đặt & đấu nối đèn Exit/sự cố (370.000 đ/thiết bị)"

        # 5. Thiết bị báo cháy (Đầu báo khói, báo nhiệt, nút ấn, chuông, còi, module)
        if any(k in combined for k in [
            "báo cháy", "đầu báo", "báo khói", "báo nhiệt", "nút ấn", "chuông", "còi",
            "module", "tủ trung tâm", "smoke detector", "heat detector", "manual call point"
        ]):
            return cls.RATE_FIRE_ALARM_DEVICE, "Nhân công lắp đặt & cài đặt thiết bị báo cháy (350.000 đ/thiết bị)"

        # 6. Đường ống chữa cháy (Ống thép Sch40, ống tráng kẽm, ống cấp nước PCCC)
        if any(k in combined for k in [
            "ống thép", "ống chữa cháy", "ống pccc", "ống cứu hỏa", "ống nước chữa cháy",
            "sch40", "sch 40", "dn25", "dn32", "dn40", "dn50", "dn65", "dn80", "dn100",
            "dn125", "dn150", "dn200", "dn250", "dn300"
        ]) or (unit.lower() in ["m", "mét"] and any(k in combined for k in ["ống", "pipe"])):
            return cls.RATE_FIRE_PIPE, "Nhân công lắp đặt & nối rãnh/ren đường ống chữa cháy (220.000 đ/m)"

        # 7. Tổ hợp máy bơm PCCC
        if any(k in combined for k in ["máy bơm", "bơm chữa cháy", "bơm cứu hỏa", "bơm điện", "bơm diesel", "bơm bù", "ebara", "grundfos"]):
            return cls.RATE_PUMP_STATION, "Nhân công lắp đặt, định vị & căn chỉnh tổ hợp máy bơm (5.000.000 đ/bộ)"

        # 8. Tủ chữa cháy vách tường
        if any(k in combined for k in ["tủ chữa cháy", "hộp chữa cháy", "tủ vách tường", "cuộn vòi", "lăng phun"]):
            return cls.RATE_HOSE_CABINET, "Nhân công lắp đặt tủ PCCC vách tường & cuộn vòi (250.000 đ/bộ)"

        # 9. Van ngăn cháy & Van PCCC
        if any(k in combined for k in ["van", "valve", "fd", "vcd", "md", "nrd", "van cổng", "van bướm", "van một chiều", "van góc"]):
            return cls.RATE_VALVE_DAMPER, "Nhân công lắp đặt van PCCC / van gió (150.000 đ/cái)"

        # 10. Miệng gió / Cửa gió
        if any(k in combined for k in ["miệng gió", "cửa gió", "diffuser", "louver", "grille"]):
            return cls.RATE_DIFFUSER, "Nhân công lắp đặt miệng gió (80.000 đ/bộ)"

        # 11. Đầu phun Sprinkler
        if any(k in combined for k in ["sprinkler", "đầu phun"]):
            return cls.RATE_SPRINKLER, "Nhân công lắp đặt đầu phun Sprinkler (50.000 đ/bộ)"

        # 12. Bình chữa cháy
        if any(k in combined for k in ["bình chữa cháy", "bình bột", "bình co2", "mfzl", "mt3", "mt5", "extinguisher"]):
            return cls.RATE_EXTINGUISHER, "Nhân công bàn giao & bố trí bình chữa cháy (30.000 đ/bình)"

        return 0.0, "Đã bao gồm trong chi phí trọn gói"
