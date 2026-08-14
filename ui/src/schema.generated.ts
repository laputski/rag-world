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
  { code: "A", name: "Knowledge representation" },
  { code: "B", name: "Query formulation" },
  { code: "C", name: "Retrieval" },
  { code: "D", name: "Context assembly" },
  { code: "E", name: "Synthesis and control" },
  { code: "F", name: "State evolution" },
  { code: "G", name: "Constraint envelope" },
];

export const DIMENSIONS: DimensionSpec[] = [
  { code: "A1", name: "Unit of retrieval", stratum: "A", core: true, default: "passage", values: ["passage", "proposition", "entity", "node_edge", "page_image", "table_row", "summary_node"] },
  { code: "A2", name: "Segmentation", stratum: "A", core: true, default: "fixed", values: ["fixed", "structure_aware", "late_chunking", "semantic", "none"] },
  { code: "A3", name: "Unit enrichment", stratum: "A", core: true, default: "none", values: ["none", "context_prefix", "summary", "extracted_triples", "metadata"] },
  { code: "A4", name: "Index topology", stratum: "A", core: true, default: "flat", values: ["flat", "tree", "graph", "hypergraph", "community_hierarchy"] },
  { code: "A5", name: "Representation model", stratum: "A", core: true, default: "dense_single", values: ["lexical", "dense_single", "dense_multi_late_interaction", "symbolic", "vision_language", "none"] },
  { code: "A6", name: "Temporality", stratum: "A", core: false, default: "snapshot", values: ["snapshot", "append_only", "bitemporal"] },
  { code: "A7", name: "Modality", stratum: "A", core: true, default: "text", values: ["text", "image", "table", "audio", "scene_3d"] },
  { code: "A8", name: "Origin of index structure", stratum: "A", core: true, default: "none", values: ["none", "given", "extracted", "computed"] },
  { code: "B1", name: "Query transformation", stratum: "B", core: true, default: "identity", values: ["identity", "hyde", "multi_reformulation", "step_back", "subquestion_decomposition"] },
  { code: "B2", name: "Routing", stratum: "B", core: true, default: "static", values: ["static", "trained_classifier", "llm_router", "cost_aware_policy"] },
  { code: "C1", name: "Search operator", stratum: "C", core: true, default: "ann", values: ["ann", "lexical", "graph_traversal", "boolean_query", "tree_navigation", "spatial_range"] },
  { code: "C2", name: "Traversal control", stratum: "C", core: true, default: "single_shot", values: ["single_shot", "multi_hop_fixed", "iterative_stopping", "agentic_open_loop"] },
  { code: "C3", name: "Source fusion", stratum: "C", core: true, default: "none", values: ["none", "rrf", "score_normalization", "learned_fusion"] },
  { code: "C4", name: "Distribution", stratum: "C", core: false, default: "single_store", values: ["single_store", "multiple_local", "federation"] },
  { code: "D1", name: "Reranking", stratum: "D", core: true, default: "none", values: ["none", "cross_encoder", "graph_structural", "set_cover", "path_pruning"] },
  { code: "D2", name: "Selection and compression", stratum: "D", core: true, default: "top_k", values: ["top_k", "budget_aware", "abstractive_compression", "latent_compression"] },
  { code: "D3", name: "Arrangement", stratum: "D", core: true, default: "natural_order", values: ["natural_order", "reliability_ascending", "hierarchical"] },
  { code: "E1", name: "Generation mode", stratum: "E", core: true, default: "single_pass", values: ["single_pass", "draft_verify", "ensemble_fragments", "multi_agent"] },
  { code: "E2", name: "Groundedness control", stratum: "E", core: true, default: "none", values: ["none", "pre_gen_grounding", "post_gen_check", "decoding_reflection", "decoding_trigger", "external_judge"] },
  { code: "E3", name: "Attribution", stratum: "E", core: true, default: "none", values: ["none", "document_level", "fragment_level", "claim_level"] },
  { code: "E5", name: "Coupling of generation to retrieval", stratum: "E", core: true, default: "none", values: ["none", "generation_seeds", "mutual_loop"] },
  { code: "E4", name: "Refusal policy", stratum: "E", core: true, default: "no_refusal", values: ["no_refusal", "confidence_threshold", "domain_policy"] },
  { code: "F1", name: "Write-back", stratum: "F", core: false, default: "none", values: ["none", "episodic", "consolidating"] },
  { code: "F2", name: "Conflict resolution", stratum: "F", core: false, default: "none", values: ["none", "by_time", "by_authority", "explicit_reconciliation"] },
  { code: "F3", name: "Forgetting", stratum: "F", core: false, default: "none", values: ["none", "by_ttl", "by_significance_decay"] },
  { code: "G1", name: "Privacy", stratum: "G", core: true, default: "open", values: ["open", "isolated_circuit", "differential_privacy", "tee"] },
  { code: "G2", name: "Execution site", stratum: "G", core: true, default: "server", values: ["server", "edge_device", "mixed"] },
  { code: "G3", name: "Trainability of components", stratum: "G", core: true, default: "frozen", values: ["frozen", "trained_retriever", "trained_reader", "joint_training"] },
];

/** Коды измерений страты в порядке объявления. */
export function dimensionsOf(stratum: string): DimensionSpec[] {
  return DIMENSIONS.filter((d) => d.stratum === stratum);
}
