"""The hand-drawn architecture diagrams stay true to the records they illustrate.

A diagram on a technology card is drawn by a person from the primary source, so
nothing derives it and nothing keeps it current. `check_diagrams` is what holds
it to the record. Two things are checked here.

The real diagrams pass. That alone proves little: clean data confirms only its
own cleanliness, not that a violation would be caught.

So every rule also gets a bait. A sound diagram is built in a temporary
directory, one defect is planted in it, and the check must name that defect. The
sound diagram must yield nothing, or the guard cries over correct data and stops
being listened to.

The first bait is the defect that started this work. The PathRAG record read the
query as passed through untouched, while its source extracts keywords from it; a
diagram drawn from the source disagreed with the record, and the record was
wrong. Putting the old value back must break the build.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import validate_data  # noqa: E402

from services.registry import store  # noqa: E402

PREPRINT = "https://arxiv.org/abs/2502.14902"

SPEC = {
    "technology_id": "alpha",
    "source": {"label": "arXiv:2502.14902v2", "url": "https://arxiv.org/html/2502.14902v2"},
    "sections": [
        {"key": "1", "title": "Preliminaries", "anchor": "Sx3"},
        {"key": "2", "title": "Node Retrieval", "anchor": "Sx4.SSx1"},
    ],
    "rows": [["corpus", "graph"], ["keywords", "paths"]],
    "nodes": {
        "corpus": {"section": "1"},
        "graph": {"section": "1", "codes": {"A4": "graph"}},
        "keywords": {"section": "2", "codes": {"B1": "key_extraction"}},
        "paths": {"section": "2", "codes": {"C1": "graph_traversal"}},
    },
    "edges": [["graph", "paths"]],
    "omitted": [],
}

WORDING = {
    "ru": {"alpha": {"nodes": {
        "corpus": {"title": "Корпус"}, "graph": {"title": "Граф"},
        "keywords": {"title": "Ключевые слова"}, "paths": {"title": "Пути"},
    }, "omitted": {}}},
    "en": {"alpha": {"nodes": {
        "corpus": {"title": "Corpus"}, "graph": {"title": "Graph"},
        "keywords": {"title": "Keywords"}, "paths": {"title": "Paths"},
    }, "omitted": {}}},
}

RECORD = {
    "id": "alpha",
    "name": "Alpha",
    "kind": "architecture",
    "groups": ["A"],
    "configuration": {
        "A4": "graph", "A8": "extracted", "B1": "key_extraction", "C1": "graph_traversal",
    },
    "links": [{"url": PREPRINT, "kind": "preprint"}],
}


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A registry of one record and a sound diagram of it, ready to be spoiled.

    A8 departs from the base and stands on no step; the sound diagram names it
    among the omissions, so the rule of completeness has something to hold.
    """
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "data")
    (tmp_path / "data" / "diagrams").mkdir(parents=True)
    spec = copy.deepcopy(SPEC)
    spec["omitted"] = ["A8"]
    wording = copy.deepcopy(WORDING)
    wording["ru"]["alpha"]["omitted"] = {"A8": "Происхождение структуры видно из шага графа."}
    wording["en"]["alpha"]["omitted"] = {
        "A8": "The origin of the structure shows in the graph step."
    }
    return {"root": tmp_path, "spec": spec, "wording": wording, "record": copy.deepcopy(RECORD)}


def run(world, vocabulary=None) -> list[str]:
    root = world["root"]
    (root / "data" / "diagrams" / f"{world['spec']['technology_id']}.json").write_text(
        json.dumps(world["spec"], ensure_ascii=False), encoding="utf-8"
    )
    for language, table in world["wording"].items():
        (root / "i18n" / language).mkdir(parents=True, exist_ok=True)
        (root / "i18n" / language / "diagrams.json").write_text(
            json.dumps(table, ensure_ascii=False), encoding="utf-8"
        )
    tech = store.Technology(**world["record"])
    return validate_data.check_diagrams([tech], vocabulary or {}, wording_dir=root / "i18n")


def complains(fragment: str, problems: list[str]) -> bool:
    return any(fragment in problem for problem in problems)


# ─── The real data ───────────────────────────────────────────────────────────


def test_the_real_diagrams_agree_with_their_records():
    problems = validate_data.check_diagrams(
        store.load_technologies(), validate_data._residual_vocabulary()
    )
    assert not problems, "the diagrams disagree with the registry:\n  " + "\n  ".join(problems)


def test_pathrag_has_a_diagram():
    """The pilot is drawn; an empty directory would pass every rule vacuously."""
    assert (store.DATA_DIR / "diagrams" / "pathrag.json").exists()


# ─── The baits ───────────────────────────────────────────────────────────────


def test_a_sound_diagram_yields_nothing(world):
    assert run(world) == []


def test_a_step_disagreeing_with_the_record_is_caught(world):
    """The defect that started this work: the record read the query untouched."""
    world["record"]["configuration"]["B1"] = "identity"
    assert complains("says B1='key_extraction', while the record holds 'identity'", run(world))


def test_a_variable_dimension_may_show_any_of_its_values(world):
    world["record"]["configuration"]["B1"] = "multi_reformulation"
    world["record"]["configuration_variable"] = ["B1"]
    assert run(world) == []


def test_a_step_on_an_inapplicable_dimension_is_caught(world):
    del world["record"]["configuration"]["B1"]
    world["record"]["configuration_inapplicable"] = ["B1"]
    assert complains("carries B1, which the record marks inapplicable", run(world))


def test_a_value_outside_the_schema_is_caught(world):
    world["spec"]["nodes"]["graph"]["codes"]["A4"] = "lattice"
    assert complains("which the schema does not contain", run(world))


def test_an_unknown_dimension_is_caught(world):
    world["spec"]["nodes"]["graph"]["codes"]["Z9"] = "graph"
    assert complains("unknown dimension 'Z9'", run(world))


def test_a_step_without_a_section_is_caught(world):
    world["spec"]["nodes"]["corpus"]["section"] = "7"
    assert complains("step 'corpus' names no section of the source", run(world))


def test_a_section_without_an_anchor_is_caught(world):
    world["spec"]["sections"][0]["anchor"] = ""
    assert complains("lacks a title or an anchor", run(world))


def test_a_source_the_record_does_not_list_is_caught(world):
    world["spec"]["source"]["url"] = "https://arxiv.org/html/2401.00001v1"
    assert complains("is not among the links of the record", run(world))


def test_a_decision_dropped_silently_is_caught(world):
    world["spec"]["omitted"] = []
    assert complains("the record decides A8='extracted'", run(world))


def test_an_omission_where_nothing_is_decided_is_caught(world):
    world["spec"]["omitted"] = ["A8", "D1"]
    world["wording"]["ru"]["alpha"]["omitted"]["D1"] = "нет"
    world["wording"]["en"]["alpha"]["omitted"]["D1"] = "none"
    assert complains("D1 is omitted, yet the record makes no decision there", run(world))


def test_a_decision_both_shown_and_omitted_is_caught(world):
    world["spec"]["omitted"] = ["A8", "B1"]
    world["wording"]["ru"]["alpha"]["omitted"]["B1"] = "нет"
    world["wording"]["en"]["alpha"]["omitted"]["B1"] = "none"
    assert complains("B1 is both shown and omitted", run(world))


def test_an_omission_without_a_reason_is_caught(world):
    del world["wording"]["en"]["alpha"]["omitted"]["A8"]
    assert complains("the omission of A8 has no en reason", run(world))


def test_a_step_without_english_wording_is_caught(world):
    del world["wording"]["en"]["alpha"]["nodes"]["paths"]
    assert complains("step 'paths' has no en wording", run(world))


def test_wording_for_a_step_not_drawn_is_caught(world):
    world["wording"]["ru"]["alpha"]["nodes"]["ghost"] = {"title": "Призрак"}
    assert complains("names a step 'ghost' not drawn", run(world))


def test_cyrillic_in_the_english_wording_is_caught(world):
    world["wording"]["en"]["alpha"]["nodes"]["graph"]["title"] = "Граф"
    assert complains("Cyrillic in the English wording", run(world))


def test_a_step_standing_in_no_row_is_caught(world):
    world["spec"]["rows"][1].remove("paths")
    world["spec"]["edges"] = []
    assert complains("step 'paths' stands in no row", run(world))


def test_an_undefined_step_in_a_row_is_caught(world):
    world["spec"]["rows"][0].append("ghost")
    assert complains("the row holds an undefined step 'ghost'", run(world))


def test_an_edge_to_an_undefined_step_is_caught(world):
    world["spec"]["edges"].append(["graph", "ghost"])
    assert complains("names an undefined step", run(world))


def test_an_edge_that_skips_a_row_or_stays_in_one_is_caught(world):
    world["spec"]["edges"] = [["corpus", "graph"]]
    assert complains("must join a step to one in the next row", run(world))


def test_a_residual_the_record_lacks_is_caught(world):
    world["spec"]["nodes"]["paths"]["residual"] = "flow_decay"
    assert complains("names the residual 'flow_decay'", run(world, {"flow_decay": {}}))


def explain_residual(world, mechanism: str) -> None:
    (world["root"] / "data" / "parse_notes.jsonl").write_text(json.dumps({
        "technology_id": "alpha", "residual": mechanism,
        "did": "Пути гаснут по мере удаления.", "did_en": "Paths fade with distance.",
    }, ensure_ascii=False) + "\n", encoding="utf-8")


def test_a_residual_nobody_justified_is_caught(world):
    """The bait: the card of the step would show the bare code to the reader."""
    world["record"]["residual"] = ["flow_decay"]
    world["spec"]["nodes"]["paths"]["residual"] = "flow_decay"
    assert complains("which no justification explains", run(world, {"flow_decay": {}}))


def test_a_justified_residual_passes(world):
    world["record"]["residual"] = ["flow_decay"]
    world["spec"]["nodes"]["paths"]["residual"] = "flow_decay"
    explain_residual(world, "flow_decay")
    assert not complains("residual", run(world, {"flow_decay": {}}))


def test_wording_for_a_record_without_a_diagram_is_caught(world):
    world["wording"]["en"]["beta"] = {"nodes": {}}
    assert complains("wording for 'beta', which has no diagram", run(world))


def test_a_file_named_apart_from_its_record_is_caught(world):
    world["spec"]["technology_id"] = "alpha"
    run(world)
    (world["root"] / "data" / "diagrams" / "alpha.json").rename(
        world["root"] / "data" / "diagrams" / "beta.json"
    )
    tech = store.Technology(**world["record"])
    problems = validate_data.check_diagrams([tech], {}, wording_dir=world["root"] / "i18n")
    assert complains("is named apart from the record", problems)


def test_a_loop_forward_is_caught(world):
    world["spec"]["loops"] = [["keywords", "paths"]]
    assert complains("the loop keywords→paths must return to an earlier step", run(world))


def test_a_loop_two_rows_back_is_caught(world):
    world["spec"]["rows"].append(["answer"])
    world["spec"]["nodes"]["answer"] = {"section": "2"}
    world["spec"]["edges"].append(["paths", "answer"])
    for language, title in (("ru", "Ответ"), ("en", "Answer")):
        world["wording"][language]["alpha"]["nodes"]["answer"] = {"title": title}
    world["spec"]["loops"] = [["answer", "corpus"]]
    assert complains("the loop answer→corpus must return to an earlier step", run(world))


def test_a_loop_within_its_row_or_to_the_previous_one_passes(world):
    world["spec"]["loops"] = [["paths", "keywords"], ["paths", "graph"]]
    assert run(world) == []


def test_a_loop_to_an_undefined_step_is_caught(world):
    world["spec"]["loops"] = [["paths", "ghost"]]
    assert complains("the loop paths→ghost names an undefined step", run(world))


def test_a_break_between_steps_that_are_not_neighbours_is_caught(world):
    world["spec"]["breaks"] = [["corpus", "paths"]]
    assert complains("the break corpus|paths must name neighbours of one row", run(world))


def test_a_break_between_neighbours_passes(world):
    world["spec"]["breaks"] = [["keywords", "paths"]]
    assert run(world) == []


def test_a_line_in_one_language_only_is_caught(world):
    """Found on the first full run: three second lines existed in Russian only."""
    world["wording"]["ru"]["alpha"]["nodes"]["paths"]["sub"] = "с возвратом"
    assert complains("step 'paths' has a ru sub without its twin", run(world))


def test_an_anchor_written_with_its_hash_is_caught(world):
    """Found by the verification pass: two links led to "##section"."""
    world["spec"]["sections"][0]["anchor"] = "#how-it-works"
    assert complains("the anchor of section '1' starts with '#'", run(world))
