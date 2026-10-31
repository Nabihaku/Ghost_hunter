import os
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools import FunctionTool
from google.adk.tools.agent_tool import AgentTool
from . import tools as t

MODEL = os.getenv("GHOST_MODEL", "gemini-3.5-flash")
# Key 1: ADK confirmation pop-up (set GHOST_CONFIRM_POPUP=0 if it misbehaves in your ADK version)
CONFIRM_POPUP = os.getenv("GHOST_CONFIRM_POPUP", "1") == "1"

# 1) Three specialist hunters run IN PARALLEL, each with one deterministic tool
ghost_detector = LlmAgent(
    name="GhostDetector", model=MODEL, tools=[t.find_ghost_accounts], output_key="ghost_findings",
    instruction="Call find_ghost_accounts. Summarise the count and list the High severity ghosts first (name, id, reason). Be concise.")
licence_reaper = LlmAgent(
    name="LicenceReaper", model=MODEL, tools=[t.find_zombie_licences], output_key="licence_findings",
    instruction="Call find_zombie_licences. Report the count and total annual waste in GBP, then the 5 most expensive zombies.")
privilege_watcher = LlmAgent(
    name="PrivilegeWatcher", model=MODEL, tools=[t.find_risky_roles], output_key="role_findings",
    instruction="Call find_risky_roles. Report Critical risks first, then toxic combinations, then other High risks.")

hunt_party = ParallelAgent(name="HuntParty", sub_agents=[ghost_detector, licence_reaper, privilege_watcher],
                           description="Runs the three hunters at the same time.")

# 2) Planner merges findings into a scored plan (still changes nothing)
planner = LlmAgent(
    name="ExorcismPlanner", model=MODEL, tools=[t.build_removal_plan], output_key="plan_summary",
    instruction="""You receive findings from three hunters:
Ghosts: {ghost_findings}
Licences: {licence_findings}
Roles: {role_findings}
Call build_removal_plan. Then present: plan_id, headline numbers (ghosts, zombie licences, risky roles,
annual saving in GBP), and the top 5 users by risk score with their actions. State clearly that NOTHING
has been changed yet and the plan is PENDING_APPROVAL.""")

scan_pipeline = SequentialAgent(name="ScanPipeline", sub_agents=[hunt_party, planner],
                                description="Scans identity data and returns a pending removal plan.")

# 3) Root coordinator: talks to the human and owns the approval gate
root_agent = LlmAgent(
    name="GhostHunter", model=MODEL,
    description="Finds ghost accounts, zombie licences and risky access, then proposes a safe clean-up plan.",
    instruction="""You are Ghost Hunter, an identity-hygiene agent for IT and security teams. Spooky tone is fine but stay professional.
- When the user asks to scan / hunt, call the ScanPipeline tool and present its result clearly.
- After presenting a plan, tell the user: to proceed, type exactly "APPROVE <plan_id>".
- Only call execute_removal_plan when the user's latest message contains that phrase. Pass plan_id and
  approval_phrase copied word-for-word from the user's message. Never type the phrase yourself.
  Everything is DRY RUN: nothing real is changed, every action goes to an audit log.
- After execution or when asked, call generate_report and tell the user where the report is.
- All data is synthetic. Do not invent findings; only use tool results.""",
    tools=[AgentTool(agent=scan_pipeline),
           FunctionTool(t.execute_removal_plan, require_confirmation=CONFIRM_POPUP),  # Key 2: typed approval phrase inside the tool
           t.generate_report])
