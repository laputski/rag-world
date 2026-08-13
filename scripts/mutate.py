#!/usr/bin/env python3
"""Мутационный прогон: правило считается проверенным, если его порча ловится.

Покрытие говорит, что строка выполнялась. Оно не говорит, что её поломку
кто-нибудь заметит. Разница не умозрительная: у проверки данных покрытие было
48 процентов, а отключение любой её проверки по одной оставляло весь набор
зелёным двадцать один раз подряд.

Здесь боевой код портится осмысленно, по одной правке за раз, и запускается
весь набор тестов. Мутант, переживший прогон, показывает место, где проверки
нет, сколько бы ни было покрытия.

**Перечень составлен вручную, и это решение, а не лень.** Средства случайной
мутации порождают тысячи правок, из которых большинство равносильны исходному
коду: они ничего не меняют в поведении, убить их нельзя, и отчёт тонет в них.
Здесь каждая запись называет правило, которое она проверяет, поэтому перечень
читается как список того, на чём проект держится.

**Неприменившийся мутант считается провалом, а не пропуском.** Строка кода
меняется, образец перестаёт совпадать, и запись тихо перестаёт что-либо
проверять. Перечень при этом остаётся зелёным и выглядит внушительно. За один
день такое случилось трижды, поэтому здесь это ошибка.

Использование::

    python3 scripts/mutate.py                 # весь перечень
    python3 scripts/mutate.py --only ссылк    # только правила про ссылки
    python3 scripts/mutate.py --list          # показать перечень, не запуская
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Mutation:
    """Одна порча: какое правило проверяется и чем оно заменяется."""

    path: str
    rule: str
    before: str
    after: str


# ─── Перечень ────────────────────────────────────────────────────────────────
#
# Порядок тематический, а не по важности: так проще искать глазами и добавлять
# соседа к родственной записи.

MUTATIONS: tuple[Mutation, ...] = (
    # ── Шкала зрелости: каждое правило утверждает о технологии ──────────────
    Mutation("core/maturity.py", "L1 требует публикации",
             'l1_ok = _has_publication(evidence, "workshop_preprint")',
             "l1_ok = True"),
    Mutation("core/maturity.py", "L3 требует L2 (монотонность)",
             'if l3_ok and "L2" in satisfied:', "if l3_ok:"),
    Mutation("core/maturity.py", "L4 засчитывает загрузки пакета",
             '        or _has_any(evidence, "package_downloads")', "        or False"),
    Mutation("core/maturity.py", "уверенность считается, а не назначается",
             "return round(sum(per_alt) / len(per_alt), 3) if per_alt else 0.0",
             "return 1.0"),
    Mutation("core/maturity.py", "свежесть свидетельства учитывается",
             "good = sum(1 for e in of_type if _is_fresh(e, as_of) and e.verified)",
             "good = len(of_type)"),

    # ── Схема измерений ─────────────────────────────────────────────────────
    Mutation("core/dimensions_schema.py", "конфигурация проверяется ограничениями",
             "def validate(", "def _disabled_validate("),

    # ── Хранилище: повторы и дозапись ───────────────────────────────────────
    Mutation("services/registry/store.py", "отбор повторов свидетельств",
             "if key in known:\n            continue",
             "if False:\n            continue"),
    Mutation("services/registry/store.py", "источник входит в ключ повторов ряда",
             "return (m.technology_id, m.metric, m.measured_at.isoformat(), m.source)",
             "return (m.technology_id, m.metric, m.measured_at.isoformat(), '')"),
    Mutation("services/registry/store.py", "уровень пишется только при изменении",
             "if previous is not None and previous.level == entry.level:",
             "if False:"),
    Mutation("services/registry/store.py", "свидетельства раскладываются по месяцам",
             "by_month.setdefault(evidence_path(item.fetched_at), [])",
             "by_month.setdefault(evidence_path(date(2000, 1, 1)), [])"),

    # ── Пригодность кандидата ───────────────────────────────────────────────
    Mutation("core/candidate_fit.py", "задача из предмета реестра весит больше",
             'fit.add(4, "coreTask", tasks=core)', 'fit.add(2, "coreTask", tasks=core)'),
    Mutation("core/candidate_fit.py", "чужая область снижает оценку",
             "if off and not core:", "if False:"),
    Mutation("core/candidate_fit.py", "чужая область не наказывает работу об извлечении",
             "if off and not core:", "if off:"),
    Mutation("core/candidate_fit.py", "оценка не опускается ниже нуля",
             "fit.score = max(0, min(MAX_SCORE, fit.score))",
             "fit.score = min(MAX_SCORE, fit.score)"),
    Mutation("core/candidate_fit.py", "признак записывается кодом, а не фразой",
             'fit.add(2, "named")', 'fit.signals.append("работа названа") or None'),

    # ── Каталог работ и кода ────────────────────────────────────────────────
    Mutation("services/collectors/paperswithcode.py",
             "ответ каталога о той ли работе",
             "    if paper.arxiv_id != arxiv_id:", "    if False:"),
    Mutation("services/collectors/paperswithcode.py",
             "лента не старше запрошенной даты",
             "        if paper.published < published_after:", "        if False:"),
    Mutation("services/collectors/paperswithcode.py",
             "без площадки нет свидетельства о публикации",
             "    if not paper.venue:\n        # Сведения о площадке нет.",
             "    if False:\n        # Сведения о площадке нет."),
    Mutation("services/collectors/paperswithcode.py",
             "счётчик цитирований назван по имени",
             'parts.append(f"citations_semantic_scholar={paper.citations}")',
             'parts.append(f"cited_by={paper.citations}")'),
    Mutation("services/collectors/paperswithcode.py",
             "запрос идёт по метке метода и дате",
             '{"method": method, "published_after": published_after.isoformat()}',
             '{"q": method}'),

    # ── Проверки ступени сбора ──────────────────────────────────────────────
    Mutation("services/collectors/s5.py", "нижняя граница года",
             "MIN_YEAR = 1900", "MIN_YEAR = 0"),

    # ── Внимание и нормировка ───────────────────────────────────────────────
    Mutation("scripts/build_artifacts.py", "порог размера возрастной подгруппы",
             "if len(values) >= MIN_COHORT", "if len(values) >= 0"),
    Mutation("scripts/build_artifacts.py", "медиана подгруппы, а не среднее",
             "year: _median(values)", "year: (sum(values) / len(values))"),
    Mutation("scripts/build_artifacts.py", "свежесть показателя считается по источнику",
             "known.measured_at, known.value", "known.value, known.measured_at"),

    # ── Ссылки ──────────────────────────────────────────────────────────────
    Mutation("scripts/check_links.py", "временный отказ не убивает ссылку",
             '    if status in GONE:\n        return "unresolved"',
             '    if status >= 400:\n        return "unresolved"'),
    Mutation("scripts/check_links.py", "разрыв связи не меняет отметку",
             'outcomes[link.url] = ("unknown", 0)',
             'outcomes[link.url] = ("unresolved", 0)'),
    Mutation("scripts/check_links.py", "закрытый правами адрес получает свою отметку",
             '    if status in GUARDED:\n        return "guarded"',
             '    if False:\n        return "guarded"'),

    # ── Дайджест ────────────────────────────────────────────────────────────
    Mutation("scripts/build_digest.py", "пустой выпуск не выходит",
             "def has_news(self) -> bool:\n        return bool(",
             "def has_news(self) -> bool:\n        return True or bool("),
    Mutation("scripts/build_digest.py", "русские числительные",
             "if 11 <= tail_100 <= 14:", "if False:"),

    # ── Шлюз просмотра ──────────────────────────────────────────────────────
    Mutation("scripts/classify_changes.py", "граница подтверждённости",
             'REVIEW_THRESHOLD = "L4"', 'REVIEW_THRESHOLD = "L6"'),
    Mutation("scripts/classify_changes.py", "понижение уровня требует просмотра",
             "if before is not None and _rank(level) < _rank(before):", "if False:"),
    Mutation("scripts/classify_changes.py", "свидетельство человека требует просмотра",
             'if entry.get("evidence_basis") == "manual":', "if False:"),
    Mutation("scripts/classify_changes.py", "сравнение с HEAD, а не с индексом",
             '["git", "diff", "HEAD", "--unified=0", "--", LEVELS_PATH]',
             '["git", "diff", "--unified=0", "--", LEVELS_PATH]'),
    Mutation("scripts/classify_changes.py", "отказ git поднимает незнание",
             "if result.returncode != 0:", "if False:"),
    Mutation("scripts/classify_changes.py", "отсутствие журнала поднимает незнание",
             "if not (base / LEVELS_PATH).exists():", "if False:"),
    Mutation("scripts/classify_changes.py", "незнание закрывает шлюз",
             'print("review=true")', 'print("review=false")'),
    Mutation("scripts/classify_changes.py", "путь журнала берётся у хранилища",
             "LEVELS_PATH = str(store.LEVELS_FILE.relative_to(ROOT))",
             'LEVELS_PATH = "data/levels/history.jsonl.old"'),

    # ── Проверка данных ─────────────────────────────────────────────────────
    Mutation("scripts/validate_data.py", "значение измерения существует в схеме",
             "elif value not in ALL_VALUES[code]:", "elif False:"),
    Mutation("scripts/validate_data.py", "измерение существует в схеме",
             "if code not in ALL_VALUES:\n"
             '                problems.append(f"{where}: неизвестное измерение',
             "if False:\n"
             '                problems.append(f"{where}: неизвестное измерение'),
    Mutation("scripts/validate_data.py", "конфигурация не нарушает ограничений",
             "for error in validate(tech.configuration):", "for error in []:"),
    Mutation("scripts/validate_data.py", "осмотренная ссылка несёт дату",
             'if link.status in ("verified", "guarded") and link.verified_at is None:',
             "if False:"),
    Mutation("scripts/validate_data.py", "неприменимое измерение не несёт значения",
             "elif code in tech.configuration:\n                # Значение у неприменимого",
             "elif False:\n                # Значение у неприменимого"),
    Mutation("scripts/validate_data.py", "роду без конфигурации нельзя иметь значения",
             "if tech.kind in store.KINDS_WITHOUT_CONFIGURATION and tech.configuration:",
             "if False:"),
    Mutation("scripts/validate_data.py", "свидетельство ссылается на известную запись",
             "if item.technology_id not in known:", "if False:"),
    Mutation("scripts/validate_data.py", "уверенность лежит в отрезке",
             "if not 0.0 <= entry.confidence <= 1.0:", "if False:"),
    Mutation("scripts/validate_data.py", "идентификатор записи не повторяется",
             "if tech.id in known:", "if False:"),
    Mutation("scripts/validate_data.py", "остаток берётся из словаря",
             "if mechanism not in vocabulary:", "if False:"),
    Mutation("scripts/validate_data.py", "имя файла совпадает с идентификатором",
             "if declared != path.stem:", "if False:"),
    Mutation("scripts/validate_data.py", "словарь остатков читается при проверке",
             "vocabulary = _residual_vocabulary()", "vocabulary = {}"),
    Mutation("scripts/validate_data.py", "идентификатор по соглашению",
             "if not ID_RE.match(tech.id):", "if False:"),
    Mutation("scripts/validate_data.py", "имя записи непусто",
             "if not tech.name.strip():", "if False:"),
    Mutation("scripts/validate_data.py", "страта принадлежит A–G",
             "if group not in STRATA:", "if False:"),
    Mutation("scripts/validate_data.py", "разобранная запись что-то утверждает",
             "if (\n            tech.configuration_reviewed", "if (\n            False"),
    Mutation("scripts/validate_data.py", "измерение не переменное и неприменимое сразу",
             "if both:", "if False:"),
    Mutation("scripts/validate_data.py", "переменное измерение имеет значение",
             "elif code not in tech.configuration:", "elif False:"),
    Mutation("scripts/validate_data.py", "у источника есть адрес",
             "if not link.url.strip():", "if False:"),
    Mutation("scripts/validate_data.py", "уровень принадлежит шкале",
             "if entry.level not in LEVELS:", "if False:"),

    # ── Объявленные зависимости ─────────────────────────────────────────────
    Mutation("pyproject.toml", "зависимость разбора рабочих процессов объявлена",
             '    "pyyaml>=6.0",\n', ""),

    # ── Проход обновления ───────────────────────────────────────────────────
    Mutation("scripts/update.py", "проход встаёт на непройденной проверке",
             "if problems:\n        sys.stderr", "if False:\n        sys.stderr"),

    # ── Выпуск: единственное необратимое действие ───────────────────────────
    Mutation("scripts/make_release.py", "выпуск проверяет данные",
             'problems = [f"данные не проходят проверку: {p}" for p in\n'
             "                validate_data.check_registry()]",
             "problems = []"),
    Mutation("scripts/make_release.py", "артефакты собраны из нынешних данных",
             "            if expected != actual:", "            if False:"),
    Mutation("scripts/make_release.py", "артефакты вообще собраны",
             "    if missing:\n        problems.append(",
             "    if False:\n        problems.append("),
    Mutation("scripts/make_release.py", "снимок не обещает отсутствующий файл",
             "    if missing:\n        raise FileNotFoundError(",
             "    if False:\n        raise FileNotFoundError("),
    Mutation("scripts/make_release.py", "выпуск не переписывается",
             "    if target.exists():\n        raise FileExistsError(",
             "    if False:\n        raise FileExistsError("),
    Mutation("scripts/make_release.py", "снимок пишется целиком или никак",
             "        os.replace(draft, target)", "        shutil.copytree(draft, target)"),
    Mutation("scripts/make_release.py", "черновик убирается при срыве",
             "        shutil.rmtree(draft, ignore_errors=True)", "        pass"),
    Mutation("scripts/make_release.py", "выпуск встаёт на препятствиях",
             '    if problems:\n        sys.stderr.write(f"выпускать нельзя',
             '    if False:\n        sys.stderr.write(f"выпускать нельзя'),
    Mutation("scripts/make_release.py", "неполный выпуск не сходит за полный",
             '    if not (target / "release.json").exists():\n        return False',
             "    if False:\n        return False"),
    Mutation("scripts/make_release.py", "архив входит в признак полноты",
             'if not (releases_dir() / f"rag-world-{tag}.zip").exists():\n        return False',
             "if False:\n        return False"),
    Mutation("scripts/make_release.py", "перечень выпусков свежими вперёд",
             'index.sort(key=lambda r: r["tag"], reverse=True)',
             'index.sort(key=lambda r: r["tag"])'),
    Mutation("scripts/make_release.py", "числа описания берутся у выпуска",
             "f\"{meta['released_at']}. Зафиксировано технологий: "
             "{meta['technologies']}, \"",
             "f\"{meta['released_at']}. Зафиксировано технологий: 0, \""),
    # ── Локализация выгрузки ───────────────────────────────────────────────
    #
    # Русский текст без двойника выглядит исправным полем и обнаруживается
    # только у потребителя, читающего данные без портала. Проза же, оставшаяся
    # в ресурсах интерфейса, не обнаруживается вовсе: выгрузка просто молчит о
    # том, что это за технология.
    Mutation("scripts/build_artifacts.py", "проза уходит в выгрузку",
             '            **prose.get(tech.prose_id or "", {}),', ""),
    Mutation("scripts/build_artifacts.py", "проза уходит на обоих языках",
             '                out[prose_id][f"{published}_en"] = english',
             "                pass"),
    Mutation("scripts/build_artifacts.py", "страты названы по-английски",
             '"name_en": strip(names["en"].get(code, code)),',
             '"name_en": "",'),
    Mutation("scripts/build_artifacts.py", "английская запись свидетельства доезжает",
             '"value_en": e.value_en,', '"value_en": None,'),
    Mutation("scripts/build_artifacts.py", "лента выпускается на обоих языках",
             '    _write_feed(target / "feed.ru.xml", changes, built_at, _issues(), "ru")',
             "    pass"),

    # ── Машиночитаемый вход: указатель, карта сайта, llms.txt ──────────────
    #
    # Отказ здесь тих вдвойне. Указатель, обещающий несуществующий набор, и
    # карта сайта без половины карточек выглядят исправными файлами; ошибка
    # обнаруживается у потребителя, который по ним написал обращение.
    Mutation("scripts/build_artifacts.py", "указатель называет все опубликованные наборы",
             '    ("digest.json", "issues",',
             '    ("digest_absent.json", "issues",'),
    Mutation("scripts/build_artifacts.py", "число записей берётся из файла",
             'entry["records"] = len(payload.get(key, []))',
             'entry["records"] = 0'),
    Mutation("scripts/build_artifacts.py", "карта сайта содержит карточки",
             'urls += [f"{SITE}/tech/{row[\'id\']}" for row in sorted(',
             'urls += [] or [f"{SITE}/tech/nowhere" for row in sorted('),
    Mutation("scripts/build_artifacts.py", "указатель несёт версию правила уровня",
             '"rule_version": RULE_VERSION,', '"rule_version": "unknown",'),
    Mutation("scripts/build_artifacts.py", "llms.txt отговаривает от разбора страниц",
             '"Do not scrape the pages.', '"Feel free to read the pages.'),
    Mutation("ui/src/i18n/ru.json", "у сообщения со счётом есть все русские формы",
             '    "thatDay_few": "{{count}} изменения",\n', ""),

    # ── Проза карточек: единственный текст портала, писанный руками ────────
    #
    # Порча вносится не в код, а в сами тексты: проверять здесь нечего, кроме
    # данных, и сторож обязан ловить именно их. Каждое правило повторяет
    # дефект, который на портале уже был.
    Mutation("ui/src/i18n/ru/tech.json", "проза без ссылок на список литературы",
             "Microsoft GraphRAG строит по всему",
             "Microsoft GraphRAG [4] строит по всему"),
    Mutation("ui/src/i18n/ru/tech.json", "проза без транслитерированного жаргона",
             "Векторное представление строится по вымышленному ответу",
             "Эмбеддинг строится по вымышленному ответу"),
    Mutation("ui/src/i18n/ru/tech.json", "проза без нерасшифрованных сокращений",
             "которые большая языковая модель извлекает из текста",
             "которые LLM извлекает из текста"),
    Mutation("ui/src/i18n/ru/tech.json", "тире не заменяет связку",
             "а рёбрами служат отношения",
             "а рёбра — отношения"),
    Mutation("ui/src/i18n/ru/tech.json", "развёрнутое описание разбито на абзацы",
             "\\n\\nСистема отвечает на вопрос одним из трёх способов",
             " Система отвечает на вопрос одним из трёх способов"),
    Mutation("ui/src/i18n/en/tech.json", "английская проза есть везде, где русская",
             '"full": "Microsoft GraphRAG builds a single knowledge graph',
             '"full_": "Microsoft GraphRAG builds a single knowledge graph'),

    Mutation("scripts/make_release.py", "пробный прогон ничего не пишет",
             '    if dry_run:\n        print("пробный прогон',
             '    if False:\n        print("пробный прогон'),
)


# ─── Прогон ──────────────────────────────────────────────────────────────────


def suite_is_green() -> bool:
    """Набор на нетронутом дереве. Без этого мутанты «гибнут» по чужой вине."""
    return _pytest().returncode == 0


def _pytest() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "-x", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
    )


def survives(mutation: Mutation) -> bool | None:
    """True — мутант выжил, False — пойман, None — не применился."""
    target = ROOT / mutation.path
    original = target.read_text(encoding="utf-8")
    if mutation.before not in original:
        return None
    target.write_text(original.replace(mutation.before, mutation.after, 1),
                      encoding="utf-8")
    try:
        return _pytest().returncode == 0
    finally:
        # Восстановление обязано случиться при любом исходе, включая прерывание
        # с клавиатуры: иначе испорченный код останется в рабочем дереве.
        target.write_text(original, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="только правила, содержащие эту подстроку")
    parser.add_argument("--list", action="store_true", help="показать перечень")
    args = parser.parse_args()

    chosen = [
        m for m in MUTATIONS
        if not args.only
        or args.only.lower() in m.rule.lower()
        or args.only.lower() in m.path.lower()
    ]
    if args.list:
        for mutation in chosen:
            print(f"  {mutation.path:<34} {mutation.rule}")
        print(f"\nвсего правил: {len(chosen)}")
        return 0
    if not chosen:
        sys.stderr.write(f"по образцу {args.only!r} ничего не найдено\n")
        return 1

    print("проверка нетронутого дерева…", flush=True)
    if not suite_is_green():
        sys.stderr.write(
            "набор тестов не проходит без всяких мутаций. Мутационный прогон "
            "в таком состоянии бессмыслен: мутанты будут «гибнуть» по чужой "
            "вине. Сначала почините набор.\n"
        )
        return 1

    started = time.monotonic()
    survivors: list[Mutation] = []
    unapplied: list[Mutation] = []
    caught = 0

    for index, mutation in enumerate(chosen, 1):
        outcome = survives(mutation)
        head = f"[{index:>2}/{len(chosen)}]"
        if outcome is None:
            unapplied.append(mutation)
            print(f"{head} ?  НЕ ПРИМЕНИЛСЯ  {mutation.rule}", flush=True)
        elif outcome:
            survivors.append(mutation)
            print(f"{head} !  ВЫЖИЛ         {mutation.rule}", flush=True)
        else:
            caught += 1
            print(f"{head} +  пойман        {mutation.rule}", flush=True)

    spent = time.monotonic() - started
    print(
        f"\nправил {len(chosen)}, пойманы {caught}, выжили {len(survivors)}, "
        f"не применились {len(unapplied)}; за {spent:.0f} с"
    )

    if survivors:
        print("\nПРАВИЛА БЕЗ ПРОВЕРКИ (порча не замечена ни одним тестом):")
        for mutation in survivors:
            print(f"  {mutation.path}: {mutation.rule}")
    if unapplied:
        # Не пропуск, а провал: образец разошёлся с кодом, и запись перестала
        # что-либо проверять, оставаясь в перечне и создавая видимость охраны.
        print("\nОБРАЗЕЦ РАЗОШЁЛСЯ С КОДОМ (запись ничего не проверяет):")
        for mutation in unapplied:
            print(f"  {mutation.path}: {mutation.rule}")

    return 1 if survivors or unapplied else 0


if __name__ == "__main__":
    raise SystemExit(main())
