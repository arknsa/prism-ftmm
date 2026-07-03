#!/usr/bin/env python3
"""Synthetic alumni data generator for development and demo (P7.2).

Generates realistic CSV files (matching IMPORT_FILE_FORMAT_SPEC.md) that can be
uploaded via the normal import pipeline — no PII used.

Produces two quarterly exports that simulate a real quarterly refresh cycle:
  - Q1 export:  100 alumni × cohorts 2018–2023, varied employers/industries/locations
  - Q2 export:  same alumni + 20 new graduates, some role changes

Usage:
    python generate_synthetic_data.py [--output-dir OUTPUT_DIR] [--seed SEED]

Output:
    OUTPUT_DIR/
        synthetic_alumni_2025_Q1.csv   — first quarter export
        synthetic_alumni_2025_Q2.csv   — second quarter (role updates + new entries)

The CSV schema matches IMPORT_FILE_FORMAT_SPEC.md (Artifact A1):
    full_name, study_program, graduation_year, employer, role_title,
    location, linkedin_url

Decisions honoured:
  D-004: Only 5 approved FTMM programs used.
  D-050: No scraping; data is entirely fabricated.
  D-051: No real PII — names are synthetic, linkedin_url is synthetic.
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

# ---------------------------------------------------------------------------
# Reference data (synthetic, no PII)
# ---------------------------------------------------------------------------

PROGRAMS = [
    "Teknik Industri",
    "Teknologi Sains Data",
    "Teknik Elektro",
    "Teknik Nanoteknologi",
    "Teknik Robotika dan Kecerdasan Buatan",
]

FIRST_NAMES = [
    "Andi", "Budi", "Citra", "Dewi", "Eko", "Fitri", "Gilang", "Hana",
    "Ivan", "Joko", "Kartika", "Lina", "Muhamad", "Nadia", "Oka", "Putri",
    "Rafi", "Sari", "Teguh", "Umar", "Vina", "Wahyu", "Xena", "Yuda", "Zara",
    "Arif", "Bayu", "Cindy", "Dika", "Elsa", "Fajar", "Gita", "Hendra",
    "Indra", "Jasmine", "Kevin", "Layla", "Miko", "Nina", "Oscar", "Prita",
    "Qori", "Rizki", "Sinta", "Tono", "Ulfa", "Viko", "Weni", "Yani",
]

LAST_NAMES = [
    "Santoso", "Wijaya", "Kusuma", "Pratama", "Utama", "Rahayu", "Setiawan",
    "Putra", "Saputra", "Nugroho", "Purnomo", "Kurniawan", "Hidayat",
    "Wibowo", "Susanto", "Suryadi", "Hartono", "Gunawan", "Hakim", "Yulianto",
    "Prabowo", "Anggraeni", "Lestari", "Dewi", "Agung", "Wahyudi",
]

EMPLOYERS_BY_PROGRAM: dict[str, list[str]] = {
    "Teknik Industri": [
        "PT Astra International", "Unilever Indonesia", "PT Indofood",
        "PT Kalbe Farma", "PT Semen Indonesia", "McKinsey & Company Indonesia",
        "PT Telekomunikasi Indonesia", "PT PLN Persero", "PT Krakatau Steel",
        "Deloitte Indonesia", "PT Bank Mandiri", "PT Pertamina",
    ],
    "Teknologi Sains Data": [
        "Gojek", "Tokopedia", "Shopee Indonesia", "Traveloka", "Bukalapak",
        "Google Indonesia", "Microsoft Indonesia", "IBM Indonesia",
        "PT Teknologi Finansial", "Accenture Indonesia", "Grab Indonesia",
        "OVO Indonesia",
    ],
    "Teknik Elektro": [
        "PT Schneider Electric", "Siemens Indonesia", "ABB Indonesia",
        "PT PLN Persero", "PT Telekomunikasi Indonesia", "Huawei Indonesia",
        "Samsung Electronics Indonesia", "PT Industri Listrik", "Ericsson Indonesia",
        "Philips Indonesia", "PT Paiton Energy",
    ],
    "Teknik Nanoteknologi": [
        "BPPT Indonesia", "LIPI Indonesia", "PT Kimia Farma", "PT Bio Farma",
        "PT Pupuk Indonesia", "BATAN Indonesia", "Bandung Institute of Technology",
        "PT Semen Gresik", "PT Aneka Tambang",
    ],
    "Teknik Robotika dan Kecerdasan Buatan": [
        "Gojek AI Lab", "Tokopedia Tech", "PT Robotik Indonesia", "Intel Indonesia",
        "NVIDIA Indonesia", "PT Automation Indonesia", "ITS Robotics Lab",
        "PT Smart Manufacturing", "Telkom Indonesia Digital", "Astra Tech",
    ],
}

ROLES_BY_PROGRAM: dict[str, list[str]] = {
    "Teknik Industri": [
        "Industrial Engineer", "Process Improvement Manager", "Supply Chain Analyst",
        "Operations Manager", "Quality Engineer", "Lean Consultant",
        "Manufacturing Supervisor", "Logistics Manager", "Business Analyst",
        "Project Manager",
    ],
    "Teknologi Sains Data": [
        "Data Scientist", "Machine Learning Engineer", "Data Analyst",
        "Business Intelligence Analyst", "Data Engineer", "AI Research Scientist",
        "Product Analyst", "Analytics Lead", "Principal Data Scientist",
    ],
    "Teknik Elektro": [
        "Electrical Engineer", "Power Systems Engineer", "Control Systems Engineer",
        "RF Engineer", "Embedded Systems Developer", "Network Engineer",
        "Automation Engineer", "Field Service Engineer", "Systems Architect",
    ],
    "Teknik Nanoteknologi": [
        "Materials Scientist", "Nanotechnology Researcher", "Process Engineer",
        "Quality Control Analyst", "R&D Scientist", "Lab Researcher",
        "Chemical Engineer", "Semiconductor Engineer",
    ],
    "Teknik Robotika dan Kecerdasan Buatan": [
        "Robotics Engineer", "Computer Vision Engineer", "AI Engineer",
        "Automation Engineer", "ROS Developer", "Deep Learning Researcher",
        "Simulation Engineer", "Controls Engineer", "Perception Engineer",
    ],
}

LOCATIONS = [
    "Jakarta, Indonesia",
    "Surabaya, Indonesia",
    "Bandung, Indonesia",
    "Yogyakarta, Indonesia",
    "Semarang, Indonesia",
    "Medan, Indonesia",
    "Singapore",
    "Kuala Lumpur, Malaysia",
    "Sydney, Australia",
    "Singapore",  # listed twice to increase probability
    "Jakarta, Indonesia",  # most common
    "Jakarta, Indonesia",
]

COHORT_YEARS = list(range(2018, 2025))

# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

_FIELDNAMES = [
    "full_name",
    "study_program",
    "graduation_year",
    "employer",
    "role_title",
    "location",
    "linkedin_url",
]


def _make_linkedin_url(name: str, idx: int) -> str:
    slug = name.lower().replace(" ", "-").replace(".", "")
    return f"https://www.linkedin.com/in/{slug}-{idx:04d}"


def _generate_alumni_pool(n: int, rng: random.Random) -> list[dict[str, object]]:
    """Create a pool of synthetic alumni records."""
    alumni = []
    for i in range(1, n + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        name = f"{first} {last}"
        program = rng.choice(PROGRAMS)
        grad_year = rng.choice(COHORT_YEARS)
        employer = rng.choice(EMPLOYERS_BY_PROGRAM[program])
        role = rng.choice(ROLES_BY_PROGRAM[program])
        location = rng.choice(LOCATIONS)
        alumni.append(
            {
                "full_name": name,
                "study_program": program,
                "graduation_year": grad_year,
                "employer": employer,
                "role_title": role,
                "location": location,
                "linkedin_url": _make_linkedin_url(name, i),
                "_idx": i,
            }
        )
    return alumni


def _write_csv(records: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    print(f"  Written: {path} ({len(records)} rows)")


def generate(output_dir: Path, seed: int = 42) -> None:
    """Generate two quarterly CSV exports and write them to output_dir."""
    rng = random.Random(seed)

    print(f"Generating synthetic alumni data (seed={seed})…")

    # Q1 — 100 alumni, all cohorts 2018–2024
    pool_q1 = _generate_alumni_pool(100, rng)

    # Q2 — same 100 alumni (some role changes) + 20 new 2024 graduates
    pool_q2 = []
    for rec in pool_q1:
        if rng.random() < 0.15:
            # 15% got a new role at the same company
            program = str(rec["study_program"])
            rec = dict(rec)
            rec["role_title"] = rng.choice(ROLES_BY_PROGRAM[program])
        elif rng.random() < 0.08:
            # 8% moved to a new employer in the same sector
            program = str(rec["study_program"])
            rec = dict(rec)
            rec["employer"] = rng.choice(EMPLOYERS_BY_PROGRAM[program])
            rec["role_title"] = rng.choice(ROLES_BY_PROGRAM[program])
            rec["location"] = rng.choice(LOCATIONS)
        pool_q2.append(rec)

    # 20 new 2024 graduates
    new_grads = _generate_alumni_pool(20, rng)
    for g in new_grads:
        g["graduation_year"] = 2024
    pool_q2.extend(new_grads)

    _write_csv(pool_q1, output_dir / "synthetic_alumni_2025_Q1.csv")
    _write_csv(pool_q2, output_dir / "synthetic_alumni_2025_Q2.csv")

    print(f"\nDone. Import these files via the curator import UI or POST /api/v1/imports.")
    print(
        "Recommended workflow:\n"
        "  1. Create snapshot '2025-Q1' via POST /api/v1/snapshots\n"
        "  2. Import synthetic_alumni_2025_Q1.csv, commit to 2025-Q1 snapshot\n"
        "  3. Validate all alumni via curator validation screen\n"
        "  4. Create snapshot '2025-Q2'\n"
        "  5. Import synthetic_alumni_2025_Q2.csv, commit to 2025-Q2 snapshot\n"
        "  6. Dashboard should now show two-quarter history"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "../../data/synthetic",
        help="Directory to write CSV files (default: scripts/../data/synthetic)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    args = parser.parse_args()
    generate(args.output_dir.resolve(), args.seed)


if __name__ == "__main__":
    main()
