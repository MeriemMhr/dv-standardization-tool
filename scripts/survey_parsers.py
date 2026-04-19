"""
survey_parsers.py

Parsers for Qualtrics, LimeSurvey, and REDCap native survey export formats.
Each parser converts platform-specific exports into the standardized wide-format
CSV that ``convert_dv.py`` expects: one row per participant, one column per
question/variable, with meaningful column names.

Part of the OpenDV-HCI project for promoting reproducibility and interoperability
in HCI research.

Usage:
    from scripts.survey_parsers import detect_and_parse, QualtricsParser

    df = detect_and_parse("path/to/export.csv")
    df = QualtricsParser().parse("path/to/qualtrics_export.csv")
"""

from __future__ import annotations

import csv
import io
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_file_bytes(file_path: Path, max_bytes: int = 65536) -> bytes:
    """Read up to *max_bytes* from the beginning of a file for sniffing."""
    with open(file_path, "rb") as fh:
        return fh.read(max_bytes)


def _detect_encoding(file_path: Path) -> str:
    """Best-effort encoding detection mirroring convert_dv.py behaviour."""
    raw = _read_file_bytes(file_path, max_bytes=32768)

    # BOM detection
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return "utf-16-be"

    try:
        import chardet  # type: ignore
        result = chardet.detect(raw)
        if result and result.get("confidence", 0) > 0.75:
            return result["encoding"] or "utf-8"
    except ImportError:
        pass

    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            raw.decode(enc)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"


def _detect_delimiter(sample: str, prefer: str | None = None) -> str:
    """Pick the most consistent delimiter from the first lines of *sample*."""
    candidates = [",", ";", "\t", "|"]
    if prefer:
        candidates = [prefer] + [c for c in candidates if c != prefer]

    rows = [r for r in sample.splitlines() if r.strip()][:15]
    if not rows:
        return prefer or ","

    best_delim = prefer or ","
    best_score = float("inf")

    for delim in candidates:
        counts = [row.count(delim) for row in rows]
        if max(counts) == 0:
            continue
        mean = sum(counts) / len(counts)
        if mean == 0:
            continue
        variance = sum((c - mean) ** 2 for c in counts) / len(counts)
        cv = (variance ** 0.5) / mean
        if cv < best_score:
            best_score = cv
            best_delim = delim

    return best_delim


def _slugify(text: str, max_len: int = 80) -> str:
    """Turn arbitrary text into a short, filesystem/column-safe slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:max_len] if slug else "unnamed"


def _ensure_unique_columns(columns: Sequence[str]) -> list[str]:
    """Deduplicate column names by appending ``_2``, ``_3``, etc."""
    seen: dict[str, int] = {}
    result: list[str] = []
    for col in columns:
        if col in seen:
            seen[col] += 1
            result.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 1
            result.append(col)
    return result


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class SurveyParser(ABC):
    """Base class for survey platform parsers.

    Subclasses must implement :meth:`parse` which reads a file exported by a
    survey platform and returns a clean :class:`pandas.DataFrame` in wide
    format (one row per participant, one column per variable).
    """

    @abstractmethod
    def parse(self, file_path: Union[str, Path], **kwargs: Any) -> pd.DataFrame:
        """Parse a survey export file.

        Parameters
        ----------
        file_path:
            Path to the exported file.
        **kwargs:
            Parser-specific options.

        Returns
        -------
        pd.DataFrame
            Wide-format DataFrame with one row per participant and
            descriptive column names.
        """
        ...


# ---------------------------------------------------------------------------
# Qualtrics
# ---------------------------------------------------------------------------

_QUALTRICS_META_COLUMNS: set[str] = {
    "StartDate", "EndDate", "Status", "IPAddress", "Progress",
    "Duration (in seconds)", "Finished", "RecordedDate",
    "ResponseId", "RecipientLastName", "RecipientFirstName",
    "RecipientEmail", "ExternalReference", "LocationLatitude",
    "LocationLongitude", "DistributionChannel", "UserLanguage",
}

# Pattern for Qualtrics import-ID header row (e.g. '{"ImportId":"QID1_TEXT"}')
_QUALTRICS_IMPORT_ID_RE = re.compile(r'\{"ImportId"\s*:', re.IGNORECASE)


class QualtricsParser(SurveyParser):
    """Parse Qualtrics CSV exports.

    Qualtrics CSVs have **three header rows**:

    1. Variable names  (``Q1``, ``Q2_1``, embedded data names, ...)
    2. Question / description text
    3. Import IDs      (``{"ImportId":"QID1_TEXT"}``)

    Actual response data starts at row 4.  This parser strips the two
    metadata rows and renames columns to their human-readable descriptions
    where possible.
    """

    def parse(
        self,
        file_path: Union[str, Path],
        *,
        use_descriptions: bool = True,
        keep_metadata: bool = True,
        rename_strategy: str = "description",
    ) -> pd.DataFrame:
        """Parse a Qualtrics CSV export.

        Parameters
        ----------
        file_path:
            Path to the Qualtrics ``.csv`` file.
        use_descriptions:
            If ``True`` (default), rename columns from their Qualtrics
            variable names (``Q1``) to the description text from header
            row 2.  When ``False``, keep Qualtrics variable names as-is.
        keep_metadata:
            If ``True`` (default), retain Qualtrics metadata columns
            (Progress, Duration, Finished, etc.).  Set to ``False`` to
            drop them.
        rename_strategy:
            ``"description"`` -- use the description row text (default).
            ``"slug"`` -- slugify the description row text.
            ``"variable"`` -- keep original Qualtrics variable names.

        Returns
        -------
        pd.DataFrame
        """
        file_path = Path(file_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Qualtrics export not found: {file_path}")

        encoding = _detect_encoding(file_path)
        logger.info("Parsing Qualtrics export: %s (encoding=%s)", file_path, encoding)

        # Read the full file so we can inspect the first three rows.
        raw_text = file_path.read_text(encoding=encoding, errors="replace")
        delimiter = _detect_delimiter(raw_text[:16384])

        reader = csv.reader(io.StringIO(raw_text), delimiter=delimiter)
        rows = list(reader)

        if len(rows) < 3:
            raise ValueError(
                f"Qualtrics CSV must have at least 3 header rows; got {len(rows)} total rows."
            )

        variable_names: list[str] = rows[0]
        descriptions: list[str] = rows[1]
        import_ids: list[str] = rows[2]

        # Validate that row 3 looks like Qualtrics import IDs.
        import_id_matches = sum(
            1 for cell in import_ids if _QUALTRICS_IMPORT_ID_RE.search(cell)
        )
        if import_id_matches == 0:
            logger.warning(
                "Row 3 does not contain recognisable Qualtrics import IDs. "
                "The file may not be a standard Qualtrics 3-header export; "
                "proceeding with best-effort parsing."
            )

        # Build data from row 4 onward.
        data_rows = rows[3:]
        if not data_rows:
            logger.warning("Qualtrics file contains header rows but no response data.")
            return pd.DataFrame(columns=variable_names)

        df = pd.DataFrame(data_rows, columns=variable_names)

        # ------------------------------------------------------------------
        # Column renaming
        # ------------------------------------------------------------------
        if use_descriptions and rename_strategy != "variable":
            col_map = self._build_column_map(
                variable_names, descriptions, rename_strategy
            )
            df.rename(columns=col_map, inplace=True)
            df.columns = pd.Index(_ensure_unique_columns(list(df.columns)))

        # ------------------------------------------------------------------
        # Drop metadata columns if requested
        # ------------------------------------------------------------------
        if not keep_metadata:
            to_drop = [
                c for c in df.columns
                if c in _QUALTRICS_META_COLUMNS
                or _slugify(c) in {_slugify(m) for m in _QUALTRICS_META_COLUMNS}
            ]
            df.drop(columns=to_drop, inplace=True, errors="ignore")

        # ------------------------------------------------------------------
        # Type coercion: try numeric conversion on every column
        # ------------------------------------------------------------------
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(df[col])

        logger.info(
            "Qualtrics parse complete: %d participants, %d columns.",
            len(df), len(df.columns),
        )
        return df

    # ---- internal helpers ------------------------------------------------

    @staticmethod
    def _build_column_map(
        variable_names: list[str],
        descriptions: list[str],
        strategy: str,
    ) -> dict[str, str]:
        """Map Qualtrics variable names to readable column names."""
        col_map: dict[str, str] = {}
        for var, desc in zip(variable_names, descriptions):
            if not desc or desc == var:
                # No useful description -- keep original variable name.
                continue
            if strategy == "slug":
                col_map[var] = _slugify(desc)
            else:
                # "description" strategy
                col_map[var] = desc.strip()
        return col_map


# ---------------------------------------------------------------------------
# LimeSurvey
# ---------------------------------------------------------------------------

# LimeSurvey SGQA pattern: surveyId X groupId X questionId X answerCode
# e.g.  123456X7X8, 123456X7X8SQ001, 123456X7X8A1
_SGQA_RE = re.compile(
    r"^(?P<sid>\d+)X(?P<gid>\d+)X(?P<qid>\d+)(?P<sq>[A-Z0-9_]*)$"
)


class LimeSurveyParser(SurveyParser):
    """Parse LimeSurvey CSV or XLSX exports.

    LimeSurvey uses **SGQA** column identifiers
    (``{SurveyID}X{GroupID}X{QuestionID}[AnswerCode]``).  These are
    machine-readable but uninformative to humans.  When a *structure_file*
    is supplied (the LimeSurvey ``.lss`` XML or a simple YAML/JSON
    mapping), the parser replaces SGQA codes with descriptive question
    text.

    Multi-choice responses separated by semicolons are expanded into
    individual boolean columns (one per option).
    """

    def parse(
        self,
        file_path: Union[str, Path],
        *,
        structure_file: Optional[Union[str, Path]] = None,
        expand_multichoice: bool = True,
        delimiter_hint: Optional[str] = None,
    ) -> pd.DataFrame:
        """Parse a LimeSurvey export.

        Parameters
        ----------
        file_path:
            Path to the exported ``.csv`` or ``.xlsx`` file.
        structure_file:
            Optional path to a LimeSurvey structure file (``.lss`` XML
            export or a YAML/JSON mapping of SGQA codes to question
            text).  When provided, SGQA columns are renamed.
        expand_multichoice:
            If ``True`` (default), columns containing semicolon-separated
            answer codes are exploded into individual boolean columns.
        delimiter_hint:
            Force a specific CSV delimiter instead of auto-detection.
            Common for LimeSurvey: ``";"`` (default in many locales).

        Returns
        -------
        pd.DataFrame
        """
        file_path = Path(file_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"LimeSurvey export not found: {file_path}")

        logger.info("Parsing LimeSurvey export: %s", file_path)

        # ------------------------------------------------------------------
        # Load raw data
        # ------------------------------------------------------------------
        suffix = file_path.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        else:
            encoding = _detect_encoding(file_path)
            sample = file_path.read_text(encoding=encoding, errors="replace")[:16384]
            delimiter = delimiter_hint or _detect_delimiter(sample, prefer=";")
            df = pd.read_csv(file_path, sep=delimiter, encoding=encoding, engine="python")

        # ------------------------------------------------------------------
        # SGQA -> question text renaming
        # ------------------------------------------------------------------
        sgqa_map: dict[str, str] = {}
        if structure_file is not None:
            sgqa_map = self._load_structure_map(Path(structure_file))

        col_map: dict[str, str] = {}
        for col in df.columns:
            readable = sgqa_map.get(col)
            if readable:
                col_map[col] = readable
            elif _SGQA_RE.match(col):
                # No mapping available -- produce a shorter code.
                col_map[col] = self._shorten_sgqa(col)

        if col_map:
            df.rename(columns=col_map, inplace=True)
            df.columns = pd.Index(_ensure_unique_columns(list(df.columns)))
            logger.info("Renamed %d SGQA columns.", len(col_map))

        # ------------------------------------------------------------------
        # Expand semicolon-separated multi-choice fields
        # ------------------------------------------------------------------
        if expand_multichoice:
            df = self._expand_multichoice_columns(df)

        # Type coercion
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(df[col])

        logger.info(
            "LimeSurvey parse complete: %d participants, %d columns.",
            len(df), len(df.columns),
        )
        return df

    # ---- internal helpers ------------------------------------------------

    @staticmethod
    def _load_structure_map(structure_path: Path) -> dict[str, str]:
        """Load a mapping from SGQA codes to descriptive question text.

        Supports:
        - ``.yaml`` / ``.yml``:  flat ``{sgqa_code: question_text}`` mapping.
        - ``.json``:  same structure.
        - ``.lss`` (XML):  LimeSurvey survey structure export; the parser
          extracts ``<question>`` elements and their SGQA identifiers.

        Returns an empty dict if parsing fails so that the pipeline
        degrades gracefully.
        """
        if not structure_path.is_file():
            logger.warning("Structure file not found: %s", structure_path)
            return {}

        suffix = structure_path.suffix.lower()

        try:
            if suffix in (".yaml", ".yml"):
                import yaml
                data = yaml.safe_load(structure_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}

            elif suffix == ".json":
                import json
                data = json.loads(structure_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}

            elif suffix == ".lss":
                return LimeSurveyParser._parse_lss_xml(structure_path)

        except Exception as exc:
            logger.warning(
                "Failed to load LimeSurvey structure file '%s': %s",
                structure_path, exc,
            )

        return {}

    @staticmethod
    def _parse_lss_xml(lss_path: Path) -> dict[str, str]:
        """Extract SGQA-to-question-text mapping from a .lss XML export.

        The ``.lss`` format stores questions in ``<rows><row>`` elements
        inside the ``<questions>`` and ``<groups>`` tables.  We build the
        SGQA code from the ``sid``, ``gid``, and ``qid`` fields and pair
        it with the question text from the matching ``<question_l10ns>``
        section.
        """
        import xml.etree.ElementTree as ET

        tree = ET.parse(lss_path)
        root = tree.getroot()

        # Collect question texts: qid -> question_text
        qid_texts: dict[str, str] = {}
        for table in root.iter("rows"):
            parent = table.find("..")
            if parent is not None and parent.tag == "question_l10ns":
                for row in table.findall("row"):
                    qid_el = row.find("qid")
                    question_el = row.find("question")
                    if qid_el is not None and question_el is not None:
                        text = (question_el.text or "").strip()
                        if text:
                            qid_texts[qid_el.text or ""] = text

        # Collect questions: build SGQA -> qid mapping
        sgqa_map: dict[str, str] = {}
        for table in root.iter("rows"):
            parent = table.find("..")
            if parent is not None and parent.tag == "questions":
                for row in table.findall("row"):
                    sid_el = row.find("sid")
                    gid_el = row.find("gid")
                    qid_el = row.find("qid")
                    if sid_el is None or gid_el is None or qid_el is None:
                        continue
                    sid = sid_el.text or ""
                    gid = gid_el.text or ""
                    qid = qid_el.text or ""
                    sgqa = f"{sid}X{gid}X{qid}"
                    text = qid_texts.get(qid, "")
                    if text:
                        sgqa_map[sgqa] = _slugify(text)

        return sgqa_map

    @staticmethod
    def _shorten_sgqa(code: str) -> str:
        """Produce a shorter but still unique column name from a SGQA code."""
        m = _SGQA_RE.match(code)
        if not m:
            return code
        short = f"q{m.group('qid')}"
        sq = m.group("sq")
        if sq:
            short += f"_{sq}"
        return short

    @staticmethod
    def _expand_multichoice_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Expand columns containing semicolon-separated answers.

        For each column whose values frequently contain ``";"``, the
        column is replaced by a set of boolean indicator columns (one per
        unique answer option across all respondents).
        """
        cols_to_expand: list[str] = []
        for col in df.columns:
            if df[col].dtype != object:
                continue
            non_null = df[col].dropna().astype(str)
            if len(non_null) == 0:
                continue
            semicolon_ratio = non_null.str.contains(";", regex=False).mean()
            if semicolon_ratio > 0.15:
                cols_to_expand.append(col)

        if not cols_to_expand:
            return df

        logger.info(
            "Expanding %d multi-choice columns: %s",
            len(cols_to_expand),
            ", ".join(cols_to_expand[:5]),
        )

        for col in cols_to_expand:
            dummies = (
                df[col]
                .astype(str)
                .str.get_dummies(sep=";")
            )
            dummies.columns = pd.Index([f"{col}__{opt.strip()}" for opt in dummies.columns])
            df = pd.concat([df.drop(columns=[col]), dummies], axis=1)

        return df


# ---------------------------------------------------------------------------
# REDCap
# ---------------------------------------------------------------------------

# REDCap checkbox field pattern: fieldname___code  (triple underscore)
_REDCAP_CHECKBOX_RE = re.compile(r"^(?P<field>.+?)___(?P<code>\w+)$")


class REDCapParser(SurveyParser):
    """Parse REDCap CSV exports.

    REDCap exports use **instrument-prefixed** field names (e.g.
    ``demographics_age``, ``nasa_tlx_mental_demand``) and a special
    triple-underscore convention for checkbox fields
    (``field___1``, ``field___2``).

    Both **raw** and **label** exports are supported.  In raw exports
    numeric codes are kept; in label exports the human-readable labels
    are retained.
    """

    def parse(
        self,
        file_path: Union[str, Path],
        *,
        data_dictionary: Optional[Union[str, Path]] = None,
        collapse_checkboxes: bool = True,
        strip_instrument_prefix: bool = False,
    ) -> pd.DataFrame:
        """Parse a REDCap CSV export.

        Parameters
        ----------
        file_path:
            Path to the REDCap ``.csv`` export.
        data_dictionary:
            Optional path to a REDCap data dictionary CSV.  When
            provided, field names are enriched with the *Field Label*
            column for readability.
        collapse_checkboxes:
            If ``True`` (default), checkbox field groups
            (``field___1``, ``field___2``, ...) are collapsed into a
            single semicolon-separated column named after the base
            field.
        strip_instrument_prefix:
            If ``True``, remove the instrument prefix from field names
            (everything before the first underscore) when it matches a
            known instrument name from the data dictionary.

        Returns
        -------
        pd.DataFrame
        """
        file_path = Path(file_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"REDCap export not found: {file_path}")

        logger.info("Parsing REDCap export: %s", file_path)

        encoding = _detect_encoding(file_path)
        df = pd.read_csv(file_path, encoding=encoding, engine="python")

        # ------------------------------------------------------------------
        # Load optional data dictionary for label enrichment
        # ------------------------------------------------------------------
        field_labels: dict[str, str] = {}
        instrument_names: set[str] = set()
        if data_dictionary is not None:
            field_labels, instrument_names = self._load_data_dictionary(
                Path(data_dictionary)
            )

        # ------------------------------------------------------------------
        # Collapse checkbox fields
        # ------------------------------------------------------------------
        if collapse_checkboxes:
            df = self._collapse_checkbox_fields(df, field_labels)

        # ------------------------------------------------------------------
        # Rename columns from data dictionary labels
        # ------------------------------------------------------------------
        if field_labels:
            col_map = self._build_label_map(df.columns, field_labels)
            if col_map:
                df.rename(columns=col_map, inplace=True)
                df.columns = pd.Index(_ensure_unique_columns(list(df.columns)))
                logger.info("Renamed %d columns from data dictionary.", len(col_map))

        # ------------------------------------------------------------------
        # Strip instrument prefix
        # ------------------------------------------------------------------
        if strip_instrument_prefix and instrument_names:
            df = self._strip_instrument_prefixes(df, instrument_names)

        # Type coercion
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(df[col])

        logger.info(
            "REDCap parse complete: %d participants, %d columns.",
            len(df), len(df.columns),
        )
        return df

    # ---- internal helpers ------------------------------------------------

    @staticmethod
    def _load_data_dictionary(
        dd_path: Path,
    ) -> tuple[dict[str, str], set[str]]:
        """Load a REDCap data dictionary CSV.

        Returns
        -------
        (field_labels, instrument_names)
            *field_labels* maps ``Variable / Field Name`` to
            ``Field Label``.  *instrument_names* is the set of unique
            ``Form Name`` values.
        """
        if not dd_path.is_file():
            logger.warning("Data dictionary not found: %s", dd_path)
            return {}, set()

        try:
            dd = pd.read_csv(dd_path, encoding="utf-8-sig")
        except Exception as exc:
            logger.warning("Failed to read data dictionary '%s': %s", dd_path, exc)
            return {}, set()

        # REDCap data dictionaries use these column names (with slight
        # variations depending on export language).
        field_col = None
        label_col = None
        form_col = None
        for c in dd.columns:
            cl = c.strip().lower()
            if cl in ("variable / field name", "variable_field_name", "field_name"):
                field_col = c
            elif cl in ("field label", "field_label"):
                label_col = c
            elif cl in ("form name", "form_name", "instrument"):
                form_col = c

        if field_col is None or label_col is None:
            logger.warning(
                "Data dictionary does not contain expected columns "
                "('Variable / Field Name', 'Field Label'). Found: %s",
                list(dd.columns),
            )
            return {}, set()

        field_labels: dict[str, str] = {}
        for _, row in dd.iterrows():
            fname = str(row[field_col]).strip()
            flabel = str(row[label_col]).strip()
            if fname and flabel and flabel != "nan":
                field_labels[fname] = flabel

        instrument_names: set[str] = set()
        if form_col is not None:
            instrument_names = {
                str(v).strip().lower()
                for v in dd[form_col].dropna().unique()
                if str(v).strip()
            }

        return field_labels, instrument_names

    @staticmethod
    def _collapse_checkbox_fields(
        df: pd.DataFrame,
        field_labels: dict[str, str],
    ) -> pd.DataFrame:
        """Collapse ``field___code`` checkbox columns into a single column.

        Each group of checkbox columns sharing the same base field name
        is merged into one column whose value is a semicolon-separated
        list of checked codes (for raw exports) or labels (for label
        exports).
        """
        checkbox_groups: dict[str, list[tuple[str, str]]] = {}
        non_checkbox_cols: list[str] = []

        for col in df.columns:
            m = _REDCAP_CHECKBOX_RE.match(col)
            if m:
                base = m.group("field")
                code = m.group("code")
                checkbox_groups.setdefault(base, []).append((col, code))
            else:
                non_checkbox_cols.append(col)

        if not checkbox_groups:
            return df

        logger.info("Collapsing %d checkbox field groups.", len(checkbox_groups))

        result = df[non_checkbox_cols].copy()

        for base_field, members in checkbox_groups.items():
            members.sort(key=lambda t: t[1])

            def _row_to_checked(row: pd.Series) -> str:
                checked: list[str] = []
                for col_name, code in members:
                    val = row.get(col_name)
                    if pd.isna(val):
                        continue
                    # Raw export: 1 = checked, 0 = unchecked
                    # Label export: value is the label text if checked,
                    # "Unchecked" or empty if not.
                    str_val = str(val).strip()
                    if str_val in ("1", "Checked"):
                        checked.append(code)
                    elif str_val not in ("0", "", "Unchecked", "nan"):
                        # Label export with the actual label text
                        checked.append(str_val)
                return ";".join(checked)

            result[base_field] = df.apply(_row_to_checked, axis=1)

        return result

    @staticmethod
    def _build_label_map(
        columns: pd.Index,
        field_labels: dict[str, str],
    ) -> dict[str, str]:
        """Build rename map from REDCap field names to data-dictionary labels."""
        col_map: dict[str, str] = {}
        for col in columns:
            label = field_labels.get(col)
            if label and label != col:
                col_map[col] = label
        return col_map

    @staticmethod
    def _strip_instrument_prefixes(
        df: pd.DataFrame,
        instrument_names: set[str],
    ) -> pd.DataFrame:
        """Remove leading instrument prefix from columns when it matches."""
        col_map: dict[str, str] = {}
        for col in df.columns:
            parts = col.split("_", 1)
            if len(parts) == 2 and parts[0].lower() in instrument_names:
                col_map[col] = parts[1]

        if col_map:
            df = df.rename(columns=col_map)
            df.columns = pd.Index(_ensure_unique_columns(list(df.columns)))

        return df


# ---------------------------------------------------------------------------
# Format auto-detection and factory
# ---------------------------------------------------------------------------

def _sniff_qualtrics(file_path: Path) -> bool:
    """Heuristic: does the file look like a Qualtrics 3-header CSV?"""
    try:
        encoding = _detect_encoding(file_path)
        sample = file_path.read_text(encoding=encoding, errors="replace")[:32768]
    except OSError:
        return False

    delimiter = _detect_delimiter(sample)
    reader = csv.reader(io.StringIO(sample), delimiter=delimiter)
    rows: list[list[str]] = []
    for row in reader:
        rows.append(row)
        if len(rows) >= 4:
            break

    if len(rows) < 3:
        return False

    # Row 3 (index 2) should contain Qualtrics import-ID JSON.
    import_id_hits = sum(
        1 for cell in rows[2] if _QUALTRICS_IMPORT_ID_RE.search(cell)
    )
    return import_id_hits >= max(1, len(rows[2]) // 3)


def _sniff_redcap(file_path: Path) -> bool:
    """Heuristic: does the file look like a REDCap CSV export?"""
    try:
        encoding = _detect_encoding(file_path)
        sample = file_path.read_text(encoding=encoding, errors="replace")[:8192]
    except OSError:
        return False

    delimiter = _detect_delimiter(sample)
    reader = csv.reader(io.StringIO(sample), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        return False

    # REDCap marker: ``record_id`` is almost always the first column, and
    # checkbox fields use the triple-underscore convention.
    has_record_id = any(
        c.strip().lower() in ("record_id", "study_id", "participant_id")
        for c in header
    )
    checkbox_count = sum(1 for c in header if _REDCAP_CHECKBOX_RE.match(c))

    # Strong signal: record_id + at least one checkbox field.
    if has_record_id and checkbox_count > 0:
        return True

    # Moderate signal: record_id + instrument-prefixed fields with
    # consistent underscored naming.
    if has_record_id:
        underscore_ratio = sum(1 for c in header if "_" in c) / max(len(header), 1)
        if underscore_ratio > 0.5:
            return True

    return False


def _sniff_limesurvey(file_path: Path) -> bool:
    """Heuristic: does the file look like a LimeSurvey export?"""
    try:
        encoding = _detect_encoding(file_path)
        sample = file_path.read_text(encoding=encoding, errors="replace")[:8192]
    except OSError:
        return False

    delimiter = _detect_delimiter(sample, prefer=";")
    reader = csv.reader(io.StringIO(sample), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        return False

    sgqa_count = sum(1 for c in header if _SGQA_RE.match(c.strip()))
    # LimeSurvey exports typically have many SGQA columns.
    return sgqa_count >= max(1, len(header) // 4)


def detect_and_parse(
    file_path: Union[str, Path],
    *,
    format_hint: Optional[str] = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Auto-detect the survey platform format and parse the file.

    Parameters
    ----------
    file_path:
        Path to the exported file.
    format_hint:
        Optional hint to skip auto-detection.  Accepted values:
        ``"qualtrics"``, ``"limesurvey"``, ``"redcap"``.
    **kwargs:
        Additional keyword arguments forwarded to the detected parser's
        :meth:`parse` method.

    Returns
    -------
    pd.DataFrame
        Wide-format DataFrame ready for ``convert_dv.py``.

    Raises
    ------
    ValueError
        If the format cannot be determined.
    """
    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Survey export file not found: {file_path}")

    # ------------------------------------------------------------------
    # Explicit hint
    # ------------------------------------------------------------------
    hint = (format_hint or "").strip().lower()
    _PARSERS: dict[str, SurveyParser] = {
        "qualtrics": QualtricsParser(),
        "limesurvey": LimeSurveyParser(),
        "lime": LimeSurveyParser(),
        "redcap": REDCapParser(),
    }
    if hint and hint in _PARSERS:
        logger.info("Using format hint: %s", hint)
        return _PARSERS[hint].parse(file_path, **kwargs)

    # ------------------------------------------------------------------
    # Auto-detection cascade
    # ------------------------------------------------------------------
    logger.info("Auto-detecting survey format for: %s", file_path)

    # Qualtrics is checked first because its 3-header structure is the
    # most distinctive fingerprint.
    if _sniff_qualtrics(file_path):
        logger.info("Detected Qualtrics format.")
        return QualtricsParser().parse(file_path, **kwargs)

    if _sniff_redcap(file_path):
        logger.info("Detected REDCap format.")
        return REDCapParser().parse(file_path, **kwargs)

    if _sniff_limesurvey(file_path):
        logger.info("Detected LimeSurvey format.")
        return LimeSurveyParser().parse(file_path, **kwargs)

    raise ValueError(
        f"Could not auto-detect survey format for '{file_path}'. "
        "Please provide a format_hint ('qualtrics', 'limesurvey', or 'redcap')."
    )
