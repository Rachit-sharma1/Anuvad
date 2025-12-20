<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# directly give me the prompts

Here are the prompts directly, ready to paste into an AI editor.

***

## Master System-Generation Prompt

```markdown
# Complete Government Welfare Scheme Eligibility Assistant

## Project Brief
Create a PRODUCTION-READY voice-first, agentic AI system that helps Indian citizens identify and apply for government welfare schemes. The system must be multilingual (at least Hindi + Marathi + Telugu + Tamil + Bengali), use a Planner–Executor–Evaluator agent loop, and integrate with structured data about government schemes so it can both check eligibility and guide users through actual application steps.

The assistant should support:
- Voice input/output
- Indic language understanding
- Eligibility calculation
- Application guidance with official links
- Step-by-step, conversational help

---

## Core Functional Requirements

### 1. Voice-first interface
- Accept microphone audio from the browser or mobile.
- Use a speech-to-text API (e.g., Google Cloud Speech-to-Text or any equivalent) for:
  - Hindi, Marathi, Telugu, Tamil, Bengali (at minimum).
- Use a text-to-speech API (e.g., Google Cloud Text-to-Speech or equivalent) to reply in the same language as the user.
- Handle:
  - Noisy audio
  - Low volume
  - User speaking in mixed Hindi–English or local language–English.

Deliverables:
- `speech_service.py` (or similar) for STT + TTS.
- Frontend JS to capture audio and play back speech.

---

### 2. Agentic Planner–Executor–Evaluator loop

Implement a clear loop with three roles:

**Planner**
- Input: user message (in any supported language) + current user profile + conversation history.
- Output: strict JSON with fields:
  - `user_intent`: string
  - `language`: detected language code
  - `missing_info`: list of questions to ask
  - `next_steps`: ordered list of high-level actions
  - `tools_needed`: array of tool names (see below)
  - `priority_schemes_hint`: list of scheme categories to consider (e.g. `["farmer", "women", "student"]`)
  - `reasoning`: short natural-language explanation (for logging, not shown to user).

**Executor**
- Has access to tools such as:
  - `check_eligibility(user_profile, schemes_db) → list[SchemeMatch]`
  - `fetch_schemes(filter_params) → list[Scheme]`
  - `verify_documents(scheme_id, user_profile) → {required, missing, optional}`
  - `search_application_links(scheme_id, state) → URLs + metadata`
  - `calculate_benefits(scheme_id, user_profile) → numeric + explanation`
- Follows `next_steps` and `tools_needed` from Planner.
- Handles tool errors and timeouts gracefully.
- Returns structured JSON for Evaluator, including:
  - `executed_tools`: list of tool call logs
  - `scheme_matches`: list sorted by relevance
  - `warnings`: any data issues (missing, conflicting)

**Evaluator**
- Input: Planner output + Executor output.
- Output:
  - Natural language answer in the user’s language.
  - Sections:
    - Summary of 2–3 best schemes.
    - Why each scheme is recommended.
    - Eligibility verdict (eligible / likely eligible / not eligible / unclear).
    - Missing information user must provide.
    - Required documents.
    - Step-by-step application instructions.
    - Official URLs and offline office details where possible.
    - Suggested next action (“Today you should do X…”).
- Must handle partial data and be explicit about uncertainties.

Deliverables:
- `agent.py` (or similar) implementing Planner, Executor, Evaluator classes.
- Clear function boundaries with type hints.

---

### 3. Multilingual & Indic support

Requirements:
- Understand and respond in:
  - Hindi, Marathi, Telugu, Tamil, Bengali (more languages welcome).
- Detect language automatically from user input.
- Support code-switching (mixture of English + local language).
- Translate scheme names, descriptions, and steps into the user’s language.
- Keep official scheme names also in English when appropriate, e.g.:
  - “प्रधान मंत्री किसान सम्मान निधि (PM-KISAN)”

Deliverables:
- Language detection utility.
- Translation layer or prompts that instruct the LLM to:
  - Answer in user’s language.
  - Preserve official scheme names.

---

### 4. Government schemes knowledge base

Create or assume a structured schemes database with at least these central schemes (you may add more):

**Employment / Livelihood**
- MGNREGA – Mahatma Gandhi National Rural Employment Guarantee Act
- PMKVY – Pradhan Mantri Kaushal Vikas Yojana
- PMEGP – Prime Minister’s Employment Generation Programme

**Farmer / Agriculture**
- PM-KISAN – Pradhan Mantri Kisan Samman Nidhi
- PMFBY – Pradhan Mantri Fasal Bima Yojana
- KCC – Kisan Credit Card (if included)

**Health / Insurance**
- PM-JAY – Ayushman Bharat Pradhan Mantri Jan Arogya Yojana
- PMJJBY – Pradhan Mantri Jeevan Jyoti Bima Yojana
- PMSBY – Pradhan Mantri Suraksha Bima Yojana

**Housing / Basic Amenities**
- PMAY – Pradhan Mantri Awas Yojana (Urban + Gramin)
- Ujjwala – Pradhan Mantri Ujjwala Yojana (LPG)

**Education / Students**
- Central and state scholarship schemes (National Scholarship Portal)
- SWAYAM or similar online learning schemes

For each scheme, store at least:
- `id`
- `name`
- `category` (farmer, woman, student, senior citizen, unemployed, etc.)
- `central_or_state`
- `states_applicable`
- `eligibility_criteria` (age, income, occupation, landholding, gender, caste reservation if relevant, disability, etc.)
- `benefits` (amounts, frequency, nature of benefit)
- `required_documents`
- `official_portal_url`
- `offline_application_info` (offices, centers)
- `language_specific_notes` (for different states / languages)

Deliverables:
- `schemes.json` (or similar, machine-readable).
- A small in-code sample but designed so it can be extended.

---

### 5. Eligibility engine

Implement an eligibility engine that:
- Takes a `user_profile`:
```

{
"age": 35,
"gender": "female",
"occupation": "farmer",
"annual_income": 250000,
"state": "Maharashtra",
"district": "Pune",
"land_holding_hectares": 1.5,
"education_level": "10th_pass",
"bpl": true,
"disability": false,
"caste": "OBC",
"has_aadhaar": true,
"has_bank_account": true,
"rural_or_urban": "rural"
}

```
- Computes for each scheme:
- `match_score` (0–100)
- `is_clearly_eligible` (bool)
- `is_clearly_ineligible` (bool)
- `uncertain` (bool + explanation)
- `missing_fields` (list of profile fields needed)
- Ranks schemes by:
- Eligibility
- Benefit value
- Simplicity of application (if encoded)

Deliverables:
- `eligibility_engine.py` (or integrated module).
- Pure functions so it can be unit-tested.

---

### 6. Application assistance & guidance

For each recommended scheme in the final answer, the system should:
- Name the scheme (local language + official name).
- Explain benefits in simple words.
- List required documents and typical places to get them.
- Provide a clear step-by-step application flow:
- Online steps (portal, register, log in, fill form, upload documents).
- Offline steps (visit office, fill form, attach photocopies).
- Provide:
- Official URL(s).
- Relevant helpline numbers if available.
- Typical processing time and what to expect next.

Deliverables:
- Formatting functions to generate:
- Bullet-point checklists.
- Numbered steps.
- Prompts or logic that force structured, actionable answers.

---

### 7. Conversation memory & context

The system must:
- Maintain per-user conversation state (in memory or Firestore-like DB), including:
- User profile fields collected so far.
- Last few recommended schemes.
- Previous clarifications.
- On each new user query:
- Reuse stored profile where possible.
- Ask only for missing or inconsistent info.
- Avoid repeating questions unnecessarily.

Deliverables:
- Simple `ConversationState` abstraction (could wrap a DB).
- Hooks in `agent.py` to read/write state.

---

### 8. Error handling & edge cases

Handle at least:
- User gives incomplete info (“मुझे कोई योजना बताओ बस”).
- Conflicting info (“मैं बेरोजगार हूं” + “मेरी सैलरी 50,000 है”).
- Out-of-scope queries (non-scheme questions).
- STT errors (empty or garbled transcript).
- Scheme data missing or outdated.

Behavior:
- Ask polite clarification questions.
- Label things as “likely” or “uncertain” if not sure.
- Never hallucinate fake official URLs; if not certain, say so and recommend checking official portals or CSC centers.

---

## Technical Architecture Requirements

You are free to choose exact libraries, but the default target is:

- Backend language: Python 3.9+
- LLM access: via GroqCloud (e.g., Llama 3.3 70B) for heavy reasoning + ability to plug in local models (such as Sarvam-1) for Indic language fluency.
- Speech: Google Cloud Speech-to-Text + Text-to-Speech or equivalent.
- Persistence: Firestore-like NoSQL DB or a simple DB abstraction.
- Deployment target: Serverless HTTP endpoint compatible with Firebase Cloud Functions or any similar FaaS.

Deliverables:
- Backend folder with:
- `agent.py`
- `eligibility_engine.py`
- `schemes_db.py` or JSON
- `speech_service.py`
- `main.py` HTTP entrypoint
- `requirements.txt`
- Frontend folder with:
- `index.html` (mic UI + results)
- `app.js` (audio capture, API calls)
- `styles.css` (basic styling)

---

## Output Expectations

Generate:

1. **Complete backend code**:
 - All Python modules listed above.
 - Clean, production-style code with:
   - Type hints
   - Docstrings
   - Error handling
   - Logging hooks

2. **Example schemes database**:
 - At least 15–20 real schemes with realistic fields.
 - Easy to extend.

3. **Frontend**:
 - HTML + JS to:
   - Record audio
   - Send to backend
   - Play back TTS audio
   - Show text transcript + scheme recommendations

4. **README**:
 - Setup steps.
 - Environment variables.
 - How to run locally.
 - How to deploy.

5. **Test cases**:
 - Minimal tests for eligibility engine.
 - A few example user profiles and expected scheme outputs.

Important:
- Do NOT leave TODOs or placeholders.
- Prefer simple, robust designs over extremely complex ones.
- Make it easy for a single developer to run this on a laptop plus GroqCloud.
```


***

## Database-Generation Prompt (Schemes JSON)

```markdown
Generate a JSON file `schemes.json` containing at least 20 Indian government welfare schemes.

For each `scheme`, include:
- `id` (short slug, e.g. "pmkisan")
- `name_en`
- `name_hi`
- `name_mr`
- `name_te`
- `name_ta`
- `category` (one of: farmer, employment, women, student, senior_citizen, health, housing, social_security)
- `central_or_state` ("central" or specific state)
- `states_applicable` (array of state names)
- `short_description_en`
- `short_description_hi`
- `eligibility`:
  - `min_age`
  - `max_age`
  - `min_income`
  - `max_income`
  - `required_occupation` (array or null)
  - `required_rural_urban` ("rural" / "urban" / "any")
  - `requires_bpl` (bool or null)
  - `requires_female` (bool or null)
  - `requires_farmer` (bool or null)
  - `other_conditions` (free text)
- `benefits`:
  - `type` ("cash_transfer" | "insurance" | "subsidy" | "training" | "loan" | "other")
  - `amount_per_year` (if applicable)
  - `frequency` ("monthly" | "yearly" | "one_time" | null)
  - `notes_en`
- `required_documents`:
  - array of objects: `{ "name": "Aadhaar", "mandatory": true, "notes_en": "..." }`
- `official_portal`:
  - `url`
  - `notes_en`
- `offline_application`:
  - `available` (bool)
  - `where_to_apply_en` (e.g. CSC, Gram Panchayat, Block office)
  - `notes_en`

Cover at least:
- PM-KISAN, PMFBY, PMJJBY, PMSBY, PMAY, Ujjwala, PMEGP, PMKVY, MGNREGA, PM-JAY
- A few state-specific schemes (e.g., for Maharashtra, Tamil Nadu, Telangana, West Bengal).

Return **only valid JSON** (no comments, no markdown).
```


***

## Planner Prompt (for the LLM inside your system)

```markdown
You are the PLANNER component of a government welfare scheme assistant for India.

Your job:
- Read the user message and the current user profile.
- Decide what information is missing.
- Decide which tools need to be called.
- Produce a machine-readable PLAN as JSON.

Always respond with **ONLY JSON**, no extra text.

JSON format:
```

{
"user_intent": "short one-line summary in English",
"language": "detected_language_code_like_hi_mr_te_ta_bn_en",
"missing_info": [
"question to ask the user in their language if some key field is missing"
],
"next_steps": [
"high-level step 1",
"high-level step 2"
],
"tools_needed": [
"check_eligibility",
"fetch_schemes",
"verify_documents"
],
"priority_scheme_categories": [
"farmer",
"women",
"student"
],
"reasoning": "short explanation in English for logging (not shown to user)"
}

```

Rules:
- Detect user language from the last message.
- Set `language` accordingly (e.g., `hi`, `mr`, `te`, `ta`, `bn`, `en`).
- If key fields like age, state, occupation, income are missing, add human-friendly questions in `missing_info` in the **user’s language**.
- If user explicitly mentions “farmer”, include `"farmer"` in `priority_scheme_categories`.
- If they ask “how to apply” for a specific scheme, set `tools_needed` to at least include `fetch_schemes`, `verify_documents`, `search_application_links`.
- Never propose tools that do not exist.

If the user message is off-topic (not about schemes), set:
- `user_intent` to `"non_scheme_query"`,
- `tools_needed` to `[]`,
- and suggest asking a scheme-related question in `missing_info`.
```


***

## Eligibility Engine Prompt (if using LLM for logic instead of pure code)

```markdown
You are the ELIGIBILITY ENGINE for Indian government schemes.

Input:
1. `user_profile` JSON
2. `schemes` JSON array
3. Optional `priority_scheme_categories` from Planner

Task:
For each scheme, compute:
- `match_score` from 0 to 100 (higher = better fit)
- `eligibility_label`: one of `"eligible"`, `"likely_eligible"`, `"uncertain"`, `"likely_ineligible"`, `"ineligible"`
- `missing_fields`: list of profile fields that must be clarified
- `explanation`: short English explanation for why it got this label

Rules:
- If mandatory conditions clearly fail (e.g., age too low, income too high), mark `"ineligible"`.
- If all key conditions match strongly, mark `"eligible"`.
- If some important data is missing (e.g., income not provided), mark `"uncertain"` and list missing fields.
- If it seems likely but some minor info is missing, use `"likely_eligible"`.

Output format:
```

[
{
"scheme_id": "pmkisan",
"match_score": 92,
"eligibility_label": "eligible",
"missing_fields": [],
"explanation": "User is a small farmer in a covered state with landholding within limits."
}
]

```

Return **only valid JSON** (no prose).
```


***

If you want, a very short “do it all” instruction for the AI editor is:

```markdown
Use the Master System-Generation Prompt above. Generate:
1) `agent.py` with Planner–Executor–Evaluator,
2) `eligibility_engine.py`,
3) `schemes.json` (using the DB prompt),
4) `speech_service.py`,
5) `main.py` HTTP endpoint,
6) minimal `index.html` + `app.js`,
all production-ready, no TODOs.
```

<span style="display:none">[^1][^10][^11][^12][^13][^14][^15][^16][^17][^18][^19][^2][^20][^21][^22][^23][^24][^25][^26][^27][^28][^29][^3][^30][^31][^32][^33][^34][^35][^36][^37][^38][^4][^5][^6][^7][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://ieeexplore.ieee.org/document/10724558/

[^2]: https://link.springer.com/10.1007/s12046-024-02520-0

[^3]: https://aclanthology.org/2021.acl-long.105

[^4]: https://aclanthology.org/2023.findings-emnlp.4

[^5]: https://ieeexplore.ieee.org/document/10627578/

[^6]: https://aclanthology.org/2025.wmt-1.102

[^7]: https://dl.acm.org/doi/10.1145/3605778

[^8]: https://aclanthology.org/2024.wmt-1.65

[^9]: https://www.semanticscholar.org/paper/2cef5b7c061a6241e6a5d890a0438dd617916942

[^10]: https://arxiv.org/abs/2508.06280

[^11]: https://arxiv.org/pdf/2203.16512.pdf

[^12]: http://arxiv.org/pdf/2401.18034.pdf

[^13]: https://arxiv.org/html/2403.01926v1

[^14]: https://arxiv.org/pdf/2104.05596.pdf

[^15]: http://arxiv.org/pdf/2403.06350.pdf

[^16]: https://arxiv.org/pdf/2212.05409.pdf

[^17]: https://arxiv.org/pdf/2005.00085.pdf

[^18]: http://arxiv.org/pdf/2203.05437v1.pdf

[^19]: https://www.sarvam.ai/blogs/sarvam-1

[^20]: https://huggingface.co/sarvamai/sarvam-1

[^21]: https://indiaai.gov.in/article/sarvam-ai-unveils-sarvam-1-optimized-language-model-for-indian-languages

[^22]: https://ai.icai.org/articles_details.php?id=132

[^23]: https://dataloop.ai/library/model/sarvamai_sarvam-1/

[^24]: https://www.crackedaiengineering.com/ai-models/groq-llama-3-3-70b-versatile

[^25]: https://cleartax.in/s/government-schemes-individuals

[^26]: https://indianexpress.com/article/technology/artificial-intelligence/what-is-sarvam-1-a-new-ai-model-optimised-for-10-indian-languages-9638492/

[^27]: https://blog.llmradar.ai/groq-llama-3-3-70b-versatile/

[^28]: https://www.ibef.org/economy/government-schemes

[^29]: https://www.sarvam.ai

[^30]: https://simtheory.ai/model-card/groq-llama-3.3-70b-versatile/

[^31]: https://financialservices.gov.in/beta/en/schemes-overview

[^32]: https://huggingface.co/sarvamai/sarvam-1/blob/main/README.md

[^33]: https://console.groq.com/docs/model/llama-3.3-70b-versatile

[^34]: https://byjus.com/govt-exams/government-schemes/

[^35]: https://aikosha.indiaai.gov.in/home/models/details/sarvam1.html

[^36]: https://groq.com/blog/a-new-scaling-paradigm-metas-llama-3-3-70b-challenges-death-of-scaling-law

[^37]: https://en.wikipedia.org/wiki/List_of_schemes_of_the_government_of_India

[^38]: https://www.gktoday.in/sarvam-ai-launches-new-language-model-for-indian-languages/

