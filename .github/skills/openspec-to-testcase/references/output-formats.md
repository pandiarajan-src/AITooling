# Output Formats

Exact markdown structure for all three output files. Follow precisely —
the xlsx generator parses these formats with known patterns.

---

## 1. `tests/<capability>/test-cases.md`

```markdown
---
capability: Project Capability or Domain
area: DOMN1
spec: specs/domain-or-capability-1/spec.md
generated: YYYY-MM-DD
---

# Test Cases — Project Capability or Domain

<!-- tc-count: 14 -->
<!-- req-coverage: REQ-DOMN1-001=Full, REQ-DOMN1-002=Full, REQ-DOMN1-003=Full -->

---

## TC-DOMN1-001-P — Install Noto Sans JP — successful download and install

| Field | Value |
|---|---|
| **TC ID** | TC-DOMN1-001-P |
| **REQ ID(s)** | REQ-DOMN1-003 |
| **Type** | P |
| **Priority** | High |
| **Automation** | Both |
| **Status** | Not Run |

**Description:**
Verify that Noto Sans JP can be successfully downloaded and installed on a supported device.

**Preconditions:**
- Device connected and recognised by the application
- Noto Sans JP not previously installed
- Network connection available

**Steps to Test:**
1. Open Project Tool.
2. Navigate to East Asian → Japanese.
3. Select "Noto Sans JP".
4. Click "Download & Install".
5. Observe the progress indicator.
6. Wait for the completion notification.

**Test Data:**
- File: Noto Sans JP
- Device: supported controller model
- Network: LAN connected

**Expected Result:**
File installs successfully. Status changes to "Installed". File appears in the installed files list. No error dialogs displayed.

**Actual Result:**
_[Fill at execution time]_

**Notes:**
_None_

---

## TC-DOMN1-001-N — Install files — network unavailable

| Field | Value |
|---|---|
| **TC ID** | TC-DOMN1-001-N |
| **REQ ID(s)** | REQ-DOMN1-003, REQ-NET-001 |
| **Type** | N |
| **Priority** | High |
| **Automation** | Both |
| **Status** | Not Run |

**Description:**
Verify the app handles a missing network connection gracefully during Project Capability or Domain.

**Preconditions:**
- Device connected
- Network disconnected before install attempt

**Steps to Test:**
1. Disable the network connection.
2. Open Project Tool.
3. Select any East Asian language files.
4. Click "Download & Install".
5. Observe error handling.

**Test Data:**
- File: East Asian language file
- Network: disconnected

**Expected Result:**
App displays a clear error: "Network unavailable. Please check your connection." No crash. No partial install artefact left on device.

**Actual Result:**
_[Fill at execution time]_

**Notes:**
_Requires network to be disabled before test step 1._

---
```

### Rules for test-cases.md
- One `##` section per TC. The heading format MUST be: `## <TC-ID> — <Name>`
- The metadata table MUST come immediately after the heading, before Description
- All field labels in the table MUST be bolded exactly as shown
- Steps MUST be an ordered list
- Actual Result MUST be `_[Fill at execution time]_` when Status is Not Run
- Separate each TC with `---`
- The YAML frontmatter `generated` date must be today's date
- The `<!-- req-coverage -->` comment must list all REQs in this file and their coverage status. **This comment is for human readers and git-diff review only — it is not parsed by `md_to_xlsx.py`.** The authoritative coverage data is the `Coverage` column in `tests/rtm.md`. Keep this comment in sync with the RTM whenever TCs are added or removed.

---

## 2. `tests/test-plan.md`

```markdown
---
project: PROJECT_NAME
version: 1.0
generated: YYYY-MM-DD
capabilities:
  - domain-or-capability-1
  - domain-or-capability-2
  - domain-or-capability-3
---

# Test Plan — PROJECT_NAME Project

## Identification

| Field | Value |
|---|---|
| Plan ID | TP-PROJECT_NAME-001 |
| Version | 1.0 |
| Spec Reference | spec.md v1.0 (OpenSpec base) |
| Date | YYYY-MM-DD |
| Prepared By | _[Author]_ |
| Approved By | _[Approver]_ |

## Scope

### Capabilities Under Test

| Capability | Folder | Spec File |
|---|---|---|
| Project Capability or Domain | domain-or-capability-1 | openspec/specs/domain-or-capability-1/spec.md |
| Project Capability or Domain | domain-or-capability-2 | openspec/specs/domain-or-capability-2/spec.md |

### Features NOT Tested

<!-- Adjust the items below for your project domain -->
- Internal implementation details not exposed to users
- Third-party library or dependency internals
- Infrastructure / network layer reliability

## Approach

| Mode | Scope |
|---|---|
| Manual | All positive, negative, and edge cases requiring human observation or visual verification |
| Automated | API-level workflows, integration flows, regression suite |

**Test levels:** Unit → Integration → System → Regression

**Entry criteria:** Build deployed to test environment; all spec.md files baselined in source control.

**Exit criteria:** 100% RTM coverage (Full or Partial); zero open P1/P2 defects; all Blocked TCs resolved or waived.

## Environment

<!-- Adjust the environment details below for your project -->
| Item | Detail |
|---|---|
| OS / Platforms | _[e.g., Windows 10, Windows 11, macOS 13+]_ |
| Runtime / Firmware | _[e.g., project-compatible target version]_ |
| Test Tools | Manual: scripted + exploratory / Automated: _[e.g., pytest, test harness]_ |
| Network | _[e.g., isolated test network or local environment]_ |

## Pass / Fail Criteria

| Result | Definition |
|---|---|
| Pass | Actual result matches expected result exactly |
| Fail | Any deviation; unexpected error; crash; data loss |
| Skip | Intentionally not run in this cycle (document reason) |

## Suspension Criteria

**Suspend:** A P1 defect blocks >20% of test cases; build broken; environment unavailable.

**Resume:** Blocking defect resolved and fix verified on build; environment confirmed stable.

## Risks

<!-- Replace the example risks below with risks relevant to your project domain -->
| Risk | Severity | Mitigation |
|---|---|---|
| _[Domain-specific risk 1]_ | High | _[Mitigation approach]_ |
| _[Domain-specific risk 2]_ | Medium | _[Mitigation approach]_ |
| Automation flakiness on integration tests | Low | Retry decorator; isolate flaky tests |

## Schedule

| Phase | Timeline |
|---|---|
| Test Planning | Week 1 |
| Test Case Authoring | Week 1–2 |
| Manual Execution | Week 3–4 |
| Automated Execution | Week 3–5 (parallel) |
| Defect Triage | Ongoing |
| Test Sign-off | Week 6 |

## Deliverables

| Deliverable | Location |
|---|---|
| Test Plan | tests/test-plan.md |
| Test Cases | tests/<capability>/test-cases.md |
| RTM | tests/rtm.md |
| Execution Workbook | Generated on demand: <ProjectName>_Tests_YYYYMMDD.xlsx |
| Test Summary Report | Produced at sign-off |
```

### Rules for test-plan.md
- YAML frontmatter `capabilities` list must be updated whenever a new capability is added
- All `_[Author]_` / `_[Approver]_` placeholders left for human to fill
- Risk table: always include at minimum the risks relevant to the capabilities in scope
- Full-scope runs (`all specs`): regenerate entirely
- Subset runs (single capability or incremental git-diff scope): preserve unchanged capability rows and update only changed capabilities, then refresh summary/identification date fields

---

## 3. `tests/rtm.md`

```markdown
---
project: PROJECT_NAME
generated: YYYY-MM-DD
total-requirements: 11
total-tcs: 17
coverage-full: 6
coverage-partial: 3
coverage-none: 2
---

# Requirements Traceability Matrix — PROJECT_NAME Project

> **How to read this:** Forward traceability = read left to right (REQ → TCs that cover it).
> Backward traceability = find a TC ID in the grid and read up to see which REQ it covers.
> Coverage: **Full** = has P + N cases. **Partial** = P only or N only. **None** = no TCs yet.

## Summary

| Metric | Count |
|---|---|
| Total Requirements | 11 |
| Total Test Cases | 17 |
| Full Coverage | 6 |
| Partial Coverage | 3 |
| No Coverage | 2 |

## Traceability Table

| REQ ID | Area | Description | Priority | Coverage | Test Cases |
|---|---|---|---|---|---|
| REQ-DOMN1-001 | DOMN1 | System SHALL allow download of one or more files in a single request | High | Full | TC-DOMN1-001-P, TC-DOMN1-001-N |
| REQ-DOMN1-002 | DOMN1 | System SHALL display download progress | High | Full | TC-DOMN1-002-P, TC-DOMN1-002-N, TC-DOMN1-002-E |
| REQ-DOMN1-003 | DOMN1 | System SHALL support East Asian language files (Noto Sans JP, Noto Serif CJK SC, Source Han Sans KR, MS Gothic) | High | Full | TC-DOMN1-003-P, TC-DOMN1-004-P, TC-DOMN1-005-P, TC-DOMN1-006-P, TC-DOMN1-007-N, TC-DOMN1-008-N |
| REQ-DEVICE-001 | DEVICE | System SHALL discover connected devices automatically | High | Partial | TC-DEVICE-001-P |
| REQ-BARCODE-001 | BARCODE | System SHALL manage files of special cases | Medium | None | |

## Reverse Index — TC to REQ

| TC ID | Type | REQ ID(s) | Capability | Status |
|---|---|---|---|---|
| TC-DOMN1-001-P | P | REQ-DOMN1-001 | domain-or-capability-1 | Not Run |
| TC-DOMN1-001-N | N | REQ-DOMN1-001 | domain-or-capability-1 | Not Run |
| TC-DOMN1-002-P | P | REQ-DOMN1-002 | domain-or-capability-1 | Not Run |
| TC-DOMN1-003-P | P | REQ-DOMN1-003 | domain-or-capability-1 | Not Run |
| TC-DEVICE-001-P | P | REQ-DEVICE-001 | domain-or-capability-3 | Not Run |
```

### Rules for rtm.md
- YAML frontmatter summary counts MUST be accurate — compute them from actual data
- Traceability Table: one row per REQ ID, TCs in the "Test Cases" column as comma-separated IDs
- Reverse Index: one row per TC ID — this is the backward traceability table
- Coverage values MUST be consistent between the summary, traceability table, and what's in test-cases.md
- Full-scope runs (`all specs`): regenerate complete RTM
- Subset runs (single capability or incremental git-diff scope): preserve rows from unchanged capabilities and replace/add rows for changed capabilities, then recompute all summary counts
- Sort rows by Area then REQ ID numerically within each area
