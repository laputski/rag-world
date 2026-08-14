# specs/ — stage specifications

Each stage is specified before it is written: SPECIFY (goal, scope, functional
requirements, acceptance criteria), then PLAN, then TASKS. A specification is
amended when understanding changes, not quietly abandoned.

**This index states what is actually built.** A specification is a plan until
its state line says otherwise, and a reader must be able to tell one from the
other without reading the code.

## State

| Stage | Subject | State |
|---|---|---|
| [STAGE-portal-rebuild.md](stages/STAGE-portal-rebuild.md) | rebuilding the engine into a portal | **built** |
| [STAGE-discovery.md](stages/STAGE-discovery.md) | finding new work and the candidate queue | **built**, runs weekly |
| [STAGE-residual-queue.md](stages/STAGE-residual-queue.md) | filling residuals, queue of candidate dimensions | **built**; two mechanisms have since become dimensions |
| [STAGE-citability.md](stages/STAGE-citability.md) | releases, citation export, persistent identifier | **built** except the DOI, which waits on Zenodo |
| [STAGE-en-locale.md](stages/STAGE-en-locale.md) | English localisation | **built**; English is now the default language |
| [STAGE-news-generator.md](stages/STAGE-news-generator.md) | digest and annotations | **first genre built**, the rest closed ([ADR-010](../governance/DECISIONS.md)) |
| [STAGE-gap-map.md](stages/STAGE-gap-map.md) | map of gaps in the configuration space | not started |
| [STAGE-compare-and-inverse.md](stages/STAGE-compare-and-inverse.md) | comparing technologies, inverse constructor | not started |
| [STAGE-engine-v1.md](stages/STAGE-engine-v1.md) | an executable engine over the schema | not started; needs a decision on what it is for |
| [STAGE-harness.md](stages/STAGE-harness.md) | test harness for measuring metrics | not started; blocked on how to read the term |

## Order, not a list

The stages are not listed in the order they get done. The order follows from
what each gives the portal, and it is this: anything that makes an existing
claim checkable comes before anything that adds a new claim.

That is why citability came before the gap map, and why the engine waits: a
constructor that builds systems from the schema is the most interesting item
here and the least useful one until the schema is proven on more records than
it is today.

---

# specs/ — спеки ступеней

Каждая ступень описывается до того, как написана: SPECIFY (цель, объём,
функциональные требования, критерии приёмки), затем PLAN и TASKS. Спека
правится, когда меняется понимание, а не забрасывается молча.

**Указатель говорит, что построено на самом деле.** Спека остаётся планом, пока
строка состояния не скажет иного, и отличить одно от другого читатель обязан не
читая код.

Порядок ступеней определяется не удобством, а правилом: то, что делает уже
сделанное утверждение проверяемым, идёт раньше того, что добавляет новое
утверждение.
