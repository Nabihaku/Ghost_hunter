"""Generate SYNTHETIC identity data for the Ghost Hunter demo.
No real personal data: all names are invented and all emails use example.com."""
import csv, random
from datetime import date, timedelta
from pathlib import Path

random.seed(31)
TODAY = date(2026, 10, 31)
DATA = Path(__file__).parent / "data"
DATA.mkdir(exist_ok=True)

FIRST = ["Ava","Ben","Cara","Dev","Ella","Finn","Gita","Hugo","Isla","Jai","Kira","Leo","Maya","Nico","Omar",
         "Priya","Quinn","Rosa","Sam","Tara","Uma","Vik","Wren","Xan","Yara","Zak","Ari","Bea","Cal","Dina"]
LAST = ["Hollow","Graves","Moon","Raven","Ash","Mist","Thorn","Vale","Crow","Bone","Fog","Night","Shade","Wick","Briar"]
DEPTS = ["Finance","R&D","Clinical Ops","IT","HR","Legal","Business Development","Regulatory"]
SKUS = {"M365 E5": 47.10, "M365 E3": 30.20, "Power BI Pro": 11.30, "Visio Plan 2": 12.40, "Project Plan 3": 24.70}

users, hr, lic, roles = [], [], [], []
for i in range(1, 61):
    uid = f"U{i:03d}"
    name = f"{random.choice(FIRST)} {random.choice(LAST)}"
    dept = random.choice(DEPTS)
    last_sign_in = TODAY - timedelta(days=random.randint(0, 20))
    status = "Enabled"
    leaver = None
    r = random.random()
    if r < 0.15:   # leaver whose account was never disabled -> GHOST
        leaver = TODAY - timedelta(days=random.randint(30, 300))
        last_sign_in = leaver - timedelta(days=random.randint(0, 5))
    elif r < 0.22: # leaver handled properly
        leaver = TODAY - timedelta(days=random.randint(30, 300))
        last_sign_in = leaver; status = "Disabled"
    elif r < 0.30: # stale account, nobody has logged in for months
        last_sign_in = TODAY - timedelta(days=random.randint(95, 400))
    users.append(dict(user_id=uid, display_name=name, email=f"{name.lower().replace(' ','.')}{i}@example.com",
                      department=dept, account_status=status, last_sign_in=last_sign_in.isoformat()))
    hr.append(dict(user_id=uid, employment_status="Leaver" if leaver else "Active",
                   leave_date=leaver.isoformat() if leaver else ""))
    for sku in random.sample(list(SKUS), random.randint(1, 3)):
        used = TODAY - timedelta(days=random.randint(0, 15) if random.random() > 0.2 else random.randint(70, 250))
        lic.append(dict(user_id=uid, sku=sku, monthly_cost_gbp=SKUS[sku], last_used=used.isoformat()))
    roles.append(dict(user_id=uid, role="User"))
    if dept == "IT" or random.random() < 0.06:
        roles.append(dict(user_id=uid, role="Global Administrator"))
    if dept == "Finance":
        roles.append(dict(user_id=uid, role=random.choice(["Payment Creator", "Payment Approver"])))
        if random.random() < 0.35:
            roles.append(dict(user_id=uid, role="Payment Approver" if roles[-1]["role"] == "Payment Creator" else "Payment Creator"))

def write(name, rows):
    with open(DATA / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

write("users.csv", users); write("hr_records.csv", hr); write("licences.csv", lic); write("role_assignments.csv", roles)
print(f"Wrote {len(users)} users, {len(lic)} licences, {len(roles)} role assignments to {DATA}")
