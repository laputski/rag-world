#!/usr/bin/env python3
"""Страница разбора конфигураций: чем обосновано каждое значение.

Разбор конфигурации — единственная часть портала, где решение принимает не
правило, а чтение источника. Уровень вычисляется из свидетельств и
воспроизводим; значение измерения — вывод из текста статьи, и проверить его
можно только рассуждением, которое к нему привело.

Поэтому обоснование хранится рядом с реестром (`data/parse_notes.jsonl`), а эта
страница его показывает. Порождение, а не ручная вёрстка, выбрано по одной
причине: страница, набранная руками, разъезжается с реестром молча — прошлая
версия уже требовала сверки в уме, и сверка эта нашла расхождения.

Проверка на расхождение выполняется здесь же: каждое значение со страницы
сверяется с реестром, и несовпадение останавливает сборку.

Использование::

    python3 scripts/build_review.py               # собрать страницу
    python3 scripts/build_review.py --out путь    # положить в указанный файл
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.dimensions_schema import DIMENSIONS  # noqa: E402
from services.registry import store  # noqa: E402

NOTES_FILE = store.DATA_DIR / "parse_notes.jsonl"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "build" / "review.html"

DIM_NAMES = {d.code: d.name for d in DIMENSIONS}
DEFAULTS = {d.code: d.default for d in DIMENSIONS}


def load_notes() -> list[dict]:
    if not NOTES_FILE.exists():
        return []
    notes = []
    for line in NOTES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            notes.append(json.loads(line))
    return notes


def check(notes: list[dict]) -> list[str]:
    """Сверить обоснования с реестром.

    Обоснование, разошедшееся с данными, хуже отсутствующего: оно объясняет
    значение, которого нет.
    """
    problems: list[str] = []
    for note in notes:
        tech = store.load_technology(note["technology_id"])
        if tech is None:
            problems.append(f"{note['technology_id']}: записи нет в реестре")
            continue

        # У записи рода без конфигурации обоснование одно и общее: оно
        # объясняет сам род, а не отдельное измерение.
        if not note.get("code") and not note.get("residual"):
            if tech.kind not in store.KINDS_WITHOUT_CONFIGURATION:
                problems.append(
                    f"{tech.id}: обоснование без измерения у записи рода {tech.kind!r}"
                )
            continue

        if note.get("residual"):
            if note["residual"] not in tech.residual:
                problems.append(
                    f"{tech.id}: обоснование остатка {note['residual']!r}, "
                    "которого у записи нет"
                )
            continue

        code = note["code"]
        if note.get("inapplicable"):
            if code not in tech.configuration_inapplicable:
                problems.append(f"{tech.id}.{code}: не помечено неприменимым")
            if code in tech.configuration:
                problems.append(f"{tech.id}.{code}: помечено неприменимым, но несёт значение")
            continue

        if code not in tech.configuration:
            problems.append(f"{tech.id}.{code}: значения нет в реестре")
            continue
        # Обоснование хранит значение, которое объясняет. Без этого правка
        # значения в реестре оставила бы при нём прежний довод, и страница
        # объясняла бы одно, показывая другое.
        if note.get("to") != tech.configuration[code]:
            problems.append(
                f"{tech.id}.{code}: обоснование написано для {note.get('to')!r}, "
                f"а в реестре {tech.configuration[code]!r}"
            )
        if bool(note.get("variable")) != (code in tech.configuration_variable):
            problems.append(f"{tech.id}.{code}: пометка «выбирается на ходу» расходится")
    return problems


def _kind(note: dict, tech: store.Technology) -> str:
    if not note.get("code") and not note.get("residual"):
        return "inapplicable"
    if note.get("residual"):
        return "residual"
    if note.get("inapplicable"):
        return "inapplicable"
    if note.get("variable"):
        return "variable"
    code = note["code"]
    return "changed" if tech.configuration.get(code) != DEFAULTS.get(code) else "confirmed"


KIND_LABEL = {
    "changed": "значение изменено",
    "confirmed": "базовое значение подтверждено",
    "variable": "выбирается на ходу",
    "inapplicable": "измерение неприменимо",
    "residual": "остаток: схема не выражает",
}


def render(notes: list[dict]) -> str:
    by_tech: dict[str, list[dict]] = defaultdict(list)
    for note in notes:
        by_tech[note["technology_id"]].append(note)

    technologies = [t for t in store.load_technologies() if t.id in by_tech]
    vocabulary = {}
    vocab_path = store.DATA_DIR / "residual_vocabulary.json"
    if vocab_path.exists():
        vocabulary = {
            m["id"]: m for m in
            json.loads(vocab_path.read_text(encoding="utf-8"))["mechanisms"]
        }

    total = len(notes)
    questioned = sum(1 for n in notes if n.get("question"))

    sections = []
    for tech in technologies:
        rows = []
        for note in by_tech[tech.id]:
            kind = _kind(note, tech)
            # У записи рода без конфигурации обоснование одно и общее: оно
            # объясняет сам род, а не отдельное измерение.
            if not note.get("code") and not note.get("residual"):
                heading = "род записи"
                subtitle = tech.kind
                value = "конфигурации нет"
            elif note.get("residual"):
                heading = vocabulary.get(note["residual"], {}).get("ru", note["residual"])
                subtitle = ""
                value = ""
            else:
                code = note["code"]
                heading = code
                subtitle = DIM_NAMES.get(code, "")
                if note.get("inapplicable"):
                    value = "значение снято"
                else:
                    now = tech.configuration.get(code, "")
                    was = DEFAULTS.get(code)
                    value = (
                        f'<span class="was">{html.escape(str(was))}</span>'
                        f'<span class="arrow">→</span>'
                        f'<span class="now">{html.escape(now)}</span>'
                        if kind in ("changed", "variable") and now != was
                        else f'<span class="now">{html.escape(now)}</span>'
                    )

            blocks = [
                f'<p class="did"><span class="lbl">Что делает система</span>'
                f'{html.escape(note["did"])}</p>',
                f'<p class="why"><span class="lbl">Почему из этого следует значение</span>'
                f'{html.escape(note["why"])}</p>',
            ]
            if note.get("instead"):
                blocks.append(
                    f'<p class="alt"><span class="lbl">Какое значение не подошло</span>'
                    f'{html.escape(note["instead"])}</p>'
                )
            if note.get("question"):
                blocks.append(
                    f'<p class="q"><span class="lbl">Здесь возможно другое прочтение</span>'
                    f'{html.escape(note["question"])}</p>'
                )

            rows.append(
                f'<article class="item k-{kind}{" open" if note.get("question") else ""}">'
                f'<div class="key"><div class="code">{html.escape(heading)}</div>'
                f'<div class="dim">{html.escape(subtitle)}</div>'
                f'<div class="val">{value}</div>'
                f'<div class="tag">{KIND_LABEL[kind]}</div></div>'
                f'<div class="body">{"".join(blocks)}'
                f'<p class="src">{html.escape(note.get("source", ""))}</p></div>'
                "</article>"
            )

        reviewed = tech.configuration_reviewed
        sections.append(
            f'<section class="rec" id="{html.escape(tech.id)}">'
            f'<header><h2>{html.escape(tech.name)}</h2>'
            f'<span class="meta">{len(by_tech[tech.id])} пунктов · '
            f'разобрано {reviewed.isoformat() if reviewed else "—"}</span></header>'
            + "".join(rows) + "</section>"
        )

    return TEMPLATE.format(
        total=total,
        records=len(technologies),
        questioned=questioned,
        sections="".join(sections),
    )


TEMPLATE = """<title>Разбор конфигураций: чем обосновано каждое значение</title>
<style>
:root {{
  --ground:#EDF1F3; --surface:#FFF; --surface2:#F5F8F9;
  --ink:#0E161C; --soft:#55636D; --faint:#8593A0;
  --rule:#D5DDE2; --rule2:#E5EBEF;
  --accent:#17596E; --changed:#9A5714; --ok:#2A6749; --open:#94363B; --open-bg:#F7E7E8;
  --serif: ui-serif,"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --sans: system-ui,-apple-system,"Segoe UI",Arial,sans-serif;
  --mono: ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --ground:#0F151A; --surface:#161E25; --surface2:#1C262D;
    --ink:#E3EAF0; --soft:#94A2AE; --faint:#6B7A87;
    --rule:#29343C; --rule2:#212B33;
    --accent:#63AFC7; --changed:#D79A55; --ok:#6FBE93; --open:#DE8B90; --open-bg:#2E1B1D;
  }}
}}
:root[data-theme="light"] {{
  --ground:#EDF1F3; --surface:#FFF; --surface2:#F5F8F9;
  --ink:#0E161C; --soft:#55636D; --faint:#8593A0;
  --rule:#D5DDE2; --rule2:#E5EBEF;
  --accent:#17596E; --changed:#9A5714; --ok:#2A6749; --open:#94363B; --open-bg:#F7E7E8;
}}
:root[data-theme="dark"] {{
  --ground:#0F151A; --surface:#161E25; --surface2:#1C262D;
  --ink:#E3EAF0; --soft:#94A2AE; --faint:#6B7A87;
  --rule:#29343C; --rule2:#212B33;
  --accent:#63AFC7; --changed:#D79A55; --ok:#6FBE93; --open:#DE8B90; --open-bg:#2E1B1D;
}}
body {{ background:var(--ground); color:var(--ink); font-family:var(--sans);
  font-size:16px; line-height:1.55; -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1020px; margin:0 auto; padding:0 20px 90px; }}
header.top {{ padding:54px 0 26px; }}
.eyebrow {{ font-family:var(--mono); font-size:.72rem; letter-spacing:.12em;
  text-transform:uppercase; color:var(--accent); margin-bottom:14px; }}
h1 {{ font-family:var(--serif); font-size:clamp(1.85rem,4vw,2.6rem); line-height:1.15;
  font-weight:600; letter-spacing:-.012em; text-wrap:balance; margin-bottom:14px; }}
.lede {{ max-width:64ch; color:var(--soft); font-size:1.02rem; }}
.lede + .lede {{ margin-top:11px; }}
.lede b {{ color:var(--ink); font-weight:600; }}
.tally {{ display:flex; gap:26px; flex-wrap:wrap; background:var(--surface);
  border:1px solid var(--rule); border-radius:3px; padding:14px 18px; margin:28px 0 36px; }}
.cell {{ display:flex; flex-direction:column; }}
.num {{ font-family:var(--mono); font-variant-numeric:tabular-nums; font-size:1.3rem;
  font-weight:600; line-height:1.1; }}
.cell.open .num {{ color:var(--open); }}
.lab {{ font-size:.7rem; letter-spacing:.07em; text-transform:uppercase; color:var(--faint); }}
.rec {{ margin-bottom:46px; }}
.rec header {{ display:flex; align-items:baseline; gap:14px; flex-wrap:wrap;
  padding-bottom:11px; border-bottom:2px solid var(--ink); margin-bottom:10px; }}
.rec h2 {{ font-family:var(--serif); font-size:1.5rem; font-weight:600; }}
.rec .meta {{ font-family:var(--mono); font-size:.75rem; color:var(--faint); margin-left:auto; }}
.item {{ display:grid; grid-template-columns:220px 1fr; gap:0 22px; background:var(--surface);
  border:1px solid var(--rule2); border-left:3px solid var(--rule); border-radius:2px;
  padding:14px 16px; margin-bottom:6px; align-items:start; }}
.item.k-changed {{ border-left-color:var(--changed); }}
.item.k-confirmed {{ border-left-color:var(--ok); }}
.item.k-variable, .item.k-inapplicable {{ border-left-color:var(--accent); }}
.item.k-residual {{ border-left-color:var(--faint); }}
.item.open {{ background:var(--open-bg); border-color:var(--open); border-left-color:var(--open); }}
.item.hidden {{ display:none; }}
.code {{ font-family:var(--mono); font-size:.84rem; font-weight:600; color:var(--accent); }}
.dim {{ font-size:.79rem; color:var(--soft); }}
.val {{ margin-top:7px; font-family:var(--mono); font-size:.78rem; word-break:break-word; }}
.val .was {{ color:var(--faint); text-decoration:line-through; }}
.val .arrow {{ color:var(--faint); margin:0 5px; }}
.val .now {{ font-weight:600; }}
.tag {{ margin-top:6px; font-size:.68rem; letter-spacing:.05em; text-transform:uppercase;
  color:var(--faint); }}
.body p {{ margin:0 0 9px; font-size:.9rem; line-height:1.5; }}
.body p:last-of-type {{ margin-bottom:0; }}
.lbl {{ display:block; font-family:var(--mono); font-size:.67rem; letter-spacing:.05em;
  text-transform:uppercase; color:var(--faint); margin-bottom:2px; }}
.alt {{ color:var(--soft); }}
.q .lbl {{ color:var(--open); }}
.src {{ font-family:var(--mono); font-size:.7rem; color:var(--faint); margin-top:10px;
  padding-top:8px; border-top:1px dashed var(--rule); }}
.filters {{ display:flex; gap:6px; flex-wrap:wrap; margin-left:auto; }}
button {{ font:inherit; font-size:.8rem; color:var(--ink); background:var(--surface2);
  border:1px solid var(--rule); border-radius:3px; padding:6px 12px; cursor:pointer; }}
button:hover {{ border-color:var(--accent); color:var(--accent); }}
button:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}
button.on {{ background:var(--accent); border-color:var(--accent); color:var(--surface); }}
.foot {{ margin-top:36px; padding-top:16px; border-top:1px solid var(--rule);
  font-size:.82rem; color:var(--faint); max-width:66ch; }}
@media (max-width:720px) {{ .item {{ grid-template-columns:1fr; gap:12px; }}
  .rec .meta {{ margin-left:0; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition:none !important; }} }}
</style>

<div class="wrap">
<header class="top">
  <div class="eyebrow">RAG World · разбор конфигураций</div>
  <h1>Чем обосновано каждое значение</h1>
  <p class="lede">Уровень зрелости вычисляется правилом и воспроизводится
    повторным запуском. Значение измерения так проверить нельзя: это вывод из
    текста статьи, и убедиться в нём можно только через рассуждение, которое к
    нему привело. Здесь оно записано целиком.</p>
  <p class="lede">У каждого пункта разделено <b>что делает система</b> и
    <b>почему из этого следует значение</b>: первое проверяется по источнику,
    второе — по схеме измерений. Отдельно названо значение, которое не подошло,
    — без него выбор выглядел бы единственно возможным.</p>
  <p class="lede">Пункты, где источник допускает другое прочтение, помечены.
    Решение по ним принято и записано; помечены они не как вопрос к вам, а как
    место, где я мог ошибиться правдоподобно.</p>
</header>

<div class="tally">
  <div class="cell"><span class="num">{records}</span><span class="lab">записей</span></div>
  <div class="cell"><span class="num">{total}</span><span class="lab">обоснований</span></div>
  <div class="cell open"><span class="num">{questioned}</span>
    <span class="lab">спорных прочтений</span></div>
  <div class="filters">
    <button data-f="all" class="on">все</button>
    <button data-f="open">спорные</button>
    <button data-f="changed">изменённые</button>
    <button data-f="residual">остатки</button>
  </div>
</div>

{sections}

<p class="foot">Свидетельства изложены моими словами со ссылкой на раздел
  источника, а не дословными выдержками. Значения на странице сверяются с
  реестром при сборке: обоснование, разошедшееся с данными, останавливает её.</p>
</div>

<script>
(() => {{
  "use strict";
  const items = [...document.querySelectorAll(".item")];
  document.querySelectorAll("[data-f]").forEach((btn) => {{
    btn.addEventListener("click", () => {{
      const f = btn.dataset.f;
      document.querySelectorAll("[data-f]").forEach((b) => b.classList.toggle("on", b === btn));
      items.forEach((it) => {{
        const show = f === "all"
          || (f === "open" && it.classList.contains("open"))
          || (f === "changed" && it.classList.contains("k-changed"))
          || (f === "residual" && it.classList.contains("k-residual"));
        it.classList.toggle("hidden", !show);
      }});
      document.querySelectorAll(".rec").forEach((rec) => {{
        const any = [...rec.querySelectorAll(".item")].some((i) => !i.classList.contains("hidden"));
        rec.style.display = any ? "" : "none";
      }});
    }});
  }});
}})();
</script>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    notes = load_notes()
    if not notes:
        print("обоснований нет: data/parse_notes.jsonl пуст")
        return 0

    problems = check(notes)
    if problems:
        sys.stderr.write(f"обоснования разошлись с реестром: {len(problems)}\n")
        for problem in problems:
            sys.stderr.write(f"  {problem}\n")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(notes), encoding="utf-8")
    print(f"страница собрана: {args.out} ({len(notes)} обоснований)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
