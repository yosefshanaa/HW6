# PRD — Bonus Inter-Group Match

**Mechanism PRD** (per submission guidelines §2.3). **Version:** 1.00.
**Parent:** [`PRD.md` §14](PRD.md#14-bonus-match-requirements) · **Shared spec:**
[`../SHARED_MATCH_RULES.md`](../SHARED_MATCH_RULES.md) · **Source:** assignment §12.

> **Framing:** the two teams are **friends**. This is a co-written shared spec so both systems
> interoperate — **not** an adversarial contract. Coordinate; don't police.

---

## 1. Description & Theoretical Background

The optional bonus is a friendly cloud match between two teams, worth up to **10 points** toward the
final project (playable within one week of publication). Each team runs its own pair of MCP servers;
the two systems connect over HTTPS and play a cross-team series. The assignment fixes the *scoring*
and *role split* but leaves the *operational protocol* open — so the two teams agree the open choices
in `SHARED_MATCH_RULES.md` and build against that single spec.

---

## 2. Specific Requirements

### 2.1 Series structure (fixed)
- Full series = **6 sub-games**.
- Sub-games **1–3:** Team A **Cop** vs Team B **Thief**.
- Sub-games **4–6:** Team B **Cop** vs Team A **Thief**.

### 2.2 Bonus scoring (fixed)
- Higher series total → **10**; the other team → **7**; exact tie → **5 each**.
- Final bonus = **average over all valid series** (e.g., 10 and 7 → 8.5). Playing multiple teams is
  allowed and encouraged.
- **Both teams must email identical JSON with `mutual_agreement: true`. Any mismatch voids the bonus
  (0/0 for that series.)**

### 2.3 Interoperability (agreed in the shared spec)
- **Coordinates:** `[row, col]`, origin `[0,0]` top-left.
- **Turn envelope:** free `message` (may bluff) + structured `action`; the **action** is
  authoritative.
- **Referee authority:** a single referee owns state. Default: the **Cop-side engine is referee** for
  its sub-games; the other side mirrors and flags mismatches. (Or one shared referee for all 6.)
- **Vision radius:** default 2 (king-move); both teams may agree on 3.
- **Start positions:** shared seed (announced beforehand) or fixed; outside each other's radius;
  never same cell.
- **Per-turn timeout:** default 30 s; timeout → concede the sub-game (or one re-prompt then concede).
- **Illegal action:** that sub-game goes to the other side; note it so the bug gets fixed.
- **Move counting:** "25 moves" = 25 Thief moves; the Cop's reply is its last capture chance.

### 2.4 Transport & fair play
- **HTTPS only.** Exchange the four MCP URLs (A-cop, A-thief, B-cop, B-thief) **out of band**.
- Each side issues the other a **token** (out of band) for the `Authorization` header; **revoke**
  after the match.
- Stay under ~**30 requests/min per direction**; retry transient errors a few times.
- Keep **full timestamped logs** of every message and action; swap logs afterward for joint
  debugging.
- Keep `message`s well-formed even when bluffing — don't crash the friends' server by accident.

### 2.5 Technical hiccups
- A drop / network glitch mid-sub-game is a **Technical Loss**: void and re-run until there are
  **6 clean sub-games**; a few retries, then pick a new time slot.

### 2.6 Matching report
- After 6 clean sub-games, the teams **compare results**, agree per-sub-game outcomes and totals,
  **then** each team emails its own copy with identical `sub_games`, `totals_by_group`,
  `bonus_claim`, `mutual_agreement: true` (the §9.2 JSON).

---

## 3. Input / Output / Performance

| | Spec |
|---|---|
| **Input** | Partner's 4 MCP URLs + tokens; agreed shared-spec choices; shared seed |
| **Output** | A bonus `MatchReport` (§9.2) emailed identically by both teams |
| **Rate** | ~30 req/min per direction (gatekeeper-enforced both ways) |
| **Reliability** | Technical-Loss rerun to 6 clean sub-games |

---

## 4. Constraints, Alternatives & Decisions

- **Decision:** Cop-side engine is referee per sub-game (default in shared spec); the other side
  mirrors and flags. Avoids a single point of ownership disputes while keeping one authority per
  sub-game.
- **Alternative — one shared referee process for all 6:** allowed if both teams prefer it (simpler
  authority, requires one team to host it).
- **Constraint:** the matching-JSON requirement is strict — a single mismatched field voids the
  bonus, so both teams reconcile before sending.
- **Constraint:** friendly framing — no anti-cheat/forfeit tone; bluffing-in-`message` is the fun
  part, payloads stay well-formed.

---

## 5. Success Criteria & Test Scenarios

**Success:** a cross-team series of 6 clean sub-games runs over HTTPS+token; both teams produce
identical §9.2 JSON with `mutual_agreement: true`; bonus computed as the average over valid series.

| # | Scenario | Expected |
|---|---|---|
| T1 | Connect to partner MCP URLs with token | Authorized; `health_check` OK both ways |
| T2 | Role split across 6 sub-games | 1–3 A-Cop/B-Thief, 4–6 B-Cop/A-Thief |
| T3 | Coordinate/rule mismatch | Mirror side flags it; teams reconcile (not a silent break) |
| T4 | Network drop mid-sub-game | Technical Loss → rerun to 6 clean |
| T5 | Reports compared then sent | Identical agreed fields; `mutual_agreement: true` |
| T6 | Intentional field mismatch (negative test) | Recognized as bonus-voiding before send |
| T7 | Rate handshake | Neither side exceeds ~30 req/min/direction |
