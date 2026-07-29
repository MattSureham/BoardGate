"""Conservative, evidence-preserving project file classification."""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from boardgate.domain.enums import FileType
from boardgate.domain.source import ClassificationCandidate

_DETECTION_BYTES = 512 * 1024
_STRONG_EVIDENCE = 0.70
_GERBER_SUFFIXES = frozenset(
    {
        ".art",
        ".cmp",
        ".g1",
        ".g2",
        ".gbl",
        ".gbo",
        ".gbp",
        ".gbr",
        ".gbs",
        ".ger",
        ".gko",
        ".gm1",
        ".gml",
        ".gpi",
        ".gtl",
        ".gto",
        ".gtp",
        ".gts",
        ".pho",
        ".sol",
    }
)
_DRILL_SUFFIXES = frozenset({".drl", ".drd", ".exc", ".ncd", ".tap", ".xln"})
_GERBER_FILE_FUNCTION = re.compile(
    rb"%TF\.FileFunction,([^*%]+)\*%",
    flags=re.IGNORECASE,
)
_GERBER_SAME_COORDINATES = re.compile(
    rb"%TF\.SameCoordinates,([^*%]+)\*%",
    flags=re.IGNORECASE,
)
_EXCELLON_TOOL = re.compile(rb"(?:^|[\r\n])T\d{1,4}C[+\-]?\d", re.IGNORECASE)
_EXCELLON_COORDINATE = re.compile(
    rb"(?:^|[\r\n])(?:G0[05])?X[+\-]?\d+Y[+\-]?\d+",
    re.IGNORECASE,
)
_NORMALIZE_HEADER = re.compile(r"[^a-z0-9]+")
_REFERENCE_HEADERS = frozenset(
    {
        "designator",
        "designators",
        "ref",
        "refdes",
        "reference",
        "referencedesignator",
        "references",
    }
)
_BOM_HEADERS = frozenset(
    {
        "description",
        "footprint",
        "manufacturerpartnumber",
        "mpn",
        "partnumber",
        "quantity",
        "qty",
        "value",
    }
)
_X_HEADERS = frozenset({"centerx", "midx", "posx", "positionx", "x"})
_Y_HEADERS = frozenset({"centery", "midy", "posy", "positiony", "y"})
_PLACEMENT_HEADERS = frozenset(
    {"layer", "rotation", "rot", "side", "thetat", "topbottom"}
)


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Selected type plus every independently supported candidate."""

    file_type: FileType
    candidates: tuple[ClassificationCandidate, ...]
    ambiguous: bool


@dataclass(frozen=True, slots=True)
class _Signal:
    file_type: FileType
    confidence: float
    evidence: str


def _read_prefix(path: Path) -> bytes:
    try:
        with path.open("rb") as stream:
            return stream.read(_DETECTION_BYTES)
    except OSError:
        return b""


def _extension_signals(logical_path: str) -> list[_Signal]:
    suffix = PurePosixPath(logical_path).suffix.casefold()
    signals: list[_Signal] = []
    if suffix in _GERBER_SUFFIXES:
        signals.append(_Signal(FileType.GERBER, 0.75, f"extension:{suffix}"))
    if suffix in _DRILL_SUFFIXES:
        signals.append(_Signal(FileType.EXCELLON, 0.80, f"extension:{suffix}"))
    if suffix == ".csv":
        signals.extend(
            (
                _Signal(FileType.BOM_CSV, 0.30, "extension:.csv"),
                _Signal(FileType.PLACEMENT_CSV, 0.30, "extension:.csv"),
            )
        )
    if suffix == ".xlsx":
        signals.append(_Signal(FileType.BOM_XLSX, 0.55, "extension:.xlsx"))
    if suffix in {".yaml", ".yml"}:
        signals.append(_Signal(FileType.RULES_YAML, 0.55, f"extension:{suffix}"))
    if suffix == ".json":
        signals.append(_Signal(FileType.RULES_JSON, 0.55, "extension:.json"))
    return signals


def _filename_signals(logical_path: str) -> list[_Signal]:
    stem = PurePosixPath(logical_path).stem.casefold()
    tokens = set(filter(None, re.split(r"[^a-z0-9]+", stem)))
    signals: list[_Signal] = []
    if tokens & {"bom", "billofmaterials"} or "billofmaterials" in stem:
        file_type = (
            FileType.BOM_XLSX
            if PurePosixPath(logical_path).suffix.casefold() == ".xlsx"
            else FileType.BOM_CSV
        )
        signals.append(_Signal(file_type, 0.82, "filename:bom-token"))
    if tokens & {"centroid", "cpl", "placement", "pickplace", "pos"} or (
        "pickandplace" in stem
    ):
        signals.append(
            _Signal(FileType.PLACEMENT_CSV, 0.82, "filename:placement-token")
        )
    if tokens & {"drill", "drills", "excellon", "npth", "pth"}:
        signals.append(_Signal(FileType.EXCELLON, 0.72, "filename:drill-token"))
    return signals


def _gerber_signals(prefix: bytes) -> list[_Signal]:
    upper = prefix.upper()
    signals: list[_Signal] = []
    strong_syntax = (
        b"%FS" in upper
        and b"%MO" in upper
        and (b"D01*" in upper or b"D02*" in upper or b"%ADD" in upper)
    )
    if strong_syntax:
        signals.append(_Signal(FileType.GERBER, 0.99, "content:rs274x-command-set"))
    elif b"%FS" in upper and (b"D01*" in upper or b"D02*" in upper):
        signals.append(_Signal(FileType.GERBER, 0.88, "content:gerber-syntax"))
    file_function = _GERBER_FILE_FUNCTION.search(prefix)
    if file_function is not None:
        value = file_function.group(1).decode("ascii", errors="replace")
        signals.append(_Signal(FileType.GERBER, 0.99, f"x2:file-function:{value}"))
    same_coordinates = _GERBER_SAME_COORDINATES.search(prefix)
    if same_coordinates is not None:
        value = same_coordinates.group(1).decode("ascii", errors="replace")
        signals.append(_Signal(FileType.GERBER, 0.95, f"x2:same-coordinates:{value}"))
    return signals


def _excellon_signals(prefix: bytes) -> list[_Signal]:
    upper = prefix.upper()
    header = b"M48" in upper
    tool = _EXCELLON_TOOL.search(prefix) is not None
    coordinate = _EXCELLON_COORDINATE.search(prefix) is not None
    if header and tool and coordinate:
        return [_Signal(FileType.EXCELLON, 0.99, "content:excellon-command-set")]
    if tool and coordinate:
        return [_Signal(FileType.EXCELLON, 0.88, "content:drill-tool-coordinates")]
    return []


def _normalized_csv_headers(prefix: bytes) -> set[str]:
    try:
        text = prefix.decode("utf-8-sig")
    except UnicodeDecodeError:
        return set()
    try:
        sample = text[:64_000]
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        row = next(csv.reader(io.StringIO(sample), dialect=dialect), [])
    except (csv.Error, StopIteration):
        return set()
    return {
        _NORMALIZE_HEADER.sub("", value.strip().casefold())
        for value in row
        if value.strip()
    }


def _csv_signals(prefix: bytes) -> list[_Signal]:
    headers = _normalized_csv_headers(prefix)
    if not headers:
        return []
    has_reference = bool(headers & _REFERENCE_HEADERS)
    bom_matches = headers & _BOM_HEADERS
    has_xy = bool(headers & _X_HEADERS) and bool(headers & _Y_HEADERS)
    placement_matches = headers & _PLACEMENT_HEADERS
    signals: list[_Signal] = []
    if has_reference and bom_matches:
        evidence = ",".join(sorted(bom_matches))
        signals.append(_Signal(FileType.BOM_CSV, 0.92, f"csv:reference+{evidence}"))
    if has_reference and has_xy:
        evidence = ",".join(sorted(placement_matches)) or "xy"
        signals.append(
            _Signal(
                FileType.PLACEMENT_CSV,
                0.98,
                f"csv:reference+xy+{evidence}",
            )
        )
    return signals


def _xlsx_signals(path: Path) -> list[_Signal]:
    if path.suffix.casefold() != ".xlsx":
        return []
    try:
        with zipfile.ZipFile(path) as workbook:
            names: set[str] = set()
            for info in workbook.infolist():
                names.add(info.filename.casefold())
                if {"[content_types].xml", "xl/workbook.xml"} <= names:
                    break
    except (OSError, zipfile.BadZipFile):
        return []
    required = {"[content_types].xml", "xl/workbook.xml"}
    if required <= names:
        return [_Signal(FileType.BOM_XLSX, 0.62, "container:ooxml-workbook")]
    return []


def _rule_profile_signals(prefix: bytes, logical_path: str) -> list[_Signal]:
    try:
        text = prefix.decode("utf-8")
    except UnicodeDecodeError:
        return []
    required_markers = ("schema_version", "profile", "fabrication", "rules")
    if not all(marker in text for marker in required_markers):
        return []
    suffix = PurePosixPath(logical_path).suffix.casefold()
    if suffix == ".json" and text.lstrip().startswith("{"):
        return [_Signal(FileType.RULES_JSON, 0.93, "content:rule-profile-keys")]
    if suffix in {".yaml", ".yml"}:
        return [_Signal(FileType.RULES_YAML, 0.93, "content:rule-profile-keys")]
    return []


def _aggregate(signals: list[_Signal]) -> tuple[ClassificationCandidate, ...]:
    grouped: defaultdict[FileType, list[_Signal]] = defaultdict(list)
    for signal in signals:
        grouped[signal.file_type].append(signal)
    candidates = [
        ClassificationCandidate(
            file_type=file_type,
            confidence=max(signal.confidence for signal in type_signals),
            evidence=tuple(sorted({signal.evidence for signal in type_signals})),
        )
        for file_type, type_signals in grouped.items()
    ]
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (-candidate.confidence, candidate.file_type.value),
        )
    )


def classify_file(path: Path, logical_path: str) -> ClassificationResult:
    """Classify a staged file without allowing one signal to erase another."""
    prefix = _read_prefix(path)
    signals = _extension_signals(logical_path)
    signals.extend(_filename_signals(logical_path))
    signals.extend(_gerber_signals(prefix))
    signals.extend(_excellon_signals(prefix))
    signals.extend(_csv_signals(prefix))
    signals.extend(_xlsx_signals(path))
    signals.extend(_rule_profile_signals(prefix, logical_path))
    candidates = _aggregate(signals)
    strong_types = {
        candidate.file_type
        for candidate in candidates
        if candidate.confidence >= _STRONG_EVIDENCE
    }
    ambiguous = len(strong_types) > 1
    if not candidates:
        unknown = ClassificationCandidate(
            file_type=FileType.UNKNOWN,
            confidence=1.0,
            evidence=("content:no-supported-signature",),
        )
        return ClassificationResult(FileType.UNKNOWN, (unknown,), False)
    if ambiguous or candidates[0].confidence < _STRONG_EVIDENCE:
        return ClassificationResult(FileType.UNKNOWN, candidates, ambiguous)
    return ClassificationResult(candidates[0].file_type, candidates, False)
