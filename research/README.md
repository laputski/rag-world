# research/ — planning archive

**These documents are archived. They are not a description of the current
system, and parts of them describe decisions that were later reversed.**

They are kept because they record how the project was reasoned about before the
code existed: which definitions were adopted, on what grounds, and which
acceptance criteria were set. Where a claim here disagrees with the code, the
code is right and the document is history.

For what the system is now, read
[docs/DATA.md](../docs/DATA.md) for the data layout,
[governance/DECISIONS.md](../governance/DECISIONS.md) for decisions and their
reversals, and [specs/](../specs/) for the state of each stage.

## What has since changed

The archive predates the rebuild. It speaks of a radar view, of an earlier
factorisation the project has since dropped, and of PostgreSQL as the store.
None of the three survives:

| In the archive | In the project now |
|---|---|
| radar as the main view | maturity map: level against attention, [ADR-008](../governance/DECISIONS.md) |
| the earlier factorisation | 28 dimensions in seven strata with compatibility constraints, [ADR-001](../governance/DECISIONS.md) |
| registry in PostgreSQL | registry in git as versioned files, [ADR-004](../governance/DECISIONS.md) and [ADR-009](../governance/DECISIONS.md) |
| test harness for measuring metrics | still not built; see [specs/stages/STAGE-harness.md](../specs/stages/STAGE-harness.md) |

## Contents

| Document | Subject | What became of it |
|---|---|---|
| [01-concept-plan.md](archive/01-concept-plan.md) | the configuration space: definitions, dimension set, inclusion criterion, the notion of residual | the conceptual core survived and lives in `core/dimensions_schema.py`; the vocabulary of the earlier model did not |
| [02-maturity-scale-plan.md](archive/02-maturity-scale-plan.md) | maturity scale, evidence, the rule that derives a level | implemented in `core/maturity.py`; the views described here were replaced |
| [03-radar-harness-plan.md](archive/03-radar-harness-plan.md) | automatic updating: collectors, validation stages, approval gates, test harness | collectors and stages built; the harness deferred |
| [99-review.md](archive/99-review.md) | a critical review of plans 01–03 | some objections resolved, some still open |

---

# research/ — архив планирования

**Документы архивны. Это не описание нынешней системы, и часть решений в них
впоследствии отменена.**

Они сохранены потому, что показывают, как проект обдумывался до появления кода:
какие определения приняты, на каком основании и с какими проверяемыми
критериями. Там, где утверждение здесь расходится с кодом, право за кодом, а
документ остаётся историей.

О нынешнем устройстве: [docs/DATA.md](../docs/DATA.md) — раскладка данных,
[governance/DECISIONS.md](../governance/DECISIONS.md) — решения и их отмены,
[specs/](../specs/) — состояние ступеней.

Архив написан до перестройки. В нём говорится о радаре как главном
представлении, о прежней факторизации, от которой проект отказался, и о
PostgreSQL как хранилище. Ни одно из трёх не уцелело: их заменили карта
зрелости, двадцать восемь измерений в семи стратах и реестр в git.
Испытательный стенд не построен до сих пор.
