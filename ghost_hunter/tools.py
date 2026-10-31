"""Deterministic tools. The LLM never does the maths or decides who is a ghost:
these Python functions do. The LLM explains, prioritises and talks to the human."""
import csv, json, uuid
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, OUT = ROOT / "data", ROOT / "output"
OUT.mkdir(exist_ok=True)
TODAY = date(2026, 10, 31)          # fixed so the demo is repeatable
STALE_DAYS, UNUSED_LICENCE_DAYS = 90, 60
PRIVILEGED = {"Global Administrator"}
TOXIC_PAIRS = [("Payment Creator", "Payment Approver")]

def _read(name):
    with open(DATA / name) as f:
        return list(csv.DictReader(f))

def _days(d):
    return (TODAY - date.fromisoformat(d)).days if d else None

def _hr():
    return {r["user_id"]: r for r in _read("hr_records.csv")}

def find_ghost_accounts() -> dict:
    """Find ghost accounts: leavers whose account is still enabled, and enabled accounts with no sign-in for 90+ days."""
    hr, ghosts = _hr(), []
    for u in _read("users.csv"):
        if u["account_status"] != "Enabled":
            continue
        h = hr.get(u["user_id"], {})
        if h.get("employment_status") == "Leaver":
            ghosts.append({**u, "reason": "Leaver with enabled account", "days_since_leaving": _days(h["leave_date"]), "severity": "High"})
        elif _days(u["last_sign_in"]) >= STALE_DAYS:
            ghosts.append({**u, "reason": f"No sign-in for {_days(u['last_sign_in'])} days", "severity": "Medium"})
    return {"count": len(ghosts), "ghosts": ghosts}

def find_zombie_licences() -> dict:
    """Find zombie licences: paid licences assigned to leavers/disabled users or unused for 60+ days. Returns annual waste in GBP."""
    hr = _hr(); users = {u["user_id"]: u for u in _read("users.csv")}
    zombies = []
    for l in _read("licences.csv"):
        u, h = users[l["user_id"]], hr[l["user_id"]]
        reason = None
        if h["employment_status"] == "Leaver" or u["account_status"] == "Disabled":
            reason = "Assigned to leaver or disabled account"
        elif _days(l["last_used"]) >= UNUSED_LICENCE_DAYS:
            reason = f"Unused for {_days(l['last_used'])} days"
        if reason:
            zombies.append({**l, "display_name": u["display_name"], "reason": reason,
                            "annual_cost_gbp": round(float(l["monthly_cost_gbp"]) * 12, 2)})
    return {"count": len(zombies), "annual_waste_gbp": round(sum(z["annual_cost_gbp"] for z in zombies), 2), "zombies": zombies}

def find_risky_roles() -> dict:
    """Find risky access: privileged roles held by leavers/stale accounts, and toxic role combinations (segregation of duties)."""
    hr = _hr(); users = {u["user_id"]: u for u in _read("users.csv")}
    by_user = {}
    for r in _read("role_assignments.csv"):
        by_user.setdefault(r["user_id"], set()).add(r["role"])
    risks = []
    for uid, rs in by_user.items():
        u = users[uid]
        stale = hr[uid]["employment_status"] == "Leaver" or _days(u["last_sign_in"]) >= STALE_DAYS
        for role in rs & PRIVILEGED:
            if stale and u["account_status"] == "Enabled":
                risks.append({"user_id": uid, "display_name": u["display_name"], "role": role,
                              "reason": "Privileged role on ghost/stale account", "severity": "Critical"})
            elif u["department"] != "IT":
                risks.append({"user_id": uid, "display_name": u["display_name"], "role": role,
                              "reason": f"Privileged role outside IT ({u['department']})", "severity": "High"})
        for a, b in TOXIC_PAIRS:
            if {a, b} <= rs:
                risks.append({"user_id": uid, "display_name": u["display_name"], "role": f"{a} + {b}",
                              "reason": "Toxic combination: can create AND approve payments", "severity": "High"})
    return {"count": len(risks), "risks": risks}

SEVERITY_POINTS = {"Critical": 40, "High": 25, "Medium": 10}

def build_removal_plan() -> dict:
    """Combine all findings into a prioritised removal plan with a 0-100 risk score per user. Saves output/plan.json. Changes NOTHING."""
    g, z, r = find_ghost_accounts(), find_zombie_licences(), find_risky_roles()
    plan = {}
    def item(uid, name):
        return plan.setdefault(uid, {"user_id": uid, "display_name": name, "actions": [], "risk_score": 0, "annual_saving_gbp": 0.0})
    for x in g["ghosts"]:
        p = item(x["user_id"], x["display_name"]); p["actions"].append(f"Disable account ({x['reason']})")
        p["risk_score"] += SEVERITY_POINTS[x["severity"]]
    for x in r["risks"]:
        p = item(x["user_id"], x["display_name"]); p["actions"].append(f"Remove role '{x['role']}' ({x['reason']})")
        p["risk_score"] += SEVERITY_POINTS[x["severity"]]
    for x in z["zombies"]:
        p = item(x["user_id"], x["display_name"]); p["actions"].append(f"Reclaim licence '{x['sku']}' ({x['reason']})")
        p["risk_score"] += 5; p["annual_saving_gbp"] += x["annual_cost_gbp"]
    items = sorted(plan.values(), key=lambda p: -p["risk_score"])
    for p in items:
        p["risk_score"] = min(p["risk_score"], 100); p["annual_saving_gbp"] = round(p["annual_saving_gbp"], 2)
    result = {"plan_id": "PLAN-" + uuid.uuid4().hex[:6].upper(), "created": datetime.now().isoformat(timespec="seconds"),
              "status": "PENDING_APPROVAL", "users_affected": len(items),
              "total_actions": sum(len(p["actions"]) for p in items),
              "ghost_accounts": g["count"], "zombie_licences": z["count"], "risky_roles": r["count"],
              "annual_saving_gbp": z["annual_waste_gbp"], "items": items}
    (OUT / "plan.json").write_text(json.dumps(result, indent=2))
    return {k: v for k, v in result.items() if k != "items"} | {"top_10": items[:10]}

def execute_removal_plan(plan_id: str, approval_phrase: str) -> dict:
    """DRY RUN ONLY. Simulates executing the approved removal plan and writes every action to output/audit_log.jsonl.
    approval_phrase must be copied EXACTLY from the human's message and must equal 'APPROVE <plan_id>'."""
    if approval_phrase.strip() != f"APPROVE {plan_id}":
        return {"status": "blocked", "message": f"Human approval missing. Ask the user to type exactly: APPROVE {plan_id}"}
    plan = json.loads((OUT / "plan.json").read_text())
    if plan["plan_id"] != plan_id:
        return {"status": "error", "message": f"Plan {plan_id} not found. Latest plan is {plan['plan_id']}."}
    with open(OUT / "audit_log.jsonl", "a") as log:
        for p in plan["items"]:
            for a in p["actions"]:
                log.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "plan_id": plan_id,
                                      "user_id": p["user_id"], "action": a, "mode": "DRY_RUN", "approved_by": "human"}) + "\n")
    plan["status"] = "EXECUTED_DRY_RUN"; (OUT / "plan.json").write_text(json.dumps(plan, indent=2))
    return {"status": "ok", "mode": "DRY_RUN", "actions_logged": plan["total_actions"], "audit_log": "output/audit_log.jsonl"}

def generate_report() -> dict:
    """Write a Markdown report of the latest plan to output/ghost_report.md."""
    plan = json.loads((OUT / "plan.json").read_text())
    lines = [f"# Ghost Hunter report ({plan['plan_id']})", "",
             f"Status: **{plan['status']}**  |  Generated: {plan['created']}", "",
             "| Metric | Value |", "|---|---|",
             f"| Ghost accounts | {plan['ghost_accounts']} |", f"| Zombie licences | {plan['zombie_licences']} |",
             f"| Risky role assignments | {plan['risky_roles']} |", f"| Users affected | {plan['users_affected']} |",
             f"| Annual saving | £{plan['annual_saving_gbp']:,.2f} |", "", "## Prioritised actions", "",
             "| Risk | User | Actions | Saving/yr |", "|---|---|---|---|"]
    for p in plan["items"]:
        lines.append(f"| {p['risk_score']} | {p['display_name']} ({p['user_id']}) | {'<br>'.join(p['actions'])} | £{p['annual_saving_gbp']:,.2f} |")
    (OUT / "ghost_report.md").write_text("\n".join(lines))
    return {"status": "ok", "report": "output/ghost_report.md"}
