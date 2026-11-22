"""Generate fake broker submissions: an email body + ACORD-style application PDF + loss run PDF.

Every business, person and carrier here is fictional. Each sample tests a different path
through the agent graph (clean, CAT referral, decline, incomplete, duplicate, bad losses).

Run:  python scripts/generate_samples.py
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "submissions"


def eff(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


SAMPLES = [
    {
        "id": "S001",
        "scenario": "Clean, preferred class, should be P1",
        "broker": ("Priya Nair", "priya.nair@lonestarbrokers.example"),
        "email": "Hi team, please find attached a new submission for Bright Smile Dental Care LLC, "
                 "a 3-dentist general dentistry practice (no oral surgery). Looking for Property and GL "
                 "effective {eff}. Clean loss history. Thanks, Priya",
        "app": {
            "Named Insured": "Bright Smile Dental Care LLC",
            "Business Description": "General dentistry office, no surgery",
            "NAICS": "621210",
            "Years in Business": "12",
            "Annual Revenue": "$2,400,000",
            "Employees": "18",
            "Mailing Address": "4410 Burnet Rd, Austin, TX 78756",
            "Location Address": "4410 Burnet Rd, Austin, TX 78756",
            "Building Value": "$1,850,000",
            "Contents / BPP Value": "$620,000",
            "Construction": "Joisted masonry",
            "Year Built": "2004",
            "Sprinklered": "Yes",
            "Lines Requested": "Property, General Liability",
            "Proposed Effective Date": "{eff}",
        },
        "eff_days": 21,
        "losses": [],
    },
    {
        "id": "S002",
        "scenario": "Coastal Texas restaurant, hurricane referral",
        "broker": ("Marcus Lee", "mlee@gulfcoastins.example"),
        "email": "Hello, new business for Gulf Breeze Seafood Grill Inc in Galveston. Full-service seafood "
                 "restaurant, Ansul system over the fryers. Need Property + GL, eff {eff}. "
                 "Loss runs attached (2 small claims). - Marcus",
        "app": {
            "Named Insured": "Gulf Breeze Seafood Grill Inc",
            "Business Description": "Full-service seafood restaurant with automatic hood extinguishing",
            "NAICS": "722511",
            "Years in Business": "7",
            "Annual Revenue": "$3,100,000",
            "Employees": "42",
            "Mailing Address": "2101 Seawall Blvd, Galveston, TX 77550",
            "Location Address": "2101 Seawall Blvd, Galveston, TX 77550",
            "Building Value": "$2,300,000",
            "Contents / BPP Value": "$450,000",
            "Construction": "Masonry non-combustible",
            "Year Built": "1998",
            "Sprinklered": "Yes",
            "Lines Requested": "Property, General Liability",
            "Proposed Effective Date": "{eff}",
        },
        "eff_days": 30,
        "losses": [(2023, "Slip and fall - customer", 18500), (2025, "Kitchen water damage", 32000)],
    },
    {
        "id": "S003",
        "scenario": "Prohibited class, should decline",
        "broker": ("Dana Ortiz", "dana@desertriskpartners.example"),
        "email": "Team - can you quote Boom Town Fireworks LLC? They manufacture and store consumer "
                 "fireworks in Pahrump NV. Property and GL, eff {eff}. Thanks, Dana",
        "app": {
            "Named Insured": "Boom Town Fireworks LLC",
            "Business Description": "Manufacturing and warehouse storage of consumer fireworks",
            "NAICS": "325998",
            "Years in Business": "9",
            "Annual Revenue": "$5,600,000",
            "Employees": "25",
            "Mailing Address": "1600 E Basin Ave, Pahrump, NV 89060",
            "Location Address": "1600 E Basin Ave, Pahrump, NV 89060",
            "Building Value": "$3,200,000",
            "Contents / BPP Value": "$1,900,000",
            "Construction": "Metal frame",
            "Year Built": "2011",
            "Sprinklered": "Yes",
            "Lines Requested": "Property, General Liability",
            "Proposed Effective Date": "{eff}",
        },
        "eff_days": 25,
        "losses": [(2024, "Small warehouse fire", 140000)],
    },
    {
        "id": "S004",
        "scenario": "Incomplete: missing construction, year built, loss runs",
        "broker": ("Tom Becker", "tbecker@rockymtnagency.example"),
        "email": "Quick one - Peak Logistics Storage LLC, dry goods warehouse in Denver. Need property "
                 "and GL starting {eff}. Will send loss runs later. Tom",
        "app": {
            "Named Insured": "Peak Logistics Storage LLC",
            "Business Description": "Warehouse storing packaged dry goods (non-hazardous)",
            "Years in Business": "4",
            "Annual Revenue": "$1,200,000",
            "Employees": "9",
            "Location Address": "5200 Fox St, Denver, CO 80216",
            "Building Value": "$2,900,000",
            "Contents / BPP Value": "$800,000",
            "Lines Requested": "Property, General Liability",
            "Proposed Effective Date": "{eff}",
        },
        "eff_days": 4,
        "losses": None,  # no loss run attached
    },
    {
        "id": "S005",
        "scenario": "Already submitted by another broker (clearance hit)",
        "broker": ("Aisha Khan", "akhan@midwestcommercial.example"),
        "email": "Hi, attaching a submission for Riverside Auto Parts Inc, auto parts retail store in "
                 "Columbus OH. Property + GL effective {eff}. Regards, Aisha",
        "app": {
            "Named Insured": "Riverside Auto Parts Inc.",
            "Business Description": "Retail auto parts store",
            "NAICS": "441330",
            "Years in Business": "15",
            "Annual Revenue": "$4,300,000",
            "Employees": "22",
            "Location Address": "880 W Broad St, Columbus, OH 43222",
            "Building Value": "$1,400,000",
            "Contents / BPP Value": "$900,000",
            "Construction": "Joisted masonry",
            "Year Built": "1987",
            "Sprinklered": "No",
            "Lines Requested": "Property, General Liability",
            "Proposed Effective Date": "{eff}",
        },
        "eff_days": 40,
        "losses": [(2022, "Customer injury", 9000)],
    },
    {
        "id": "S006",
        "scenario": "Bad loss history (4 claims incl. fire), referral",
        "broker": ("Ben Carter", "bcarter@buckeyeriskgroup.example"),
        "email": "New submission: Sunset Furniture Assembly Co, Dayton OH. Light assembly of flat-pack "
                 "furniture. Property and GL, eff {eff}. Loss runs attached - there was a fire in "
                 "2024, sprinklers have since been upgraded. Ben",
        "app": {
            "Named Insured": "Sunset Furniture Assembly Co",
            "Business Description": "Light assembly of wooden flat-pack furniture",
            "NAICS": "337122",
            "Years in Business": "11",
            "Annual Revenue": "$6,800,000",
            "Employees": "55",
            "Location Address": "3300 Valley St, Dayton, OH 45404",
            "Building Value": "$4,100,000",
            "Contents / BPP Value": "$2,200,000",
            "Construction": "Frame",
            "Year Built": "1955",
            "Sprinklered": "Yes",
            "Lines Requested": "Property, General Liability",
            "Proposed Effective Date": "{eff}",
        },
        "eff_days": 35,
        "losses": [(2022, "Employee hand injury (GL claim by temp)", 22000),
                   (2023, "Theft of tools", 15000),
                   (2024, "Fire in finishing area", 310000),
                   (2025, "Roof leak water damage", 41000)],
    },
    # ---------- Harder cases (day 2): the model has to reason, not just copy ----------
    {
        "id": "S007",
        "scenario": "Cannabis dispensary that never says 'cannabis' (decline)",
        "broker": ("Lena Park", "lpark@frontrangerisk.example"),
        "email": "Hi all, new retail account: Green Leaf Wellness LLC in Denver. State-licensed adult-use "
                 "dispensary, sells THC flower, edibles and vape products. Property + GL eff {eff}. Lena",
        "app": {
            "Named Insured": "Green Leaf Wellness LLC",
            "Business Description": "State-licensed adult-use retail dispensary (THC flower, edibles, vapes)",
            "Years in Business": "5",
            "Annual Revenue": "$1,900,000",
            "Employees": "12",
            "Location Address": "1550 S Broadway, Denver, CO 80210",
            "Building Value": "$900,000",
            "Contents / BPP Value": "$350,000",
            "Construction": "Masonry",
            "Year Built": "1978",
            "Sprinklered": "No",
            "Lines Requested": "Property, General Liability",
            "Proposed Effective Date": "{eff}",
        },
        "eff_days": 30,
        "losses": [],
    },
    {
        "id": "S008",
        "scenario": "Bar where liquor is 70% of sales (decline)",
        "broker": ("Sam Novak", "snovak@lakeshorebrokerage.example"),
        "email": "Hello, please quote Rusty Anchor Tavern Inc, a sports bar in Chicago. Liquor is roughly "
                 "70% of sales, the kitchen does wings and burgers. Property + GL eff {eff}. Sam",
        "app": {
            "Named Insured": "Rusty Anchor Tavern Inc",
            "Business Description": "Sports bar and tavern; liquor approx. 70% of sales; bar food kitchen",
            "Years in Business": "8",
            "Annual Revenue": "$1,400,000",
            "Employees": "16",
            "Location Address": "2244 N Clark St, Chicago, IL 60614",
            "Building Value": "$1,100,000",
            "Contents / BPP Value": "$200,000",
            "Construction": "Joisted masonry",
            "Year Built": "1925",
            "Sprinklered": "No",
            "Lines Requested": "Property, General Liability",
            "Proposed Effective Date": "{eff}",
        },
        "eff_days": 20,
        "losses": [(2023, "Patron assault claim", 45000)],
    },
    {
        "id": "S009",
        "scenario": "Email contradicts the application; values written as $4.5M / 1.2 million",
        "broker": ("Grace Liu", "gliu@pugetsoundins.example"),
        "email": "Hi team - Cascade Code Labs Inc, IT consulting firm in Seattle. Revenue is about $3.2M "
                 "this year. Property + GL eff {eff}, no losses. Thanks, Grace",
        "app": {
            "Named Insured": "Cascade Code Labs Inc",
            "Business Description": "IT consulting and software development office",
            "NAICS": "541512",
            "Years in Business": "9",
            "Annual Revenue": "$2,800,000",
            "Employees": "31",
            "Location Address": "1420 5th Ave, Seattle, WA 98101",
            "Building Value": "$4.5M",
            "Contents / BPP Value": "1.2 million",
            "Construction": "Fire resistive",
            "Year Built": "2015",
            "Sprinklered": "Yes",
            "Lines Requested": "Property, General Liability",
            "Proposed Effective Date": "{eff}",
        },
        "eff_days": 20,
        "losses": [],
    },
    {
        "id": "S010",
        "scenario": "New venture, $11.5M insured value, unsprinklered (3 referral rules)",
        "broker": ("Omar Haddad", "ohaddad@sonoranbrokers.example"),
        "email": "New clinic for you: Desert Bloom Family Medicine PLLC, Phoenix. Primary care, no "
                 "surgery. Owners are experienced physicians but the practice opened 2 years ago. "
                 "Property + GL eff {eff}. Omar",
        "app": {
            "Named Insured": "Desert Bloom Family Medicine PLLC",
            "Business Description": "Primary care medical clinic, no surgery",
            "Years in Business": "2",
            "Annual Revenue": "$3,500,000",
            "Employees": "27",
            "Location Address": "2600 N Central Ave, Phoenix, AZ 85004",
            "Building Value": "$9,000,000",
            "Contents / BPP Value": "$2,500,000",
            "Construction": "Fire resistive",
            "Year Built": "1999",
            "Sprinklered": "No",
            "Lines Requested": "Property, General Liability",
            "Proposed Effective Date": "{eff}",
        },
        "eff_days": 45,
        "losses": [(2025, "Patient slip and fall", 12000)],
    },
    {
        "id": "S011",
        "scenario": "Abbreviated form labels; California wildfire zone (refer)",
        "broker": ("Rosa Mendez", "rmendez@napacountyins.example"),
        "email": "Pls quote attached - hardware store in Napa. Prop/GL, eff {eff}. Rosa",
        "app": {
            "Insd": "Napa Valley Home & Garden Supply LLC",
            "Desc": "Retail hardware and garden supply store",
            "Yrs in bus.": "14",
            "Rev ($)": "2.2M",
            "Emp": "15",
            "Loc": "1300 Soscol Ave, Napa, CA 94559",
            "Bldg ($)": "1.6M",
            "BPP ($)": "700K",
            "Constr.": "JM",
            "Yr Blt": "1972",
            "Sprk": "Y",
            "LOB": "Prop / GL",
            "Eff. Date": "{eff}",
        },
        "eff_days": 50,
        "losses": [],
    },
    {
        "id": "S012",
        "scenario": "Revenue and staff count only in the email, not the application",
        "broker": ("Jake Turner", "jturner@capitalcityagency.example"),
        "email": "Hi, new account: Keystone Insurance Agency LLC, downtown Columbus. FYI revenue isn't on "
                 "the app - they do about $1.6M in commissions with 11 staff. Property + GL eff {eff}. Jake",
        "app": {
            "Named Insured": "Keystone Insurance Agency LLC",
            "Business Description": "Independent insurance agency office",
            "NAICS": "524210",
            "Years in Business": "22",
            "Location Address": "155 E Broad St, Columbus, OH 43215",
            "Building Value": "$1,300,000",
            "Contents / BPP Value": "$250,000",
            "Construction": "Fire resistive",
            "Year Built": "1990",
            "Sprinklered": "Yes",
            "Lines Requested": "Property, General Liability",
            "Proposed Effective Date": "{eff}",
        },
        "eff_days": 10,
        "losses": [],
    },
]

# Answer key for scripts/evaluate.py. Written by hand from the documents and guidelines,
# NOT copied from agent output. None = the value is genuinely absent, so the agent must not invent it.
LABELS = {
    "S001": dict(insured_name="Bright Smile Dental Care LLC", annual_revenue=2_400_000, building_value=1_850_000,
                 contents_value=620_000, construction_type="joisted masonry", year_built=2004, sprinklered=True,
                 state="TX", appetite="in_appetite", clearance="clear", priority="P1-hot", blocking=[], conflict=False),
    "S002": dict(insured_name="Gulf Breeze Seafood Grill Inc", annual_revenue=3_100_000, building_value=2_300_000,
                 contents_value=450_000, construction_type="masonry non-combustible", year_built=1998, sprinklered=True,
                 state="TX", appetite="refer", clearance="clear", priority="P2-standard", blocking=[], conflict=False),
    "S003": dict(insured_name="Boom Town Fireworks LLC", annual_revenue=5_600_000, building_value=3_200_000,
                 contents_value=1_900_000, construction_type="metal frame", year_built=2011, sprinklered=True,
                 state="NV", appetite="out_of_appetite", clearance="clear", priority="decline", blocking=[], conflict=False),
    "S004": dict(insured_name="Peak Logistics Storage LLC", annual_revenue=1_200_000, building_value=2_900_000,
                 contents_value=800_000, construction_type=None, year_built=None, sprinklered=None,
                 state="CO", appetite="in_appetite", clearance="clear", priority="P2-standard",
                 blocking=["construction_type", "loss_runs", "year_built"], conflict=False),
    "S005": dict(insured_name="Riverside Auto Parts Inc.", annual_revenue=4_300_000, building_value=1_400_000,
                 contents_value=900_000, construction_type="joisted masonry", year_built=1987, sprinklered=False,
                 state="OH", appetite=None, clearance="possible_duplicate", priority="P3-low", blocking=[], conflict=False),
    "S006": dict(insured_name="Sunset Furniture Assembly Co", annual_revenue=6_800_000, building_value=4_100_000,
                 contents_value=2_200_000, construction_type="frame", year_built=1955, sprinklered=True,
                 state="OH", appetite="refer", clearance="clear", priority="P2-standard", blocking=[], conflict=False),
    "S007": dict(insured_name="Green Leaf Wellness LLC", annual_revenue=1_900_000, building_value=900_000,
                 contents_value=350_000, construction_type="masonry", year_built=1978, sprinklered=False,
                 state="CO", appetite="out_of_appetite", clearance="clear", priority="decline", blocking=[], conflict=False),
    "S008": dict(insured_name="Rusty Anchor Tavern Inc", annual_revenue=1_400_000, building_value=1_100_000,
                 contents_value=200_000, construction_type="joisted masonry", year_built=1925, sprinklered=False,
                 state="IL", appetite="out_of_appetite", clearance="clear", priority="decline", blocking=[], conflict=False),
    "S009": dict(insured_name="Cascade Code Labs Inc", annual_revenue=2_800_000, building_value=4_500_000,
                 contents_value=1_200_000, construction_type="fire resistive", year_built=2015, sprinklered=True,
                 state="WA", appetite="in_appetite", clearance="clear", priority="P1-hot", blocking=[], conflict=True),
    "S010": dict(insured_name="Desert Bloom Family Medicine PLLC", annual_revenue=3_500_000, building_value=9_000_000,
                 contents_value=2_500_000, construction_type="fire resistive", year_built=1999, sprinklered=False,
                 state="AZ", appetite="refer", clearance="clear", priority="P2-standard", blocking=[], conflict=False),
    "S011": dict(insured_name="Napa Valley Home & Garden Supply LLC", annual_revenue=2_200_000, building_value=1_600_000,
                 contents_value=700_000, construction_type="joisted masonry", year_built=1972, sprinklered=True,
                 state="CA", appetite="refer", clearance="clear", priority="P2-standard", blocking=[], conflict=False),
    "S012": dict(insured_name="Keystone Insurance Agency LLC", annual_revenue=1_600_000, building_value=1_300_000,
                 contents_value=250_000, construction_type="fire resistive", year_built=1990, sprinklered=True,
                 state="OH", appetite="in_appetite", clearance="clear", priority="P1-hot", blocking=[], conflict=False),
}

# Submissions the carrier has already received (used by the Clearance Agent).
EXISTING = [
    {"submission_id": "EX-2026-0912", "insured_name": "Riverside Auto Parts, Inc.",
     "address": "880 West Broad Street, Columbus, OH 43222", "broker": "Great Lakes Insurance Brokers",
     "received": "2026-11-02"},
    {"submission_id": "EX-2026-0877", "insured_name": "Lakeview Pediatrics PC",
     "address": "77 Lake Shore Dr, Chicago, IL 60611", "broker": "Windy City Agency",
     "received": "2026-10-28"},
    {"submission_id": "EX-2026-0790", "insured_name": "Bright Horizons Daycare LLC",
     "address": "12 Elm St, Plano, TX 75074", "broker": "Lone Star Brokers",
     "received": "2026-10-11"},
]


def write_pdf(path: Path, title: str, lines: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=LETTER)
    w, h = LETTER
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, h - 50, title)
    c.setFont("Helvetica", 10)
    y = h - 80
    for line in lines:
        c.drawString(50, y, line)
        y -= 16
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = h - 50
    c.save()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for s in SAMPLES:
        d = OUT / s["id"]
        d.mkdir(exist_ok=True)
        e = eff(s["eff_days"])
        name, addr = s["broker"]
        (d / "email.txt").write_text(
            f"From: {name} <{addr}>\nSubject: New submission - {LABELS[s['id']]['insured_name']}\n\n"
            + s["email"].format(eff=e) + "\n",
            encoding="utf-8",
        )
        app_lines = ["COMMERCIAL INSURANCE APPLICATION (ACORD 125/140 style - demo)", ""]
        app_lines += [f"{k}: {v.format(eff=e)}" for k, v in s["app"].items()]
        write_pdf(d / "application.pdf", "Commercial Insurance Application", app_lines)
        if s["losses"] is not None:
            lines = [f"Insured: {LABELS[s['id']]['insured_name']}", "Period: last 5 years", "",
                     "Year | Cause | Paid (USD)"]
            lines += [f"{y} | {cause} | ${amt:,.0f}" for y, cause, amt in s["losses"]] or []
            if not s["losses"]:
                lines.append("No losses reported in the last 5 years.")
            write_pdf(d / "loss_run.pdf", "Loss Run Report", lines)
        (d / "meta.json").write_text(json.dumps({"scenario": s["scenario"]}, indent=2), encoding="utf-8")
        label = dict(LABELS[s["id"]], effective_date=e, loss_count=len(s["losses"] or []),
                     loss_total=sum(a for _, _, a in (s["losses"] or [])))
        (d / "expected.json").write_text(json.dumps(label, indent=2), encoding="utf-8")
    (ROOT / "data" / "existing_submissions.json").write_text(json.dumps(EXISTING, indent=2), encoding="utf-8")
    print(f"Wrote {len(SAMPLES)} submissions to {OUT}")


if __name__ == "__main__":
    main()
