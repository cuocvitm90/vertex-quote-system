"""
Vietnamese CAD Text Decoder & Encoding Repair Engine for Vertex Quote System
Handles:
1. AutoCAD formatting codes: \\P, \\U+XXXX, %%d, %%c, %%p, {\\f...;...}
2. Legacy TCVN3 (ABC) single-byte fonts (.vnTime, .vnArial, .vnTeknisch)
3. VNI-Windows fonts (VNI-Times, VNI-Helve, VNI-Aptima)
4. Corrupted mojibake CAD text repair (e.g. '¡ng th¡p m¡ k\"m DN50' -> 'Ống thép mạ kẽm DN50')
5. Safe unaccented fallback mechanism to ensure NO garbled characters are displayed.
"""
import re
from typing import Optional


class VietnameseCADTextDecoder:
    """
    Decodes and repairs Vietnamese text extracted from CAD DXF and DWG drawings.
    """

    # 1. TCVN3 (ABC) Character Map (1-byte characters mapped to Unicode)
    TCVN3_CHAR_MAP = {
        # Lowercase vowels
        '\xb5': 'à', '\xb8': 'á', '\xb6': 'ả', '\xb7': 'ã', '\xb9': 'ạ',
        '\xa8': 'ă', '\xbb': 'ằ', '\xbe': 'ắ', '\xbc': 'ẳ', '\xbd': 'ẵ', '\xc6': 'ặ',
        '\xa9': 'â', '\xc7': 'ầ', '\xca': 'ấ', '\xc8': 'ẩ', '\xc9': 'ẫ', '\xcb': 'ậ',
        '\xcc': 'è', '\xd0': 'é', '\xce': 'ẻ', '\xcf': 'ẽ', '\xd1': 'ẹ',
        '\xaa': 'ê', '\xd2': 'ề', '\xd5': 'ế', '\xd3': 'ể', '\xd4': 'ễ', '\xd6': 'ệ',
        '\xd7': 'ì', '\xdd': 'í', '\xd8': 'ỉ', '\xdc': 'ĩ', '\xde': 'ị',
        '\xdf': 'ò', '\xe3': 'ó', '\xe1': 'ỏ', '\xe2': 'õ', '\xe4': 'ọ',
        '\xab': 'ô', '\xe5': 'ồ', '\xe8': 'ố', '\xe6': 'ổ', '\xe7': 'ỗ', '\xe9': 'ộ',
        '\xac': 'ơ', '\xea': 'ờ', '\xed': 'ớ', '\xeb': 'ở', '\xec': 'ỡ', '\xee': 'ợ',
        '\xef': 'ù', '\xf3': 'ú', '\xf1': 'ủ', '\xf2': 'ũ', '\xf4': 'ụ',
        '\xad': 'ư', '\xf5': 'ừ', '\xf8': 'ứ', '\xf6': 'ử', '\xf7': 'ữ', '\xf9': 'ự',
        '\xfa': 'ỳ', '\xfd': 'ý', '\xfb': 'ỷ', '\xfc': 'ỹ', '\xfe': 'ỵ',
        '\xae': 'đ',

        # Uppercase vowels in TCVN3
        '\xa1': 'Ă', '\xa2': 'Â', '\xa3': 'Ê', '\xa4': 'Ô', '\xa5': 'Ơ', '\xa6': 'Ư', '\xa7': 'Đ'
    }

    # 2. VNI-Windows Character Map
    VNI_COMPOUND_MAP = [
        # Uppercase compound
        ('AÙ', 'Á'), ('AØ', 'À'), ('AÛ', 'Ả'), ('AÕ', 'Ã'), ('AÏ', 'Ạ'),
        ('AÊ', 'Ă'), ('AÉ', 'Ắ'), ('AÈ', 'Ằ'), ('AÚ', 'Ẳ'), ('AÜ', 'Ẵ'), ('AË', 'Ặ'),
        ('AÂ', 'Â'), ('AÁ', 'Ấ'), ('AÀ', 'Ầ'), ('AÅ', 'Ẩ'), ('AÃ', 'Ẫ'), ('AÄ', 'Ậ'),
        ('EÙ', 'É'), ('EØ', 'È'), ('EÛ', 'Ẻ'), ('EÕ', 'Ẽ'), ('EÏ', 'Ẹ'),
        ('EÂ', 'Ê'), ('EÁ', 'Ế'), ('EÀ', 'Ề'), ('EÅ', 'Ể'), ('EÃ', 'Ễ'), ('EÄ', 'Ệ'),
        ('IÙ', 'Í'), ('IØ', 'Ì'), ('IÛ', 'Ỉ'), ('IÕ', 'Ĩ'), ('IÏ', 'Ị'),
        ('OÙ', 'Ó'), ('OØ', 'Ò'), ('OÛ', 'Ỏ'), ('OÕ', 'Õ'), ('OÏ', 'Ọ'),
        ('OÂ', 'Ô'), ('OÁ', 'Ố'), ('OÀ', 'Ồ'), ('OÅ', 'Ổ'), ('OÃ', 'Ỗ'), ('OÄ', 'Ộ'),
        ('ÔÙ', 'Ớ'), ('ÔØ', 'Ờ'), ('ÔÛ', 'Ở'), ('ÔÕ', 'Ỡ'), ('ÔÏ', 'Ợ'),
        ('UÙ', 'Ú'), ('UØ', 'Ù'), ('UÛ', 'Ủ'), ('UÕ', 'Ũ'), ('UÏ', 'Ụ'),
        ('ÖÙ', 'Ứ'), ('ÖØ', 'Ừ'), ('ÖÛ', 'Ử'), ('ÖÕ', 'Ữ'), ('ÖÏ', 'Ự'),
        ('YÙ', 'Ý'), ('YØ', 'Ỳ'), ('YÛ', 'Ỷ'), ('YÕ', 'Ỹ'),
        ('Ñ', 'Đ'),

        # Lowercase compound
        ('aù', 'á'), ('aø', 'à'), ('aû', 'ả'), ('aõ', 'ã'), ('aï', 'ạ'),
        ('aê', 'ă'), ('aé', 'ắ'), ('aè', 'ằ'), ('aú', 'ẳ'), ('aü', 'ẵ'), ('aë', 'ặ'),
        ('aâ', 'â'), ('aá', 'ấ'), ('aà', 'ầ'), ('aå', 'ẩ'), ('aã', 'ẫ'), ('aä', 'ậ'),
        ('eù', 'é'), ('eø', 'è'), ('eû', 'ẻ'), ('eõ', 'ẽ'), ('eï', 'ẹ'),
        ('eâ', 'ê'), ('eá', 'ế'), ('eà', 'ề'), ('eå', 'ể'), ('eã', 'ễ'), ('eä', 'ệ'),
        ('iù', 'í'), ('iø', 'ì'), ('iû', 'ỉ'), ('iõ', 'ĩ'), ('iï', 'ị'),
        ('où', 'ó'), ('oø', 'ò'), ('oû', 'ỏ'), ('oõ', 'õ'), ('oï', 'ọ'),
        ('oâ', 'ô'), ('oá', 'ố'), ('oà', 'ồ'), ('oå', 'ổ'), ('oã', 'ỗ'), ('oä', 'ộ'),
        ('ôù', 'ớ'), ('ôø', 'ờ'), ('ôû', 'ở'), ('ôõ', 'ỡ'), ('ôï', 'ợ'),
        ('uù', 'ú'), ('uø', 'ù'), ('uû', 'ủ'), ('uõ', 'ũ'), ('uï', 'ụ'),
        ('öù', 'ứ'), ('öø', 'ừ'), ('öû', 'ử'), ('öõ', 'ữ'), ('öï', 'ự'),
        ('yù', 'ý'), ('yø', 'ỳ'), ('yû', 'ỷ'), ('yõ', 'ỹ'), ('î', 'ỵ'),
        ('ñ', 'đ'), ('ö', 'ư'), ('ô', 'ơ')
    ]

    # 3. Known CAD Mojibake & Technical Term Replacements
    CAD_MOJIBAKE_PATTERNS = [
        # Full phrase repairs
        (re.compile(r"[¡i\u1ed0\u0102\u1ed1\u00f4]ng\s+th[¡a\u1ed0\u0102\u00e9\xd0e]p\s+m[¡a\u1ea1\xb9\u1ed0\u0102]\s+k[\"e\u1ebd\xcf\\]+m", re.IGNORECASE), "Ống thép mạ kẽm"),
        (re.compile(r"[¡i\u1ed0\u0102\u1ed1\u00f4]ng\s+th[¡a\u1ed0\u0102\u00e9\xd0e]p", re.IGNORECASE), "Ống thép"),
        (re.compile(r"m[¡a\u1ea1\xb9\u1ed0\u0102]\s+k[\"e\u1ebd\xcf\\]+m", re.IGNORECASE), "mạ kẽm"),
        (re.compile(r"[¡i\u1ed0\u0102\u1ed1\u00f4]ng\s+gi[oã\u00f3\u1ed1]", re.IGNORECASE), "Ống gió"),
        (re.compile(r"ch[oè\u1ed1]ng\s+ch[¡a\u00e1]y", re.IGNORECASE), "chống cháy"),
        (re.compile(r"b[i×\u00ec]nh\s+ch[u÷\u1eef]a\s+ch[a¸\u00e1]y", re.IGNORECASE), "Bình chữa cháy"),
        (re.compile(r"[d®][aÇ\u1ea7]u\s+b[a¸\u00e1]o\s+kh[oã\u00f3]i", re.IGNORECASE), "Đầu báo khói"),
        (re.compile(r"[d®][aÇ\u1ea7]u\s+b[a¸\u00e1]o\s+nhi[eÖ\u1ec7]t", re.IGNORECASE), "Đầu báo nhiệt"),
        (re.compile(r"[d®][eÌ\u00e8]n\s+exit", re.IGNORECASE), "Đèn Exit"),
        (re.compile(r"[d®][eÌ\u00e8]n\s+s[uù\u1ef1]\s+c[oè\u1ed1]", re.IGNORECASE), "Đèn sự cố"),
        (re.compile(r"[d®][aÇ\u1ea7]u\s+phun\s+sprinkler", re.IGNORECASE), "Đầu phun Sprinkler"),
        (re.compile(r"van\s+ng[a¨\u0103]n\s+ch[a¸\u00e1]y", re.IGNORECASE), "Van ngăn cháy"),
        (re.compile(r"mi[eÖ\u1ec7]ng\s+gi[oã\u00f3]", re.IGNORECASE), "Miệng gió"),
        (re.compile(r"c[uö\u1eeda]\s+gi[oã\u00f3]", re.IGNORECASE), "Cửa gió"),
        (re.compile(r"t[uñ\u1ee7]\s+ch[u÷\u1eef]a\s+ch[a¸\u00e1]y", re.IGNORECASE), "Tủ chữa cháy"),
        (re.compile(r"tr[uñ\u1ee5]\s+c[uù\u1ee9]u\s+h[oả\u1ecfa]a", re.IGNORECASE), "Trụ cứu hỏa"),
        (re.compile(r"v[oø\u00f2]i\s+ch[u÷\u1eef]a\s+ch[a¸\u00e1]y", re.IGNORECASE), "Vòi chữa cháy"),

        # Word-level repairs
        (re.compile(r"\b[¡\u1ed0\u0102]ng\b", re.IGNORECASE), "Ống"),
        (re.compile(r"\bth[¡\u1ed0\u0102]p\b", re.IGNORECASE), "thép"),
        (re.compile(r"\bm[¡\u1ed0\u0102]\b", re.IGNORECASE), "mạ"),
        (re.compile(r"\bk[\"e\u1ebd\xcf\\]+m\b", re.IGNORECASE), "kẽm")
    ]

    @classmethod
    def clean_autocad_formatting(cls, text: str) -> str:
        """
        Removes AutoCAD MTEXT formatting codes and handles Unicode escape sequences.
        """
        if not text:
            return ""

        s = str(text)

        # 1. Decode Unicode escape sequences: \\U+XXXX or \U+XXXX (e.g. \U+1ED1 -> ố)
        def _replace_u_escape(match):
            hex_code = match.group(1)
            try:
                return chr(int(hex_code, 16))
            except Exception:
                return match.group(0)

        s = re.sub(r"(?:\\U\+|\\u\+)([0-9a-fA-F]{4})", _replace_u_escape, s)

        # 2. AutoCAD special symbols
        s = s.replace("%%c", "Ø").replace("%%C", "Ø")
        s = s.replace("%%d", "°").replace("%%D", "°")
        s = s.replace("%%p", "±").replace("%%P", "±")
        s = s.replace("%%u", "").replace("%%U", "")

        # 3. Strip MTEXT formatting codes
        # Remove font definitions: {\f...;...}
        s = re.sub(r"\{\\f[^;]*;([^}]*)\}", r"\1", s)
        # Remove alignment, color, height codes: \A1;, \C1;, \H1.5;, \W0.8;, \Q30;
        s = re.sub(r"\\[AaCcHhWwQq][0-9.]+;", "", s)
        # Remove paragraphs \P and linebreaks
        s = s.replace("\\P", " ").replace("\\p", " ")
        s = s.replace("\\~", " ")
        s = re.sub(r"\\[LlOoKk]", "", s)
        s = re.sub(r"[{}\\]", " ", s)

        return re.sub(r"\s+", " ", s).strip()

    @classmethod
    def is_already_unicode(cls, text: str) -> bool:
        """
        Returns True if the text contains standard Vietnamese precomposed Unicode characters (ord >= 256).
        """
        # Checks for standard Vietnamese Unicode vowels/consonants like Ố, ế, ạ, đ, ư, ơ...
        return any(ord(ch) >= 256 for ch in text)

    @classmethod
    def is_vni(cls, text: str) -> bool:
        """
        Detects if a string is encoded in VNI-Windows format.
        """
        if cls.is_already_unicode(text):
            return False

        vni_signatures = [
            'aù', 'aø', 'aû', 'aõ', 'aï', 'aê', 'aé', 'aè', 'aú', 'aü', 'aë', 'aâ', 'aá', 'aà', 'aå', 'aã', 'aä',
            'eù', 'eø', 'eû', 'eõ', 'eï', 'eâ', 'eá', 'eà', 'eå', 'eã', 'eä',
            'iù', 'iø', 'iû', 'iõ', 'iï',
            'où', 'oø', 'oû', 'oõ', 'oï', 'oâ', 'oá', 'oà', 'oå', 'oã', 'oä',
            'ôù', 'ôø', 'ôû', 'ôõ', 'ôï',
            'uù', 'uø', 'uû', 'uõ', 'uï', 'öù', 'öø', 'öû', 'öõ', 'öï',
            'yù', 'yø', 'yû', 'yõ',
            'AÙ', 'AØ', 'AÂ', 'AÁ', 'EÂ', 'EÁ', 'OÁ', 'OÂ', 'ÖÙ', 'ÔÙ', 'Ñ', 'ñ'
        ]
        return any(sig in text for sig in vni_signatures)

    @classmethod
    def is_tcvn3(cls, text: str) -> bool:
        """
        Detects if a string is encoded in TCVN3 format using distinct TCVN3 signature bytes.
        """
        if cls.is_already_unicode(text):
            return False

        tcvn3_distinct_signatures = [
            '\xa1', '\xa2', '\xa3', '\xa4', '\xa5', '\xa6', '\xa7',
            '\xa8', '\xa9', '\xaa', '\xab', '\xac', '\xad', '\xae',
            '\xb5', '\xb6', '\xb7', '\xb8', '\xb9',
            '\xbb', '\xbc', '\xbd', '\xbe',
            '\xc6', '\xc7', '\xc8', '\xc9', '\xca', '\xcb',
            '\xcc', '\xd0', '\xd1', '\xd2', '\xd3', '\xd4', '\xd5', '\xd6',
            '\xd7', '\xdd', '\xd8', '\xdc', '\xde'
        ]
        return any(ch in text for ch in tcvn3_distinct_signatures)

    @classmethod
    def decode_tcvn3(cls, text: str) -> str:
        """
        Converts TCVN3 / ABC encoded strings into UTF-8 Unicode.
        """
        if not text:
            return ""

        chars = []
        for ch in text:
            chars.append(cls.TCVN3_CHAR_MAP.get(ch, ch))
        return "".join(chars)

    @classmethod
    def decode_vni(cls, text: str) -> str:
        """
        Converts VNI-Windows compound strings into UTF-8 Unicode.
        """
        if not text:
            return ""

        s = text
        for vni_seq, utf8_char in cls.VNI_COMPOUND_MAP:
            s = s.replace(vni_seq, utf8_char)
        return s

    @classmethod
    def repair_mojibake_and_lexicon(cls, text: str) -> str:
        """
        Repairs known CAD engineering terms corrupted by legacy font decoders.
        """
        if not text:
            return ""

        s = text
        for pattern, replacement in cls.CAD_MOJIBAKE_PATTERNS:
            s = pattern.sub(replacement, s)
        return s

    @classmethod
    def sanitize_unaccented_fallback(cls, text: str) -> str:
        """
        Removes remaining corrupt non-ASCII characters and produces clean, readable text.
        """
        if not text:
            return ""

        # Replace common corrupt symbols with legible equivalents
        corrupt_replacements = {
            '¡': 'O', '¢': 'A', '£': 'E', '¤': 'O', '¥': 'O', '¦': 'U', '§': 'D',
            '©': 'c', '®': 'd', 'µ': 'u', '¶': 'a', '·': 'a', '¸': 'a', '¹': 'a',
            'º': 'a', '»': 'a', '¼': 'a', '½': 'a', '¾': 'a', '¿': 'a',
            '\"m': 'em', '¡ng': 'Ong', 'th¡p': 'thep', 'm¡': 'ma', 'k"m': 'kem'
        }

        s = text
        for k, v in corrupt_replacements.items():
            s = s.replace(k, v)

        # Remove non-printable and suspicious orphan control bytes
        s = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", "", s)
        return re.sub(r"\s+", " ", s).strip()

    @classmethod
    def decode_cad_string(cls, raw_text: str) -> str:
        """
        Full Pipeline:
        1. Strips AutoCAD MTEXT formatting & decodes \\U+XXXX.
        2. Detects VNI or TCVN3 and converts to Unicode.
        3. Applies technical engineering lexicon repair for corrupted CAD terms.
        4. Applies unaccented clean fallback if any corrupt bytes remain.
        """
        if not raw_text:
            return ""

        # 1. Clean AutoCAD controls & format escapes
        s = cls.clean_autocad_formatting(raw_text)

        # 2. Check and decode VNI vs TCVN3
        if cls.is_vni(s):
            s = cls.decode_vni(s)
        elif cls.is_tcvn3(s):
            s = cls.decode_tcvn3(s)

        # 3. Repair CAD mojibake & technical lexicon
        s = cls.repair_mojibake_and_lexicon(s)

        # 4. Fallback sanitize to ensure no garbled characters remain
        s = cls.sanitize_unaccented_fallback(s)

        return s.strip()
