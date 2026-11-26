"""Data contracts for GROUNDED NO MORE.

Single source of truth for table schemas, enums, keys and provenance tags.
Every table written to ``data/processed`` (Parquet + DuckDB) must validate
against :data:`TABLES` via :func:`validate_table`.

Conventions
-----------
* Time: integer ``*_h`` columns are hours since the simulated epoch
  (``config/assumptions.yaml: calendar.epoch``, UTC). ``week`` = h // 168.
* Money: AED, float64, columns end in ``_aed``.
* Quantities: int64, never negative (except signed ``qty_delta``).
* Every table has a ``provenance`` column or a table-level provenance tag.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

import pandas as pd


class Provenance(str, Enum):
    REAL = "REAL"
    DERIVED = "DERIVED"
    ASSUMED = "ASSUMED"
    SIMULATED = "SIMULATED"


class PartClass(str, Enum):
    CONSUMABLE = "C"
    EXPENDABLE = "E"
    ROTABLE = "R"


class DeadlineClass(str, Enum):
    """Hypothetical requirement deadline classes. NOT MEL categories."""
    D0 = "D0"    # needed before next departure -> aircraft grounded until fitted
    D3 = "D3"    # ~72 h deferral window
    D10 = "D10"  # ~10 day deferral window
    NONE = "NONE"  # (v2) servicing fluids: no deadline class, never an AOG driver (line usage only)


DEADLINE_HOURS = {"D0": 0, "D3": 72, "D10": 240, "NONE": None}   # NONE = no rectification window
DEADLINE_VALUES = ("D0", "D3", "D10", "NONE")


class SerialState(str, Enum):
    SERVICEABLE = "SERVICEABLE"   # in stores, ready to issue (at a station)
    INSTALLED = "INSTALLED"       # fitted on an aircraft
    REMOVED = "REMOVED"           # unserviceable, awaiting / in transit to shop
    IN_REPAIR = "IN_REPAIR"       # at a repair shop (queue or work)
    IN_TRANSIT = "IN_TRANSIT"     # serviceable unit moving between stations
    CONDEMNED = "CONDEMNED"       # beyond economic repair; terminal state
    RETURNED_TO_LENDER = "RETURNED_TO_LENDER"   # (v2) non-owned exchange/loan/borrow unit handed back; terminal


class Archetype(str, Enum):
    NARROWBODY = "narrowbody"
    WIDEBODY = "widebody"


class DemandClass(str, Enum):
    """Syntetos–Boylan classification (ADI 1.32, CV² 0.49)."""
    SMOOTH = "smooth"
    ERRATIC = "erratic"
    INTERMITTENT = "intermittent"
    LUMPY = "lumpy"
    INSUFFICIENT = "insufficient_data"


class RequestSource(str, Enum):
    UNSCHEDULED = "unscheduled_removal"
    SCHEDULED_KIT = "scheduled_kit"
    LINE_USAGE = "line_usage"
    PLANNED_REMOVAL = "planned_removal"   # (v2) wear-planned rotable change known ahead (brakes)


class TxnType(str, Enum):
    RECEIPT_PO = "RECEIPT_PO"
    RECEIPT_REPAIR = "RECEIPT_REPAIR"
    ISSUE = "ISSUE"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"
    CONDEMN = "CONDEMN"
    EXPIRE = "EXPIRE"
    UNSERVICEABLE_IN = "UNSERVICEABLE_IN"   # removed rotable booked into U/S stores
    INITIAL = "INITIAL"


PROVENANCE_VALUES = [p.value for p in Provenance]


@dataclass(frozen=True)
class Col:
    name: str
    dtype: str            # pandas dtype family: int64 | float64 | string | bool | category
    desc: str
    unit: str = ""
    nullable: bool = False
    nonneg: bool = False
    allowed: tuple = ()


@dataclass(frozen=True)
class Table:
    name: str
    desc: str
    provenance: Provenance
    cols: tuple
    pk: tuple
    fks: tuple = ()          # (col, other_table, other_col)
    hidden: bool = False     # True -> ground truth; lives in data/ground_truth only

    @property
    def colnames(self) -> list[str]:
        return [c.name for c in self.cols]


def _t(name, desc, prov, cols, pk, fks=(), hidden=False) -> Table:
    return Table(name, desc, prov, tuple(cols), tuple(pk), tuple(fks), hidden)


STATIONS = ["AUH", "LHR", "FRA", "CAI", "JED", "BOM", "SIN"]
ATA = ["20", "21", "24", "27", "28", "29", "30", "32", "33", "34", "35", "36", "38", "49"]

TABLES: dict[str, Table] = {}


def _reg(t: Table) -> Table:
    TABLES[t.name] = t
    return t


_reg(_t("aircraft_master", "Fictional fleet of Falcon Hub Airways (fictional).", Provenance.SIMULATED, [
    Col("tail", "string", "Fictional registration, e.g. A6-FHA"),
    Col("archetype", "string", "narrowbody | widebody", allowed=("narrowbody", "widebody")),
    Col("type_label", "string", "Generic archetype label"),
    Col("entry_week", "int64", "First week in service", "week", nonneg=True),
    Col("fh_per_day_mean", "float64", "Planned mean flight hours/day", "FH/day", nonneg=True),
    Col("fc_per_day_mean", "float64", "Planned mean flight cycles/day", "FC/day", nonneg=True),
], pk=["tail"]))

_reg(_t("station_master", "Hub + outstations. Coordinates REAL (OurAirports).", Provenance.REAL, [
    Col("station", "string", "IATA code", allowed=tuple(STATIONS)),
    Col("name", "string", "Airport name"),
    Col("lat", "float64", "Latitude (WGS84)", "deg"),
    Col("lon", "float64", "Longitude (WGS84)", "deg"),
    Col("role", "string", "hub | outstation", allowed=("hub", "outstation")),
], pk=["station"]))

_reg(_t("part_master", "120 fictional part numbers. Public attributes only (no true failure rates).", Provenance.SIMULATED, [
    Col("pn", "string", "Fictional PN GN-<ATA>-<C|E|R><nnn>"),
    Col("description", "string", "Fictional nomenclature"),
    Col("ata", "string", "ATA chapter (2-digit)", allowed=tuple(ATA)),
    Col("part_class", "string", "C consumable | E expendable | R rotable", allowed=("C", "E", "R")),
    Col("deadline_class", "string", "Hypothetical rectification-window class (NONE = servicing fluid)",
        allowed=("D0", "D3", "D10", "NONE")),
    Col("unit_cost_aed", "float64", "Unit cost (new)", "AED", nonneg=True),
    Col("lead_time_mean_d", "float64", "Quoted purchase lead time mean", "days", nonneg=True),
    Col("lead_time_cv", "float64", "Quoted lead time coefficient of variation", nonneg=True),
    Col("driver", "string", "Exposure driver for removals: FH | FC | FC_usage | none", allowed=("FH", "FC", "FC_usage", "none")),
    Col("mtbur_quoted", "float64", "Vendor-quoted MTBUR (deviates from truth)", "FH or FC", nullable=True, nonneg=True),
    Col("repair_shop", "string", "Repair shop id (rotables)", nullable=True),
    Col("repair_tat_mean_d", "float64", "Quoted shop TAT mean (rotables)", "days", nullable=True, nonneg=True),
    Col("repair_cost_aed", "float64", "Repair cost per shop visit", "AED", nullable=True, nonneg=True),
    Col("condemnation_prob_quoted", "float64", "Historical condemnation rate quoted", nullable=True, nonneg=True),
    Col("shelf_life_months", "float64", "Shelf life if limited", "months", nullable=True, nonneg=True),
    Col("planted", "string", "Planted demo situation id (PS1..PS4) or empty", nullable=True),
    Col("removal_mode", "string", "unscheduled | wear_planned (v2: brakes, known ahead)", allowed=("unscheduled", "wear_planned")),
], pk=["pn"]))

_reg(_t("part_applicability", "Which archetype uses which PN and installed qty per aircraft.", Provenance.SIMULATED, [
    Col("pn", "string", "Part number"),
    Col("archetype", "string", "narrowbody | widebody", allowed=("narrowbody", "widebody")),
    Col("qty_per_aircraft", "int64", "Installed quantity per aircraft (0 for consumables usage-driven)", nonneg=True),
], pk=["pn", "archetype"], fks=[("pn", "part_master", "pn")]))

_reg(_t("flight_exposure", "Synthetic flight legs (exposure). One row per leg.", Provenance.SIMULATED, [
    Col("leg_id", "int64", "Leg id", nonneg=True),
    Col("tail", "string", "Aircraft"),
    Col("dep_station", "string", "Departure station", allowed=tuple(STATIONS)),
    Col("arr_station", "string", "Arrival station", allowed=tuple(STATIONS)),
    Col("dep_h", "int64", "Departure time", "h since epoch", nonneg=True),
    Col("arr_h", "int64", "Arrival time", "h since epoch", nonneg=True),
    Col("fh", "float64", "Flight hours", "FH", nonneg=True),
    Col("fc", "int64", "Flight cycles (1)", "FC", nonneg=True),
    Col("week", "int64", "Week of departure", "week", nonneg=True),
], pk=["leg_id"], fks=[("tail", "aircraft_master", "tail")]))

_reg(_t("maintenance_schedule", "Scheduled checks with kit requirements known in advance.", Provenance.SIMULATED, [
    Col("task_id", "int64", "Scheduled task id", nonneg=True),
    Col("tail", "string", "Aircraft"),
    Col("check_type", "string", "e.g. A-check"),
    Col("station", "string", "Where performed", allowed=tuple(STATIONS)),
    Col("due_h", "int64", "Planned start", "h", nonneg=True),
    Col("notice_h", "int64", "When kit requirement becomes known", "h", nonneg=True),
    Col("pn", "string", "Kit line part number"),
    Col("qty", "int64", "Kit line quantity", nonneg=True),
], pk=["task_id", "pn"], fks=[("tail", "aircraft_master", "tail"), ("pn", "part_master", "pn")]))

_reg(_t("removal_events", "Unscheduled removals (rotables/expendables) — exogenous demand.", Provenance.SIMULATED, [
    Col("removal_id", "int64", "Removal id", nonneg=True),
    Col("tail", "string", "Aircraft"),
    Col("pn", "string", "Part number"),
    Col("station", "string", "Station where removed / required", allowed=tuple(STATIONS)),
    Col("removal_h", "int64", "Time of removal (need time)", "h", nonneg=True),
    Col("deadline_class", "string", "Deadline class of this requirement", allowed=("D0", "D3", "D10")),
    Col("week", "int64", "Week", "week", nonneg=True),
], pk=["removal_id"], fks=[("tail", "aircraft_master", "tail"), ("pn", "part_master", "pn")]))

_reg(_t("material_requests", "All material demand (unscheduled, kit, line usage). Unconstrained demand.", Provenance.SIMULATED, [
    Col("request_id", "int64", "Request id", nonneg=True),
    Col("pn", "string", "Part number"),
    Col("station", "string", "Requesting station", allowed=tuple(STATIONS)),
    Col("tail", "string", "Aircraft", nullable=True),
    Col("need_h", "int64", "Need time", "h", nonneg=True),
    Col("known_h", "int64", "Time requirement became known (== need_h for unscheduled)", "h", nonneg=True),
    Col("qty", "int64", "Quantity", nonneg=True),
    Col("source", "string", "unscheduled_removal | planned_removal | scheduled_kit | line_usage",
        allowed=("unscheduled_removal", "planned_removal", "scheduled_kit", "line_usage")),
    Col("deadline_class", "string", "Deadline class", allowed=("D0", "D3", "D10", "NONE")),
    Col("removal_id", "int64", "Linked removal (unscheduled)", nullable=True),
    Col("week", "int64", "Week of need", "week", nonneg=True),
    # policy-run outcome columns (filled by engine; null in pure scenario tables)
    Col("filled_h", "int64", "Time fitted/issued", "h", nullable=True),
    Col("fill_source", "string", "local | transfer | lateral | purchase | repair | pool | exchange_loan | local_borrow | robbery | local_buy | loan_or_donor_return", nullable=True),
    Col("immediate_fill", "bool", "Filled from local serviceable stock at need time", nullable=True),
], pk=["request_id"], fks=[("pn", "part_master", "pn")]))

_reg(_t("serialised_components", "Serial-number register for rotables at end of run + full state history.", Provenance.SIMULATED, [
    Col("serial", "string", "Serial number, e.g. GN-32-R014-S0007"),
    Col("pn", "string", "Part number"),
    Col("state", "string", "Serial state", allowed=tuple(s.value for s in SerialState)),
    Col("location", "string", "Station, tail, or shop id"),
    Col("since_h", "int64", "In this state since", "h", nonneg=True),
    Col("until_h", "int64", "Left this state (null if current)", "h", nullable=True),
], pk=["serial", "since_h"], fks=[("pn", "part_master", "pn")]))

_reg(_t("inventory_transactions", "Stock movements (serviceable unless noted).", Provenance.SIMULATED, [
    Col("txn_id", "int64", "Transaction id", nonneg=True),
    Col("t_h", "int64", "Time", "h", nonneg=True),
    Col("pn", "string", "Part number"),
    Col("station", "string", "Station", allowed=tuple(STATIONS)),
    Col("txn_type", "string", "Transaction type", allowed=tuple(t.value for t in TxnType)),
    Col("qty_delta", "int64", "Signed change to serviceable on-hand"),
    Col("ref_id", "string", "Reference (request/PO/RO/transfer id)", nullable=True),
    Col("serial", "string", "Serial (rotables)", nullable=True),
], pk=["txn_id"], fks=[("pn", "part_master", "pn")]))

_reg(_t("repair_orders", "Shop visits of removed rotables.", Provenance.SIMULATED, [
    Col("ro_id", "int64", "Repair order id", nonneg=True),
    Col("serial", "string", "Serial"),
    Col("pn", "string", "Part number"),
    Col("shop", "string", "Repair shop id"),
    Col("removed_h", "int64", "Removal time", "h", nonneg=True),
    Col("shop_in_h", "int64", "Arrival at shop", "h", nonneg=True),
    Col("start_h", "int64", "Repair start (after queue)", "h", nullable=True),
    Col("quoted_due_h", "int64", "Quoted return-to-stock due time", "h", nonneg=True),
    Col("return_h", "int64", "Returned serviceable to AUH (null if open/condemned)", "h", nullable=True),
    Col("condemned", "bool", "Beyond economic repair"),
    Col("repair_cost_aed", "float64", "Cost", "AED", nonneg=True),
], pk=["ro_id"], fks=[("pn", "part_master", "pn")]))

_reg(_t("purchase_orders", "Purchase orders (new stock, condemnation replacement).", Provenance.SIMULATED, [
    Col("po_id", "int64", "PO id", nonneg=True),
    Col("pn", "string", "Part number"),
    Col("station", "string", "Receiving station", allowed=tuple(STATIONS)),
    Col("qty", "int64", "Quantity", nonneg=True),
    Col("order_h", "int64", "Order time", "h", nonneg=True),
    Col("due_h", "int64", "Quoted due", "h", nonneg=True),
    Col("receipt_h", "int64", "Actual receipt (null if open)", "h", nullable=True),
    Col("reason", "string", "reorder | condemn_replacement | expedite | initial"),
    Col("value_aed", "float64", "Order value", "AED", nonneg=True),
], pk=["po_id"], fks=[("pn", "part_master", "pn")]))

_reg(_t("transfers", "Serviceable stock moves between stations.", Provenance.SIMULATED, [
    Col("transfer_id", "int64", "Transfer id", nonneg=True),
    Col("pn", "string", "Part number"),
    Col("from_station", "string", "Origin", allowed=tuple(STATIONS)),
    Col("to_station", "string", "Destination", allowed=tuple(STATIONS)),
    Col("qty", "int64", "Quantity", nonneg=True),
    Col("ship_h", "int64", "Ship time", "h", nonneg=True),
    Col("arrive_h", "int64", "Arrival", "h", nonneg=True),
    Col("kind", "string", "routine | emergency | lateral | rebalance"),
    Col("cost_aed", "float64", "Logistics cost", "AED", nonneg=True),
    Col("request_id", "int64", "Triggering request (emergency)", nullable=True),
], pk=["transfer_id"], fks=[("pn", "part_master", "pn")]))

_reg(_t("aog_events", "Material-related groundings (merged intervals per aircraft).", Provenance.SIMULATED, [
    Col("aog_id", "int64", "AOG id", nonneg=True),
    Col("tail", "string", "Aircraft"),
    Col("station", "string", "Where grounded", allowed=tuple(STATIONS)),
    Col("start_h", "int64", "Grounding start", "h", nonneg=True),
    Col("end_h", "int64", "Part fitted / released", "h", nonneg=True),
    Col("hours", "float64", "Duration", "h", nonneg=True),
    Col("pns", "string", "Driving PN(s), ';'-separated"),
    Col("request_ids", "string", "Driving request ids, ';'-separated"),
    Col("trigger", "string", "D0_no_stock | deadline_expired"),
], pk=["aog_id"], fks=[("tail", "aircraft_master", "tail")]))

_reg(_t("policy_results", "KPIs per policy × seed run (evaluation window only).", Provenance.SIMULATED, [
    Col("policy_id", "string", "P0 | P1 | P2 | P3 | frontier candidate id"),
    Col("seed", "int64", "Scenario seed", nonneg=True),
    Col("split", "string", "selection | holdout", allowed=("selection", "holdout", "history")),
    Col("immediate_fill_rate", "float64", "Share of request qty filled from local stock at need time", nonneg=True),
    Col("aog_hours", "float64", "Material AOG hours (window, annualised to 52 w)", "h", nonneg=True),
    Col("aog_events", "int64", "AOG event count", nonneg=True),
    Col("backorder_unit_hours", "float64", "Unfilled request-hours", "unit·h", nonneg=True),
    Col("spare_capital_aed", "float64", "Average capital tied up in spares (serviceable + pipeline owned)", "AED", nonneg=True),
    Col("holding_cost_aed", "float64", "Annual carrying cost", "AED", nonneg=True),
    Col("repair_cost_aed", "float64", "Annual repair cost", "AED", nonneg=True),
    Col("logistics_cost_aed", "float64", "Annual routine logistics", "AED", nonneg=True),
    Col("expedite_cost_aed", "float64", "Annual emergency/expedite logistics + premiums", "AED", nonneg=True),
    Col("aog_penalty_aed", "float64", "Annual AOG penalty (scenario)", "AED", nonneg=True),
    Col("purchase_spend_aed", "float64", "Purchases in window (consumption replenishment)", "AED", nonneg=True),
], pk=["policy_id", "seed", "split"]))

_reg(_t("planner_exceptions", "Weekly planner action inbox.", Provenance.DERIVED, [
    Col("exception_id", "string", "Exception id"),
    Col("week", "int64", "Week raised", "week", nonneg=True),
    Col("type", "string", "Exception type"),
    Col("severity", "string", "urgent | review | info", allowed=("urgent", "review", "info")),
    Col("pn", "string", "Part number", nullable=True),
    Col("station", "string", "Station", nullable=True),
    Col("summary", "string", "One-line summary"),
    Col("evidence", "string", "JSON evidence payload"),
    Col("recommended_action", "string", "Recommended action"),
    Col("owner", "string", "Role owning the action"),
    Col("due_week", "int64", "Due week", "week", nonneg=True),
], pk=["exception_id"]))

_reg(_t("assumption_register", "Flattened config/assumptions.yaml.", Provenance.ASSUMED, [
    Col("key", "string", "Dotted key"),
    Col("value", "string", "Value (JSON)"),
    Col("provenance", "string", "Provenance tag", allowed=tuple(PROVENANCE_VALUES)),
    Col("rationale", "string", "Rationale", nullable=True),
], pk=["key"]))

# ---- hidden ground truth (data/ground_truth only) ----
_reg(_t("gt_part_truth", "TRUE generator parameters. Only truth-recovery evaluation may read.", Provenance.SIMULATED, [
    Col("pn", "string", "Part number"),
    Col("mtbur_true", "float64", "True MTBUR", "FH or FC", nullable=True),
    Col("nb_k", "float64", "Negative-binomial shape (null = Poisson)", nullable=True),
    Col("usage_per_1000_fc_true", "float64", "True line usage rate (consumables)", nullable=True),
    Col("condemnation_prob_true", "float64", "True condemnation probability", nullable=True),
    Col("repair_tat_mean_true_d", "float64", "True shop TAT mean", "days", nullable=True),
    Col("lead_time_mean_true_d", "float64", "True lead time mean (pre-change)", "days", nullable=True),
    Col("lead_time_change_week", "int64", "Week of lead-time jump (PS4)", nullable=True),
    Col("lead_time_after_d", "float64", "Lead time after jump", "days", nullable=True),
    Col("trend_per_year", "float64", "Multiplicative demand trend per year (PS3)", nullable=True),
], pk=["pn"], hidden=True))


def validate_table(name: str, df: pd.DataFrame) -> list[str]:
    """Return a list of contract violations (empty list == valid)."""
    t = TABLES[name]
    errs: list[str] = []
    missing = [c for c in t.colnames if c not in df.columns]
    if missing:
        errs.append(f"{name}: missing columns {missing}")
        return errs
    if len(df) and df.duplicated(list(t.pk)).any():
        errs.append(f"{name}: duplicate primary key {t.pk}")
    for c in t.cols:
        s = df[c.name]
        if not c.nullable and s.isna().any():
            errs.append(f"{name}.{c.name}: nulls in non-nullable column")
        if c.nonneg and pd.api.types.is_numeric_dtype(s) and (s.dropna() < 0).any():
            errs.append(f"{name}.{c.name}: negative values")
        if c.allowed:
            bad = set(s.dropna().astype(str)) - set(c.allowed)
            if bad:
                errs.append(f"{name}.{c.name}: values outside allowed set {sorted(bad)[:5]}")
    return errs


def validate_fks(tables: dict[str, pd.DataFrame]) -> list[str]:
    errs = []
    for name, df in tables.items():
        if name not in TABLES:
            continue
        for col, other, ocol in TABLES[name].fks:
            if other in tables and len(df):
                bad = set(df[col].dropna()) - set(tables[other][ocol])
                if bad:
                    errs.append(f"{name}.{col} -> {other}.{ocol}: {len(bad)} orphan keys e.g. {sorted(bad)[:3]}")
    return errs


def public_tables() -> Iterable[str]:
    return [n for n, t in TABLES.items() if not t.hidden]
