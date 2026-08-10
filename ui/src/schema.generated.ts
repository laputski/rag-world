// СГЕНЕРИРОВАНО из core/dimensions_schema.py командой `make artifacts`.
// Не править вручную: правка потеряется и разведёт два описания схемы.

export interface DimensionSpec {
  code: string;
  name: string;
  stratum: string;
  core: boolean;
  default: string;
  values: string[];
}

export const SCHEMA_SIZE = 28;

export const STRATA: { code: string; name: string }[] = [
  { code: "A", name: "Представление знаний" },
  { code: "B", name: "Формулировка и маршрутизация запроса" },
  { code: "C", name: "Извлечение" },
  { code: "D", name: "Формирование контекста" },
  { code: "E", name: "Синтез и контроль" },
  { code: "F", name: "Эволюция состояния" },
  { code: "G", name: "Оболочка ограничений" },
];

export const DIMENSIONS: DimensionSpec[] = [
  { code: "A1", name: "Единица извлечения", stratum: "A", core: true, default: "passage", values: ["passage", "proposition", "entity", "node_edge", "page_image", "table_row", "summary_node"] },
  { code: "A2", name: "Сегментация", stratum: "A", core: true, default: "fixed", values: ["fixed", "structure_aware", "late_chunking", "semantic", "none"] },
  { code: "A3", name: "Обогащение единицы", stratum: "A", core: true, default: "none", values: ["none", "context_prefix", "summary", "extracted_triples", "metadata"] },
  { code: "A4", name: "Топология индекса", stratum: "A", core: true, default: "flat", values: ["flat", "tree", "graph", "hypergraph", "community_hierarchy"] },
  { code: "A5", name: "Модель представления", stratum: "A", core: true, default: "dense_single", values: ["lexical", "dense_single", "dense_multi_late_interaction", "symbolic", "vision_language", "none"] },
  { code: "A6", name: "Темпоральность", stratum: "A", core: false, default: "snapshot", values: ["snapshot", "append_only", "bitemporal"] },
  { code: "A7", name: "Модальность", stratum: "A", core: true, default: "text", values: ["text", "image", "table", "audio", "scene_3d"] },
  { code: "A8", name: "Происхождение структуры индекса", stratum: "A", core: true, default: "none", values: ["none", "given", "extracted", "computed"] },
  { code: "B1", name: "Преобразование запроса", stratum: "B", core: true, default: "identity", values: ["identity", "hyde", "multi_reformulation", "step_back", "subquestion_decomposition"] },
  { code: "B2", name: "Маршрутизация", stratum: "B", core: true, default: "static", values: ["static", "trained_classifier", "llm_router", "cost_aware_policy"] },
  { code: "C1", name: "Оператор поиска", stratum: "C", core: true, default: "ann", values: ["ann", "lexical", "graph_traversal", "boolean_query", "tree_navigation", "spatial_range"] },
  { code: "C2", name: "Управление обходом", stratum: "C", core: true, default: "single_shot", values: ["single_shot", "multi_hop_fixed", "iterative_stopping", "agentic_open_loop"] },
  { code: "C3", name: "Слияние источников", stratum: "C", core: true, default: "none", values: ["none", "rrf", "score_normalization", "learned_fusion"] },
  { code: "C4", name: "Распределённость", stratum: "C", core: false, default: "single_store", values: ["single_store", "multiple_local", "federation"] },
  { code: "D1", name: "Переранжирование", stratum: "D", core: true, default: "cross_encoder", values: ["none", "cross_encoder", "graph_structural", "set_cover", "path_pruning"] },
  { code: "D2", name: "Отбор и сжатие", stratum: "D", core: true, default: "top_k", values: ["top_k", "budget_aware", "abstractive_compression", "latent_compression"] },
  { code: "D3", name: "Компоновка", stratum: "D", core: true, default: "natural_order", values: ["natural_order", "reliability_ascending", "hierarchical"] },
  { code: "E1", name: "Режим генерации", stratum: "E", core: true, default: "single_pass", values: ["single_pass", "draft_verify", "ensemble_fragments", "multi_agent"] },
  { code: "E2", name: "Контроль обоснованности", stratum: "E", core: true, default: "none", values: ["none", "pre_gen_grounding", "post_gen_check", "decoding_reflection", "decoding_trigger", "external_judge"] },
  { code: "E3", name: "Атрибуция", stratum: "E", core: true, default: "none", values: ["none", "document_level", "fragment_level", "claim_level"] },
  { code: "E5", name: "Связь порождения с извлечением", stratum: "E", core: true, default: "none", values: ["none", "generation_seeds", "mutual_loop"] },
  { code: "E4", name: "Политика отказа", stratum: "E", core: true, default: "no_refusal", values: ["no_refusal", "confidence_threshold", "domain_policy"] },
  { code: "F1", name: "Запись обратно", stratum: "F", core: false, default: "none", values: ["none", "episodic", "consolidating"] },
  { code: "F2", name: "Разрешение противоречий", stratum: "F", core: false, default: "none", values: ["none", "by_time", "by_authority", "explicit_reconciliation"] },
  { code: "F3", name: "Забывание", stratum: "F", core: false, default: "none", values: ["none", "by_ttl", "by_significance_decay"] },
  { code: "G1", name: "Приватность", stratum: "G", core: true, default: "open", values: ["open", "isolated_circuit", "differential_privacy", "tee"] },
  { code: "G2", name: "Место исполнения", stratum: "G", core: true, default: "server", values: ["server", "edge_device", "mixed"] },
  { code: "G3", name: "Обучаемость компонентов", stratum: "G", core: true, default: "frozen", values: ["frozen", "trained_retriever", "trained_reader", "joint_training"] },
];

/** Коды измерений страты в порядке объявления. */
export function dimensionsOf(stratum: string): DimensionSpec[] {
  return DIMENSIONS.filter((d) => d.stratum === stratum);
}
