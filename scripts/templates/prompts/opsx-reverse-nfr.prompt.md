---
mode: 'agent'
description: 'Generate non-functional requirements from code patterns for a domain or the whole system'
---

Generate **non-functional requirements (NFRs)** in OpenSpec format by scanning code for signals of performance, security, reliability, scalability, and observability intent.

**Ask the user which domain to analyse** if not already specified. Options:
- A specific domain name (e.g., `auth`, `payments`) — scoped NFRs appended to that domain's spec
- `cross-cutting` or `system` — system-wide NFRs written to `openspec/specs/quality-attributes/spec.md`

Reference `domain-map.yaml` at the repository root for available domains and their paths.

---

## Setup

1. Read `domain-map.yaml` to find the domain's `paths`.
2. Determine the target spec file:
   - **Domain-scoped**: `openspec/specs/<domain-name>/spec.md` — append a `## Non-Functional Requirements` section
   - **Cross-cutting / system**: `openspec/specs/quality-attributes/spec.md` — create if it doesn't exist
3. Note any `nfr_signals` already recorded in `domain-map.yaml` for this domain — use them as a starting point.

---

## NFR Signal Scanning

Scan the domain paths for the patterns below. For each signal found, record:
- **What pattern** was detected
- **Where** it was found (file path / class / function name)
- **What NFR category** it implies

### Performance Signals
| Pattern | Implication |
|---|---|
| Cache decorator or explicit cache calls (`@Cacheable`, `redis.get/set`, `MemoryCache`, `IDistributedCache`) | Performance — caching strategy exists |
| Pagination parameters (`limit`/`offset`/`cursor`/`page` in queries or API inputs) | Performance — large dataset handling |
| Async workers, task queues, background jobs | Performance — deferred/non-blocking processing |
| DB index definitions, query projections, query hints | Performance — DB query optimization |
| Connection pool configuration (pool size, min/max connections) | Performance — connection reuse |
| Explicit timeout values on HTTP clients, DB queries, or external calls | Performance — bounded latency design |

### Security Signals
| Pattern | Implication |
|---|---|
| Auth middleware or guards (`[Authorize]`, `@UseGuards`, JWT validation, session checks) | Security — authentication enforced |
| Role or permission checks, RBAC decorators, policy enforcement | Security — authorization model |
| Password hashing (bcrypt, argon2, PBKDF2) | Security — credential protection |
| Input validation schemas (Joi, Zod, FluentValidation, DataAnnotations) | Security — injection prevention |
| Rate limiting middleware (`express-rate-limit`, `@RateLimit`, throttle policies) | Security/Scalability — abuse prevention |
| CORS configuration, CSRF tokens, `SameSite` cookie settings | Security — web attack surface reduction |
| Secrets loaded from environment/vault (no hardcoded credentials in code) | Security — secrets management |
| Parameterized queries, ORM usage (no raw string concatenation in queries) | Security — SQL injection prevention |

### Reliability Signals
| Pattern | Implication |
|---|---|
| Retry logic with backoff (Polly, `@Retry`, custom retry loops) | Reliability — transient failure tolerance |
| Circuit breakers (`Polly.CircuitBreaker`, Hystrix, `@CircuitBreaker`) | Reliability — cascading failure prevention |
| Health check endpoints (`/health`, `/ready`, `/live`) | Reliability — operational observability |
| Graceful shutdown handlers (SIGTERM/SIGINT hooks, connection drain logic) | Reliability — zero in-flight request loss |
| Dead letter queues, poison message handling | Reliability — message processing guarantee |
| Idempotency keys or duplicate detection logic | Reliability — exactly-once semantics |
| Database transaction management, saga/compensating transaction patterns | Reliability — data consistency |

### Scalability Signals
| Pattern | Implication |
|---|---|
| Message queue producers/consumers (Kafka, RabbitMQ, SQS, Azure Service Bus) | Scalability — async decoupling |
| Stateless request handling (no in-memory session, state externalised to DB/cache) | Scalability — horizontal scaling readiness |
| Concurrency limits, semaphore patterns, max worker settings | Scalability — throughput control |
| Kubernetes Deployment replica settings, HPA (HorizontalPodAutoscaler) configs | Scalability — horizontal scaling config |
| Database read replica usage, sharding patterns | Scalability — read/write scaling |

### Observability Signals
| Pattern | Implication |
|---|---|
| Structured logging with correlation IDs (JSON output, request IDs in logs) | Observability — traceable log trail |
| Metrics emission (Prometheus counters/histograms, StatsD, custom metrics) | Observability — operational metrics |
| Distributed tracing (OpenTelemetry spans, Jaeger, AWS X-Ray, B3 headers) | Observability — cross-service trace visibility |
| Kubernetes readiness/liveness probes | Observability — deployment health |
| Alerting rules or SLO definitions | Observability — proactive failure detection |

---

## Generate the NFR Spec

### Format for Domain-Scoped NFRs

Append to `openspec/specs/<domain-name>/spec.md`:

```markdown
---

## Non-Functional Requirements

### Performance

#### Requirement: <Performance Behavior Name>
The system SHALL <observable performance behavior statement>.

> **Evidence**: <file/module where this was inferred from>
> **Target**: **[PLACEHOLDER — EM: replace with actual target, e.g., "p95 response time < 200ms"]**

##### Scenario: Normal operating load
- GIVEN the service is handling normal traffic
- WHEN a <specific action> is performed
- THEN the response is delivered within [PLACEHOLDER] at the 95th percentile

##### Scenario: Peak load
- GIVEN the service is under peak traffic as defined in capacity planning
- WHEN <specific action> is performed
- THEN performance SHALL remain within [PLACEHOLDER]

---

### Security

#### Requirement: <Security Behavior Name>
The system SHALL <security behavior>.

> **Evidence**: <code location>

##### Scenario: Authenticated access
- GIVEN <precondition>
- WHEN <authorized action>
- THEN <secure, successful outcome>

##### Scenario: Unauthenticated or unauthorized attempt
- GIVEN <precondition>
- WHEN <unauthorized action>
- THEN the request is rejected with an appropriate error response
- AND no sensitive data is exposed

---

### Reliability

#### Requirement: <Reliability Behavior Name>
The system SHALL <reliability behavior>.

> **Evidence**: <code location>
> **Target**: **[PLACEHOLDER — EM: replace with target, e.g., "99.9% of operations succeed after retry"]**

##### Scenario: Transient failure
- GIVEN a transient failure occurs in a downstream dependency
- WHEN the operation is attempted
- THEN the system SHALL retry up to [PLACEHOLDER] times with [PLACEHOLDER] backoff
- AND ultimately succeed or return a clear failure response

---

### Scalability

[Use same pattern — add only categories where code signals were found]

---

### Observability

[Use same pattern]
```

### Format for Cross-Cutting / System-Wide NFRs

Create `openspec/specs/quality-attributes/spec.md`:

```markdown
# System Quality Attributes

## Purpose
Cross-cutting non-functional requirements that apply to the system as a whole,
independent of any individual business domain.

## Availability

### Requirement: System Uptime
The system SHALL maintain [PLACEHOLDER]% uptime measured over any rolling 30-day period.

> **Target**: **[PLACEHOLDER — EM: fill in from SLA contracts or OKRs, e.g., "99.9%"]**

#### Scenario: Normal operations
- GIVEN the system is deployed and operational
- WHEN measured over any 30-day calendar period
- THEN uptime SHALL be at or above [PLACEHOLDER]%

#### Scenario: Planned maintenance
- GIVEN a maintenance window has been communicated in advance
- WHEN maintenance is performed within the scheduled window
- THEN this downtime MAY be excluded from the uptime SLA calculation

---

## Security Baseline

### Requirement: Authentication Required on All Endpoints
All non-public API endpoints SHALL require a valid authentication token.

> **Evidence**: <list of files/middleware where auth enforcement was detected>

#### Scenario: Valid token
- GIVEN a client presents a valid, non-expired authentication token
- WHEN any protected endpoint is called
- THEN the request is processed normally

#### Scenario: Missing or invalid token
- GIVEN a client presents no token or an invalid/expired token
- WHEN any protected endpoint is called
- THEN the request is rejected with HTTP 401
- AND no resource data is included in the response

[Add more cross-cutting security requirements as found]

---

## Observability Baseline

### Requirement: Structured Logging with Correlation IDs
All services SHALL emit structured logs containing a correlation ID traceable across service boundaries.

> **Evidence**: <list of files where structured logging was detected>

#### Scenario: Inbound request
- GIVEN a request arrives at any service
- WHEN the request is processed
- THEN all log entries for that request SHALL include the same correlation ID
- AND the correlation ID SHALL be propagated to downstream service calls

[Add more cross-cutting observability requirements as found]
```

---

## Critical Rules

1. **Never invent SLA numbers.** Always write `[PLACEHOLDER]` for any metric target. The EM must fill in real values from contracts, OKRs, or operational experience.
2. **Cross-cutting goes in `quality-attributes/`**. If a pattern applies across multiple domains (e.g., "all endpoints require authentication"), put it there, not in individual domain specs.
3. **Missing evidence = documented gap**. If a category has no code signals, add:
   ```markdown
   <!-- No [category] patterns detected in this domain.
        Consider whether [category] requirements need to be specified manually. -->
   ```
4. **Uncertainty markers**. Use `<!-- TODO(EM-REVIEW): ... -->` for any inference you are not confident about.
5. **Don't add empty sections**. Only include NFR categories where you found actual code evidence (or a documented gap note).

---

## After Generating NFR Specs

Print this summary:

```
NFR spec updated: openspec/specs/<target>/spec.md

NFR categories with evidence:     [list]
NFR categories with no evidence:  [list]
[PLACEHOLDER] values needing EM:  N

Key actions for the EM:
  1. Replace every [PLACEHOLDER] with a real target value from your SLAs / OKRs / contracts
  2. Review TODO(EM-REVIEW) comments and correct any misinterpretations
  3. For categories with no evidence, decide whether to specify from scratch or defer
  4. Commit the updated spec to source control
```
