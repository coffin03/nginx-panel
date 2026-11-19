"""解析 X.509 证书的基本信息。

只读取面板展示需要的字段（有效期、域名、签发者、指纹），因此用纯标准库
手写最小 DER 解析，避免为打包版增加 cryptography 之类的重依赖。
"""

import base64
import hashlib
import re
from datetime import datetime, timezone
from typing import Dict, List, Tuple

_PEM_RE = re.compile(rb"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----", re.S)
_BEGIN_RE = re.compile(rb"-----BEGIN ([^-]+)-----(.+?)-----END \1-----", re.S)

_OID_CN = "2.5.4.3"
_OID_O = "2.5.4.10"
_OID_SAN = "2.5.29.17"

_SIGNATURE_ALGS = {
    "1.2.840.113549.1.1.5": "sha1WithRSAEncryption",
    "1.2.840.113549.1.1.11": "sha256WithRSAEncryption",
    "1.2.840.113549.1.1.12": "sha384WithRSAEncryption",
    "1.2.840.113549.1.1.13": "sha512WithRSAEncryption",
    "1.2.840.10045.4.3.2": "ecdsa-with-SHA256",
    "1.2.840.10045.4.3.3": "ecdsa-with-SHA384",
    "1.2.840.10045.4.3.4": "ecdsa-with-SHA512",
}


class CertError(ValueError):
    """证书内容无法解析。"""


def _tlv(data: bytes, pos: int) -> Tuple[int, int, int]:
    """返回 (tag, value_start, value_end)。"""
    if pos + 2 > len(data):
        raise CertError("truncated")
    tag = data[pos]
    pos += 1
    first = data[pos]
    pos += 1
    if first & 0x80:
        count = first & 0x7F
        if count == 0 or count > 4 or pos + count > len(data):
            raise CertError("bad length")
        length = int.from_bytes(data[pos : pos + count], "big")
        pos += count
    else:
        length = first
    end = pos + length
    if end > len(data):
        raise CertError("truncated")
    return tag, pos, end


def _children(data: bytes, start: int, end: int) -> List[Tuple[int, int, int]]:
    items = []
    pos = start
    while pos < end:
        tag, vstart, vend = _tlv(data, pos)
        items.append((tag, vstart, vend))
        pos = vend
    return items


def _oid(raw: bytes) -> str:
    if not raw:
        return ""
    first = raw[0]
    if first >= 80:
        parts = [2, first - 80]
    elif first >= 40:
        parts = [1, first - 40]
    else:
        parts = [0, first]
    value = 0
    for byte in raw[1:]:
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            parts.append(value)
            value = 0
    return ".".join(str(p) for p in parts)


def _text(tag: int, raw: bytes) -> str:
    if tag == 0x1E:
        return raw.decode("utf-16-be", "replace")
    if tag in (0x14, 0x13):
        return raw.decode("latin-1", "replace")
    return raw.decode("utf-8", "replace")


def _name(data: bytes, start: int, end: int) -> Dict[str, str]:
    """解析 RDNSequence，返回 OID -> 第一个值。"""
    values: Dict[str, str] = {}
    for tag, s, e in _children(data, start, end):
        if tag != 0x31:  # SET
            continue
        for tag2, s2, e2 in _children(data, s, e):
            if tag2 != 0x30:  # SEQUENCE
                continue
            parts = _children(data, s2, e2)
            if len(parts) < 2:
                continue
            key = _oid(data[parts[0][1] : parts[0][2]])
            if key not in values:
                values[key] = _text(parts[1][0], data[parts[1][1] : parts[1][2]])
    return values


def _time(tag: int, raw: bytes) -> datetime:
    text = raw.decode("ascii", "replace").strip().rstrip("Z")
    if "." in text:
        text = text.split(".")[0]
    if tag == 0x17:  # UTCTime
        year = int(text[0:2])
        year = 2000 + year if year < 50 else 1900 + year
        rest = text[2:]
    else:  # GeneralizedTime
        year = int(text[0:4])
        rest = text[4:]
    rest = (rest + "0000")[:10]
    return datetime(
        year,
        int(rest[0:2]),
        int(rest[2:4]),
        int(rest[4:6]),
        int(rest[6:8]),
        int(rest[8:10]),
        tzinfo=timezone.utc,
    )


def _san_domains(data: bytes, tbs: List[Tuple[int, int, int]], start_index: int) -> List[str]:
    for tag, s, e in tbs[start_index:]:
        if tag != 0xA3:  # [3] EXPLICIT Extensions
            continue
        wrapper = _children(data, s, e)
        if not wrapper or wrapper[0][0] != 0x30:
            continue
        for ext in _children(data, wrapper[0][1], wrapper[0][2]):
            parts = _children(data, ext[1], ext[2])
            if len(parts) < 2:
                continue
            if _oid(data[parts[0][1] : parts[0][2]]) != _OID_SAN:
                continue
            value_index = 1
            if parts[1][0] == 0x01:  # critical BOOLEAN
                value_index = 2
            if value_index >= len(parts) or parts[value_index][0] != 0x04:
                continue
            inner_tag, inner_s, inner_e = _tlv(data, parts[value_index][1])
            if inner_tag != 0x30:
                continue
            domains = []
            for gtag, gs, ge in _children(data, inner_s, inner_e):
                if gtag == 0x82:  # dNSName
                    domains.append(data[gs:ge].decode("ascii", "replace"))
            return domains
    return []


def parse_der(der: bytes) -> dict:
    tag, s, e = _tlv(der, 0)
    if tag != 0x30:
        raise CertError("not a certificate")
    top = _children(der, s, e)
    if len(top) < 3:
        raise CertError("not a certificate")
    tbs = _children(der, top[0][1], top[0][2])
    index = 0
    if tbs and tbs[0][0] == 0xA0:  # [0] version
        index = 1
    if len(tbs) < index + 6:
        raise CertError("not a certificate")
    serial = der[tbs[index][1] : tbs[index][2]].hex().upper()
    index += 1
    index += 1  # signature AlgorithmIdentifier
    issuer = tbs[index]
    index += 1
    validity = tbs[index]
    index += 1
    subject = tbs[index]
    index += 1

    times = _children(der, validity[1], validity[2])
    if len(times) < 2:
        raise CertError("missing validity")
    not_before = _time(times[0][0], der[times[0][1] : times[0][2]])
    not_after = _time(times[1][0], der[times[1][1] : times[1][2]])

    subject_attrs = _name(der, subject[1], subject[2])
    issuer_attrs = _name(der, issuer[1], issuer[2])

    domains = _san_domains(der, tbs, index + 1)
    common_name = subject_attrs.get(_OID_CN, "")
    if not domains and common_name:
        domains = [common_name]

    sig_parts = _children(der, top[1][1], top[1][2])
    sig_oid = _oid(der[sig_parts[0][1] : sig_parts[0][2]]) if sig_parts else ""

    return {
        "subject": common_name or subject_attrs.get(_OID_O, ""),
        "issuer": issuer_attrs.get(_OID_CN, "") or issuer_attrs.get(_OID_O, ""),
        "domains": domains,
        "not_before": not_before.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "not_after": not_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "serial": serial,
        "sha256": hashlib.sha256(der).hexdigest().upper(),
        "signature_algorithm": _SIGNATURE_ALGS.get(sig_oid, sig_oid),
    }


def load_certificate(path: str) -> dict:
    """读取 PEM（或 DER）证书文件并返回解析结果。"""
    with open(path, "rb") as fh:
        raw = fh.read()
    match = _PEM_RE.search(raw)
    if match:
        der = base64.b64decode(re.sub(rb"\s+", b"", match.group(1)))
    elif raw.lstrip().startswith(b"-----BEGIN"):
        match = _BEGIN_RE.search(raw)
        if not match:
            raise CertError("no PEM block found")
        der = base64.b64decode(re.sub(rb"\s+", b"", match.group(2)))
    else:
        der = raw
    return parse_der(der)