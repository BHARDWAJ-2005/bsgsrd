# Bharat Scouts & Guides (BSG) - Sangareddy District Enrollment Portal

A district-scale Bharat Scouts & Guides student enrollment and uniform measurement web application built according to the **Implementation Guide for Sangareddy District** and populated with the official list of **112 Sanctioned Schools** from `SCOUTS & GUIDES SRD NEW SCHOOLS-112 (1).xlsx`.

---

## 🏛️ Official Sanctioned Schools & Admin Controls

### 1. Only Sanctioned Schools Allowed
- Bharat Scouts & Guides units are governed by government sanction. **Only schools officially sanctioned for Bharat Scouts & Guides** in Sangareddy appear on the enrollment portal and can log in.
- All **112 officially sanctioned schools** across 26 mandals from `SCOUTS & GUIDES SRD NEW SCHOOLS-112 (1).xlsx` have been imported directly into the database:
  - Exact 11-digit UDISE codes (`3616...` / `3617...`)
  - Official school names and mandals
  - Names of Headmasters (HM)
  - Designated Male Teacher Leaders (Scout Masters / Cub Masters) with mobile numbers
  - Designated Female Teacher Leaders (Guide Captains / Flock Leaders) with mobile numbers

### 2. Admin-Only Feature: Add & Sanction New Schools
- **Exclusive Permission:** Only authenticated District Administrators (`admin`) can sanction and add new schools.
- Accessible directly from the **District Command Center** (`/district/`) via the **"🏛️ + Add / Sanction New School"** button.
- Captures:
  - 11-digit UDISE code
  - Mandal
  - School Full Name
  - School Category (Co-ed High School, Girls High School, Boys High School, Primary, Upper Primary)
  - Sanction Order / Reference Number
  - Headmaster (HM) Name & Contact Mobile
  - Boys and Girls Quota
  - Designated Male Teacher (Scout Master) Name & Mobile
  - Designated Female Teacher (Guide Captain) Name & Mobile
- Automatically:
  1. Creates the school record with `is_sanctioned = True`.
  2. Generates the school's authentication credentials with default password `BSG@Sangareddy2026` (prompted to change on first login).
  3. Establishes the designated teacher unit leaders.
  4. Records a security audit log entry.

---

## 🌟 Other Core Features

1. **Cascading Dropdowns on Login (`/login/`):** Select Mandal &rarr; dynamically filters only sanctioned schools in that mandal keyed by UDISE code.
2. **Progressive Disclosure (SHORT vs BRIEF):**
   - **SHORT Mode:** Fast registration capturing essential uniform size, shoe size, and height (cm).
   - **BRIEF Mode:** Comprehensive tailoring specifications in inches (0.5 steps) for boys (shirt & pant) and girls (kameez & salwar/skirt).
3. **Strict Quota Enforcement:** Prevents over-enrollment via database row locks (`select_for_update`).
4. **Excel Toolkit (`openpyxl`):**
   - School-tailored Excel template with dropdown data validation.
   - All-or-nothing transactional import with row-by-row error reporting.
   - Excel export with dedicated **Uniform Size Ordering Summary Sheet** for tailors and suppliers.
5. **Official PDF Generation (`ReportLab`):** Formatted official BSG verification roster with letterhead, summary, rosters, and signature declaration lines.
6. **Bilingual Support (English & Telugu):** Toggled by `?lang=en` or `?lang=te`.

---

## 🔑 Login Credentials

| Role | Username / Selection | Password | Portal URL |
| :--- | :--- | :--- | :--- |
| **District Admin** | `admin` | `Admin@Sangareddy2026` | `http://127.0.0.1:8000/login/?tab=admin` |
| **School Login** | Select Mandal: **Ameenpur**<br/>Select School: **ZPHS AMEENPUR** (`36162500711`) | `BSG@Sangareddy2026` | `http://127.0.0.1:8000/login/` |

---

## 🚀 Running the Project

```bash
# Start development server
python manage.py runserver 127.0.0.1:8000

# Re-import official sanctioned schools from Excel
python manage.py load_official_sanctioned_schools --clear

# Run automated test suite
python manage.py test
```
