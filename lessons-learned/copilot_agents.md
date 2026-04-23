# SKILL: Copilot Studio Agent Builder
# File: skills/copilot_agents.md
# Version: 1.0
# Created: 2026-04-22
# Origin: Scout Motors Procurement Bot build (LL-CS-001 through LL-CS-021)
# Applicable buckets: scout, business/freelance
# Productizable: Yes — $3-8k per bot build + $500/month maintenance

---

## 1. What This Skill Does

Designs, builds, tests, and deploys conversational AI agents on Microsoft Copilot Studio (or equivalent low-code platforms). Takes a broken/undocumented business process and turns it into a self-service bot that guides users step-by-step with clickable options, structured data collection, and knowledge base Q&A.

**Not a chatbot.** A structured process guide with conversational fallback.

---

## 2. When to Invoke This Skill

- Client has a business process that users struggle to follow
- Process documentation exists but nobody reads it
- Users repeatedly ask the same questions to the same people
- The process has sequential steps with decision points
- Client uses Microsoft 365 / Teams ecosystem

---

## 3. Inputs Required

Before starting, collect:

```
INTAKE CHECKLIST:
□ Process owner name and role
□ Who are the end users? (job titles, technical level)
□ What is the process? (name, purpose, frequency)
□ Where is the current documentation? (Confluence, SharePoint, PDFs, someone's head)
□ What systems are involved? (Ivalua, SAP, Jira, etc.)
□ What are the pain points? ("where do people get stuck?")
□ Who has M365 Copilot licenses?
□ Who approves publishing? (IT admin, team lead)
□ Is this private (team only) or org-wide?
□ What channels? (Teams, M365 Copilot, both)
```

---

## 4. Process — 6 Phases

### Phase 0: Discovery (1-2 hours)

**Goal:** Understand the actual process, not the documented one.

1. Meet with the process SME (Subject Matter Expert)
2. Record or take detailed notes — the SME knows things that aren't documented
3. Map the process end-to-end: every step, every decision point, every handoff
4. Identify the **shadow processes** — manual steps that aren't in any documentation but are required
5. Identify every URL, email address, form, and system the user touches
6. Ask: "Where do people get stuck?" — that's where the bot adds the most value

**Output:** Process map (can be informal — bullet list or flow diagram)

**CRITICAL RULE:** Verify every URL and email address against source documents. LLMs will hallucinate plausible-sounding addresses. Maintain a verified contacts list. See LL-CS-009.

### Phase 1: Knowledge Base Architecture (2-4 hours)

**Goal:** Structure the process documentation so the LLM can answer questions accurately.

**Architecture decision — fewer, larger files:**
- 3-5 markdown files grouped by domain (not by step)
- Each file is self-contained — no cross-file references
- See LL-CS-021: 3 large files > 15 small ones for RAG retrieval

**Standard file structure:**
```
01_PROCESS_GUIDE.md    — End-to-end process, every step, every URL
02_CONTACTS.md         — All contacts, emails, system URLs, templates
03_RULES.md            — Thresholds, policies, compliance requirements
04_AGENT_INSTRUCTIONS.md — System prompt + starter prompts (under 8K chars)
```

**Writing rules for knowledge files:**
- Written for someone who has never seen the system (LL-CS-010)
- Every acronym defined on first use
- No UI element references ("orange box", "workflow tab") — use plain language
- No internal cross-references between files
- Actual instructions, not references to external docs (LL-CS-011)
- Every URL must be verified against source documents
- Every email must be verified — flag any that seem auto-generated

**Agent Instructions (04):**
- Under 8,000 characters
- Include anti-hallucination rule: "NEVER invent or guess email addresses"
- Define 3-4 starter prompts that map to the most common user needs
- Set the tone: helpful, professional, no jargon

### Phase 2: Topic Design (2-4 hours)

**Goal:** Define the guided conversation flows for structured processes.

**When to use a Topic vs Knowledge Base:**
- **Topic:** Process with sequential steps, decision branches, or data collection. User needs to be guided, not just informed.
- **Knowledge Base:** One-off factual questions ("what's the threshold?", "who do I contact?"). LLM answers from knowledge files.

**Topic design principles:**

1. **One step per message.** Never dump multiple steps at once. Show one step, ask for confirmation, then show the next. (LL-CS-007)

2. **Every question has 3+ options.** Never use Boolean (Yes/No only). Always add a third option: "I'm not sure", "How do I check?", "What is this?". (LL-CS-008)

3. **Every "No" loops back.** When the user says No or needs help, show helpful context and loop back to the same question using GotoAction. Never dead-end the conversation. (LL-CS-007)

4. **Parallel tracks are surfaced early.** If multiple things can happen simultaneously (like NDA + BPDD + TPRM in procurement), tell the user upfront before starting the sequential steps.

5. **The completion message reminds about parallel items.** Don't assume the user tracked everything.

6. **IT-specific or role-specific steps use a Boolean gate.** Ask one question at the top ("Is this an IT purchase?") and use a condition to show/hide role-specific steps. Don't create separate topics for each role.

**Topic structure template:**
```
TOPIC: [Name]
TRIGGER: "The agent chooses" with aggressive description (15+ phrases)
  ↓
Gate Question (if needed): Role/type classification
  ↓
Step 0: Pre-requisite check
  ├── Confirmed → continue
  ├── Not done → provide links/instructions → GotoAction back
  ↓
Parallel Tracks Reminder (if applicable)
  ↓
Step 1: [Action] → provide URL/instructions
  Question: "Have you completed this?" → Yes/No/Help
  ├── Yes → continue
  ├── No → context + GotoAction back
  ├── Help → detailed instructions + GotoAction back
  ↓
Step 2-N: [Repeat pattern]
  ↓
Completion: Summary + parallel items reminder + next steps options
```

### Phase 3: Build in Copilot Studio (4-8 hours)

**Goal:** Implement topics, upload knowledge, configure agent.

**Build order:**
1. Create the agent in Copilot Studio
2. Upload knowledge files (markdown, embedded — not SharePoint for v1)
3. Set Agent Instructions
4. Set Starter Prompts (max 4, put top 3 first — only 3 show in M365 Copilot, see LL-CS-017)
5. Build the Greeting topic with Adaptive Card menu (see §5 Adaptive Cards below)
6. Build each custom topic from the YAML blueprints
7. Configure trigger descriptions for each topic
8. Test in Copilot Studio test panel

**Trigger configuration — critical rules:**

- Use **"The agent chooses"** for all custom topics (LL-CS-006)
- NEVER use **"A message is received"** for content topics — it intercepts everything
- Make trigger descriptions aggressive: "This topic handles ANY question about..."
- Include 15+ trigger phrase variations
- Explicitly state what the topic does NOT handle
- For the Greeting topic, explicitly exclude business topics: "Do NOT use for vendor, procurement, finance questions"

**Topic trigger description template:**
```
This topic handles ANY question about [domain]. Also handles: 
[phrase 1], [phrase 2], [phrase 3], [phrase 4], [phrase 5],
[phrase 6], [phrase 7], [phrase 8], [phrase 9], [phrase 10].
Do NOT use this topic for [other domain 1], [other domain 2].
```

**Variable naming convention:**
- Topic-scoped: `Topic.StepName` (e.g., `Topic.VWRegistration`, `Topic.DUNSNumber`)
- Use ClosedListEntity (Multiple Choice) not BooleanPrebuiltEntity for most questions
- Variable type for Adaptive Card outputs: define via Edit Schema in YAML format:
  ```yaml
  kind: Record
  properties:
    variableName:
      type: String
  ```

### Phase 4: Adaptive Cards (when needed)

**When to use Adaptive Cards:**
- More than 3 options needed (Teams caps quick reply buttons at 3) — LL-CS-002
- Data collection that needs a clean form layout
- Email assembly with "Open in Outlook" button
- Any display that needs variables inserted dynamically

**Critical rules — memorize these:**

1. **Interactive cards (with Submit):** Use **"Ask with Adaptive Card"** node, NOT Message node. Message nodes are display-only — buttons render but clicks do nothing. (LL-CS-001)

2. **Display-only cards (no Submit):** Use Message node with Adaptive Card.

3. **Dynamic variables:** Switch from JSON mode to **Formula (Power Fx)** mode. JSON mode treats everything as static text — variables won't substitute. (LL-CS-003)
   - Power Fx variable syntax: `Text(Topic.VariableName)`
   - URL encoding: `EncodeUrl(Text(Topic.VariableName))`

4. **Edit Schema for output variables:** Uses YAML format, not JSON. (LL-CS-004)
   ```yaml
   kind: Record
   properties:
     userChoice:
       type: String
   ```

5. **Mailto links with variables:** Use Power Fx Formula mode + EncodeUrl:
   ```
   "mailto:email@company.com?subject=" & EncodeUrl(Text(Topic.Subject)) & "&body=" & EncodeUrl(Text(Topic.Body))
   ```

6. **"Missing action submit button" error:** Copilot Studio requires at least one Action.Submit on interactive cards. If you only need Action.OpenUrl, add a "Done" submit button alongside it.

**Menu card pattern (for Greeting with 4+ options):**
```json
{
  "type": "AdaptiveCard",
  "version": "1.5",
  "body": [
    {
      "type": "TextBlock",
      "text": "What do you need help with?",
      "weight": "Bolder",
      "size": "Medium"
    },
    {
      "type": "Input.ChoiceSet",
      "id": "userChoice",
      "style": "expanded",
      "choices": [
        { "title": "Option 1", "value": "Option 1" },
        { "title": "Option 2", "value": "Option 2" },
        { "title": "Option 3", "value": "Option 3" },
        { "title": "Option 4", "value": "Option 4" },
        { "title": "Option 5", "value": "Option 5" }
      ]
    }
  ],
  "actions": [
    { "type": "Action.Submit", "title": "Go", "data": { "actionSubmitId": "menu_select" } }
  ]
}
```

### Phase 5: Testing & Publishing (2-4 hours)

**Testing protocol:**

1. **Test in Copilot Studio first** (instant updates, full visibility)
2. Test every topic end-to-end: every Yes path, every No path, every Help path
3. Test trigger routing: type messages that should trigger each topic — verify correct routing
4. Test knowledge base: ask questions that only the knowledge files can answer
5. Test out-of-scope: ask something unrelated — verify graceful fallback
6. Test edge cases: what happens with empty input, very long input, unexpected input
7. **Verify every URL and email** in the bot's responses — check against source docs

**Publishing checklist:**

```
□ All topics saved without errors (check Topic Checker)
□ Share settings confirmed: only specific viewers, NOT "Everyone in organization"
□ Screenshot the Share dialog as audit trail (LL-CS-015)
□ Publish with "Force newest version" checked
□ Wait 15-30 minutes for Teams/M365 propagation (LL-CS-012)
□ Send direct link to testers (bot won't appear in Agent Store search) (LL-CS-014)
□ Tell testers to start a NEW conversation (not continue old ones)
□ Create a Testing Guide document for testers
```

**Known platform limitations to communicate to stakeholders:**
- URLs may render as plain text in Teams (LL-CS-016). Use Adaptive Card Action.OpenUrl for critical links.
- M365 Copilot shows max 3 starter prompt cards on landing page (LL-CS-017)
- Teams channel may take 10-15 min to provision (LL-CS-013)
- Changes require re-publish + new conversation to take effect (LL-CS-012)

### Phase 6: Handoff & Closeout (1-2 hours)

**Deliverables to the client/stakeholder:**

1. Deployed bot accessible via direct link
2. Knowledge base files (markdown) — client owns these for future updates
3. Testing Guide with all paths documented
4. Agent Instructions document
5. Lessons Learned from the build

**Maintenance plan (if ongoing):**
- Knowledge files need updating when the process changes
- After every update: re-upload files → re-publish → "Force newest version"
- Monthly review: check bot analytics for unanswered questions → update knowledge or add topics
- Quarterly review: validate all URLs and email addresses still work

---

## 5. Outputs

| Deliverable | Format | Who owns it |
|-------------|--------|-------------|
| Deployed bot | Copilot Studio agent | Client's M365 tenant |
| Knowledge base files | 3-5 .md files | Client (editable) |
| Topic YAML blueprints | .yaml files | Builder (reference) |
| Agent Instructions | Text in Copilot Studio | Client (editable) |
| Testing Guide | .md file | Client |
| Lessons Learned | .yaml entries in LL-COPILOT-STUDIO.yaml | Builder's LL register |

---

## 6. Cost Estimation Template

| Component | Hours | Rate | Total |
|-----------|------:|-----:|------:|
| Phase 0: Discovery | 2 | $150 | $300 |
| Phase 1: Knowledge Base | 3 | $150 | $450 |
| Phase 2: Topic Design | 3 | $150 | $450 |
| Phase 3: Build | 6 | $150 | $900 |
| Phase 4: Adaptive Cards | 3 | $150 | $450 |
| Phase 5: Testing & Publishing | 3 | $150 | $450 |
| Phase 6: Handoff | 1 | $150 | $150 |
| **Total** | **21** | | **$3,150** |

Adjust based on complexity:
- Simple bot (3 topics, no Adaptive Cards): $2,000-3,000
- Medium bot (5 topics, Adaptive Cards, email integration): $3,000-5,000
- Complex bot (8+ topics, Power Automate, API integration): $5,000-8,000
- Monthly maintenance: $500/month (knowledge updates, URL verification, analytics review)

---

## 7. Anti-Patterns (from LL-CS register)

| Anti-Pattern | What Happens | Do This Instead |
|---|---|---|
| Adaptive Card in Message node | Buttons render but clicks do nothing | Use "Ask with Adaptive Card" node |
| More than 3 quick reply buttons | Only 3 show in Teams | Use Adaptive Card with Input.ChoiceSet |
| Boolean for diagnostic questions | User has no "I don't know" option | Use ClosedListEntity with 3+ options |
| "A message is received" trigger | Catches ALL messages, blocks other topics | Use "The agent chooses" with specific description |
| Weak trigger descriptions | Knowledge base overrides your topic | 15+ trigger phrases, explicit exclusions |
| Knowledge files with jargon | Users don't understand responses | Write for day-1 new hire level |
| References to external docs | LLM can't follow links | Include actual content in knowledge files |
| Publishing without "Force newest version" | Old bot keeps running for existing users | Always check Force + tell testers to start new chat |
| Trusting LLM-generated emails | Fake addresses that go nowhere | Verify every email against source documents |
| JSON mode for dynamic cards | Variables show as literal text | Switch to Formula (Power Fx) mode |
| Dead-end on "No" answers | User has to restart entire conversation | GotoAction loops back to same question |
| No audit trail for sharing | Can't prove bot is private when asked | Screenshot Share dialog before every publish |

---

## 8. Reference Implementation

The Scout Motors Procurement Bot (April 2026) is the reference implementation for this skill. It demonstrates:

- 5 custom topics (Greeting, Onboard New Vendor, My Request Is Stuck, Send Finance Email, What Do I Need)
- 3 knowledge base files (Process Guide, Contacts & Resources, Thresholds & Rules)
- Adaptive Card menu with 5 options (bypassing 3-button limit)
- Adaptive Card with Power Fx for dynamic email assembly + mailto link
- Step-by-step guided flow with confirmation at each step
- GotoAction loops on all "No" branches
- IT/non-IT gate question with conditional steps
- Parallel tracks awareness
- Anti-hallucination instructions for email addresses
- Private sharing with audit trail

**Lessons learned:** 21 entries in LL-COPILOT-STUDIO.yaml (LL-CS-001 through LL-CS-021)

---

## 9. Platform-Specific Notes

### Microsoft Copilot Studio (primary platform)
- All rules in this skill are based on Copilot Studio as of April 2026
- YAML blueprints are reference documents — cannot be imported directly into the visual editor (LL-CS-019)
- Build topics node-by-node in the visual editor following the YAML as blueprint

### Future platforms (adapt when needed)
- Dialogflow (Google): Different trigger system, no Adaptive Cards, uses Fulfillment webhooks
- Power Virtual Agents: Predecessor to Copilot Studio, similar patterns
- Amazon Lex: Different UI, same Topic/Intent pattern
- Custom (Rasa, Botpress): Full code control, no visual editor constraints
