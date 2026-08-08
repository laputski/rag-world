# RAG Taxonomy — исчерпывающий реестр архитектур RAG (июль 2026)

> Источник-документ: «Сравнительный анализ архитектур RAG» (июль 2026) + веб-исследование
> 2024–2026 (arXiv, NeurIPS/ICLR/ACL/EMNLP/AAAI, GitHub). Цель — составить
> максимально полный реестр известных типов/вариантов RAG и их классифицировать.
> Маппинг каждого типа на способы подключения к платформе — в
> [[rag-platform-evolution]] (блок A). Декомпозиция в оси конструктора — в
> [[rag-constructor]].

Версия: 1.0.0

---

## Как читать этот документ

Реестр устроен в трёх ортогональных срезах:

1. **[Реестр-таблица](#реестр-по-семействам)** — все типы, сгруппированные по 11 семействам.
2. **[Матрица зрелости](#матрица-зрелости)** — насколько каждый тип оформлен (статья → библиотека → продукт).
3. **[Ось «общее ↔ конкретное»](#ось-общее--конкретное)** — парадигма ли это, конкретная архитектура, техника-примитив или фреймворк.

Обозначения зрелости:
- 📄 — статья/arXiv-preprint только
- 🏆 — peer-reviewed (NeurIPS / ICLR / ACL / EMNLP / AAAI / MLSys / SIGIR)
- 📦 — есть open-source библиотека с активным сообществом
- 🏭 — commercial product / production deployment
- 💡 — концепция/blog без формальной публикации

---

## Реестр по семействам

### A. Self-Reflective / Corrective / Active

| Тип | Core idea (1 предложение) | Источник / зрелость |
|---|---|---|
| **Self-RAG** | Обучает генератор токенам рефлексии (Retrieve/ISREL/ISGND/ISUSE), чтобы он сам решал, искать ли и насколько ответ заземлён. | 🏆 ICLR 2024 Oral · arXiv 2310.11511 |
| **Corrective RAG (CRAG)** | Лёгкий Retrieval Evaluator перед генерацией; при низкой уверенности — веб-поиск, при неоднозначности — гибрид. | 📄 arXiv 2401.15884 · 📦 LangGraph impl |
| **FLARE / Active RAG** | Генерирует tentative-предложение и инициирует retrieval только при неуверенности (низкий logprob / триггер поиска). | 🏆 EMNLP 2023 · arXiv 2305.06983 |
| **Speculative RAG** | Draft-then-verify: маленький specialist-LM генерирует параллельно драфты по подмножествам, большой generalist-LM верифицирует. | 🏆 ICLR 2025 · arXiv 2407.08223 (Google) |
| **REPLUG** | LLM как чёрный ящик: прогон над каждым пассажем параллельно + ensemble предсказаний, взвешенный retrieval-оценками. | 🏆 NAACL 2024 · arXiv 2301.12652 |
| **RA-ISF** | Итеративная декомпозиция задачи → retrieve → generate → self-feedback, пока подзадача не разрешится. | 📄 arXiv |
| **SimRAG** | Self-training: LLM учится QA + генерации вопросов, адаптируя RAG к домену без разметки. | 🏆 NAACL 2025 |

### B. Graph-based

| Тип | Core idea | Источник / зрелость |
|---|---|---|
| **Microsoft GraphRAG** | Глобальный граф знаний + сообщества (Лейден) + Map-Reduce отчёты по сообществам (Local/Global/DRIFT). | 🏭 product · 📦 github.com/microsoft/graphrag |
| **LightRAG** | Двухуровневый граф (low-level сущности / high-level темы) + инкрементальное обновление без перестройки. | 📦 github.com/HKUDS/LightRAG · 🏆 ACL 2025 Findings |
| **HippoRAG / HippoRAG 2** | Имитация гиппокампа: OpenIE + Personalized PageRank для multi-hop за один проход. | 🏆 NeurIPS 2024 · arXiv 2405.14831 |
| **PathRAG** | Потоковый прунинг путей между узлами (вместо neighbor-dumping) с затуханием по расстоянию. | 📄 arXiv 2502.14902 |
| **ArchRAG** | Атрибутированные сообщества (AC) + индекс C-HNSW + адаптивный спуск (глобал/локал). | 📄 arXiv 2502.09891 · AAAI |
| **TagRAG** | Иерархические цепочки доменных тегов (вместо тысяч сущностей) — для малых LLM и лимита ресурсов. | 📄 arXiv 2601.05254 |
| **S-Path-RAG** | Семантически взвешенные k-shortest пути + beam + random walks + Neural-Socratic dialogue loop. | 📄 arXiv (semantic scholar) |
| **MemGraphRAG** | Мультиагентная экстракция графа через общую трёхслойную глобальную память; разрешение противоречий на индексации. | 📄 arXiv 2606.00610 |
| **OG-RAG** | Онтологическое заземление: проекция текста в гиперграф (s,a,v-тройки) + жадный Set Cover. | 📄 arXiv 2412.15235 · 🏆 EMNLP 2025 |
| **Think-on-Graph (ToG / ToG-2)** | LLM-агент итеративно beam-search по KG; ToG-2 чередует retrieval из текста и KG. | 🏆 ICLR 2024 · arXiv 2307.07697 |
| **GNN-RAG** | GNN рассуждает над KG и даёт candidate-пути в LLM (симбиоз GNN-вывода и LLM). | 🏆 ACL 2025 Findings · arXiv 2405.20139 |
| **G-RAG** | GNN-реранкер между ретривером и ридером, учитывающий структуру document graph. | 📄 arXiv 2405.18414 |
| **KAG** | Knowledge Augmented Generation: структурированный KG + retrieval + семантический reasoning для профессиональной точности. | 📦 OpenSPG/KAG |
| **GraphReader** | Граф длинного документа (чанки → атомарные факты → ключевые элементы) + агент-навигатор. | 📄 arXiv · 📦 Neo4j/LangGraph impl |
| **nano-graphrag** | Лёгкая реимплементация MSFT GraphRAG для быстрого экспериментирования. | 📦 github.com/gusye1234/nano-graphrag |
| **PGraphRAG** | Персонализация graph RAG через user-centric KG. | 🏆 PACLIC 2025 |
| **SURGE** | Conditioning генерации на селективно извлечённых подграфах KG. | 💡 survey-level |

### C. Agentic / Multi-step / Multi-Agent

| Тип | Core idea | Источник / зрелость |
|---|---|---|
| **Agentic RAG** *(парадигма)* | RAG, где LLM-агент сам решает когда/что/сколько раз искать и какие инструменты дёргать (обобщение). | 💡 концепция · 📦 LlamaIndex/LangChain workflows |
| **ReAct** | Чередование reasoning-traces и tool/action-вызовов (вкл. retrieval) — канон агентной парадигмы. | 🏆 ICLR 2023 · arXiv 2210.03629 |
| **IRCoT** | Чередует каждое предложение CoT с шагом retrieval — CoT ведёт retrieval, retrieval ведёт CoT. | 🏆 ACL 2023 · arXiv 2212.10509 |
| **RAGEN** | RL-система обучения LLM-агентов в multi-turn стохастических средах (StarPO). | 📄 arXiv 2504.20073 · 📦 github.com/mll-lab-nu/RAGEN |
| **MA-RAG** | Декомпозиция RAG-пайплайна по координируемым агентам (multi-agent) для многшагового reasoning. | 📄 arXiv |
| **MAPPO-RAG** | Каждый компонент RAG = агент; вся пайплайна оптимизируется как cooperative multi-agent RL (MAPPO). | 🏆 NeurIPS 2025 |
| **Auto-RAG** | Итеративно/непрерывно дёргает ретривер во время генерации, поддерживая релевантность документов. | 📄 arXiv |
| **S³ (Search Agent)** | Multi-turn RL-trained поисковый агент поверх RAGEN/VERL. | 🏆 EMNLP 2025 |

### D. Modular / Routing / Training-paradigm

| Тип | Core idea | Источник / зрелость |
|---|---|---|
| **Modular RAG** *(парадигма)* | RAG как композиция модулей (retrieve/rerank/fuse/ground/...) — общая рамка, частными случаями которой являются почти все остальные. | 💡 survey/framework |
| **Adaptive RAG** | Выученный роутер выбирает no-retrieval / single-step / multi-step retrieval под конкретный запрос. | 🏆 NAACL/ACL 2024 · arXiv 2403.14403 |
| **Federated RAG** *(парадигма)* | Запрос маршрутизируется/сливается через несколько независимых источников RAG/баз знаний. | 💡 концепция |
| **Standard HybridRAG** | BM25 (sparse) + dense-vector + слияние RRF + нейросетевой reranker — золотой стандарт продакшна. | 🏭 industry-standard · 📦 повсеместно |
| **RA-DIT** | Joint fine-tuning и LLM-ридера, и ретривера (dual instruction tuning) — retrofit любой LLM с RAG. | 🏆 ICLR 2024 · arXiv 2310.01352 (Meta) |
| **RAFT** | Fine-tuning на смеси gold+distractor документов, принуждающий CoT цитировать gold (open-book domain RAG). | 📄 arXiv 2403.10131 (Gorilla/Berkeley) |
| **SAIL** | Fine-tuning LLM на инструкциях, аугментированных реальными search-API результатами. | 🏆 EMNLP 2023 Findings · arXiv 2305.15225 |

### E. Multimodal

| Тип | Core idea | Источник / зрелость |
|---|---|---|
| **Multimodal RAG** *(парадигма)* | Retrieval/generation над несколькими модальностями (текст + изображение + таблицы). | 💡 концепция |
| **MuRAG** | Первый multimodal retrieval-augmented transformer с непараметрической памятью (изображения+текст). | 🏆 EMNLP 2022 · arXiv 2210.02928 (Google) |
| **RA-CM3** | Первый retrieval-augmented мультимодальный модель, и retrieve-, и generate-ящий текст И изображения. | Google Research |
| **ColPali** | Vision-language retriever: late-interaction (ColBERT) поверх патчей изображения страницы (скриншоты). | 📄 arXiv 2407.01449 · 📦 широко принят |
| **ColQwen** | «Col»-семейство мультимодальный ретривер на базе Qwen-VL. | 📦 community |

### F. Memory / Long-context / Compression

| Тип | Core idea | Источник / зрелость |
|---|---|---|
| **MemoRAG** | Dual-system: лёгкая long-range-memory-модель строит глобальную память и эмитит «clues», ведущие к точному retrieval. | 🏆 ACL 2025 · arXiv 2409.05591 · 📦 github.com/qhjqhj00/MemoRAG |
| **xRAG** | Экстремальное сжатие контекста: пассажи компрессируются в пространство представлений модели (не текстовые токены). | 🏆 NeurIPS 2024 · arXiv 2405.13792 |
| **EdgeRAG** | RAG на memory-constrained edge: прунинг cluster-эмбеддингов, on-demand генерация эмбеддингов при retrieval. | 🏆 MLSys 2025 · arXiv 2412.21023 |
| **ChatQA / ChatQA 2** | NVIDIA-семейство fine-tuned для conversational QA + RAG; v2 добавляет long-context handling. | 🏆 ACL 2024 · arXiv 2401.10225 · 🏭 HF-модели |
| **Long-Context-vs-RAG** | Не архитектура, а сравнение long-context LLM vs RAG; U-NIAH унифицирует оценку. | 💡 survey/benchmark · arXiv 2501.01880 |

### G. Pre-retrieval / Query transformation (техники-примитивы)

| Тип | Core idea | Источник / зрелость |
|---|---|---|
| **HyDE** | LLM генерирует гипотетический ответ, по нему эмбеддится и ищется — мостит question→answer семантический разрыв. | 📄 arXiv 2212.10496 |
| **RAG-Fusion** | Генерация нескольких query-вариантов + слияние их списков через RRF. | 💡 blog-origin · 📦 широко принят |
| **Step-Back Prompting** | LLM сначала задаёт более абстрактный/родительский вопрос, retrieve по нему, затем отвечает на конкретный. | 📄 Google DeepMind 2023 |
| **Multi-Query Retrieval** | N переформулировок запроса, retrieve по каждой, union результатов. | 💡 LangChain primitive |

### H. Chunking / Structure / Late-interaction (техники-примитивы)

| Тип | Core idea | Источник / зрелость |
|---|---|---|
| **Vectorless RAG / PageIndex** | Никаких эмбеддингов: LLM строит TOC-дерево и навигирует по нему логически; прямой выгруз страниц. | 📦 github.com/VectifyAI/PageIndex |
| **RAPTOR** | Рекурсивная кластеризация + суммаризация чанков в многоуровневое дерево (retrieval на разных гранулярностях). | 🏆 ICLR 2024 · arXiv 2401.18059 |
| **ColBERT** | Per-token эмбеддинги + MaxSim late-interaction (вместо одного вектора на документ). | 🏆 SIGIR 2020 · 📦 широко |
| **Contextual Retrieval** | LLM-генерируемый контекст-prepend к каждому чанку перед эмбеддингом (−35…67% retrieval-fail rate). | 💡 Anthropic 2024 |
| **Late Chunking** | Сначала эмбеддится весь документ long-context-эмбеддером, потом нарезается — сохраняя кросс-чанк контекст. | 📄 arXiv 2409.19773 (Jina AI) |
| **Dense X Retrieval** | «Propositions» (атомарные самодостаточные факты) как единица retrieval вместо пассажей. | 📄 arXiv 2312.06648 |

### I. Frameworks / Tooling (НЕ архитектуры — вынесены отдельно)

| Название | Что это на самом деле | Зрелость |
|---|---|---|
| **DSPy** | Программный фреймворк (Stanford) компиляции/оптимизации LLM-пайплайнов, включая retrieval-модули. | 📦 framework |
| **FlexRAG** | Фреймворк быстрого воспроизведения/разработки/оценки RAG (модульный config). | 🏆 ACL 2025 Demo · arXiv 2506.12494 · 📦 |
| **RAGFlow** | Open-source RAG-engine / document-processing. | 🏭 product |
| **nano-graphrag** | Лёгкая реимплементация GraphRAG (см. семейство B). | 📦 |
| **M²RAG** | Бенчмарк оценки мультимодальных RAG (не архитектура). | benchmark |

### J. Domain-specific

| Тип | Core idea | Источник / зрелость |
|---|---|---|
| **BiomedRAG** | Chunk-retrieval фреймворк под биомед-NLP (domain adaptation). | 🏆 J. Biomedical Informatics |
| **TOBUGraph** | Graph-based персонализация для conversational AI. | 📄 arXiv 2412.05447 |

### K. Security (не архитектуры генерации — вынесены отдельно)

| Тип | Что это | Источник |
|---|---|---|
| **PoisonedRAG** | Атака corruption-of-knowledge: инъекция вредоносных текстов в БД RAG (до 90% success). | 📄 arXiv 2402.07867 |
| **Poison-RAG** | Семейство практических poisoning-атак. | 📄 arXiv 2501.11759 |

---

## Матрица зрелости

| Зрелость | Типы |
|---|---|
| 🏭 **product / production** | Microsoft GraphRAG, Standard HybridRAG, ColPali (в проде), ChatQA (HF-модели), RAGFlow, LightRAG (deployed) |
| 📦 **open-source библиотека + сообщество** | LightRAG, nano-graphrag, KAG, MemoRAG, ColBERT, RAGEN, DSPy, FlexRAG, PageIndex, CRAG (LangGraph) |
| 🏆 **peer-reviewed (топ-конференция)** | Self-RAG, FLARE, REPLUG, Speculative RAG, Adaptive RAG, HippoRAG, ToG, GNN-RAG, RA-DIT, SAIL, RAPTOR, MuRAG, xRAG, EdgeRAG, ChatQA, SimRAG, OG-RAG, PathRAG/ArchRAG/TagRAG (AAAI/ACL), MAPPO-RAG, IRCoT, ReAct, PGraphRAG |
| 📄 **arXiv / статья только** | CRAG, RA-ISF, S-Path-RAG, MemGraphRAG, G-RAG, SURGE, HyDE, Late Chunking, Dense X, GraphReader, MA-RAG, Auto-RAG, RAFT, AGRAG |
| 💡 **концепция / blog** | Agentic RAG (парадигма), Modular RAG (парадигма), Federated RAG (парадигма), Multimodal RAG (парадигма), RAG-Fusion, Multi-Query, Contextual Retrieval, Step-Back, Long-Context-vs-RAG |

> **Вывод по зрелости:** зрелые production/open-source реализации есть у
> ~15 типов (главным образом HybridRAG, GraphRAG/LightRAG, HippoRAG, RAPTOR,
> ColBERT/ColPali, Self-RAG, CRAG). Остальные ~35 — либо академические статьи
> без reference-имплементации, либо концепции. Это означает: **платформа не
> может «подключить» большинство типов как готовые сервисы** — она должна
> уметь **собирать их из примитивов** (см. [[rag-constructor]]).

---

## Ось «общее ↔ конкретное»

Один и тот же термин «тип RAG» применяется к объектам разного уровня общности.
Это критично для конструктора: **парадигмы** задают оси, **архитектуры** —
конкретные значения по осям, **техники** — значения по одной оси.

### Парадигмы (задают оси конструктора — самые общие)
- **Modular RAG** — мета-рамка: RAG = композиция модулей. Под неё подпадают почти все остальные.
- **Agentic RAG** — ось «traversal»: агент сам решает, сколько раз и как искать.
- **Adaptive RAG** — ось «routing»: выученный выбор стратегии под запрос.
- **Federated RAG** — ось «retrieval store»: несколько независимых источников.
- **Self-Reflective RAG** — ось «reflection»: самооценка и коррекция.
- **Hybrid RAG** — ось «retrieval store»: sparse+dense; ось «rerank»: reranker.
- **Graph RAG** — ось «retrieval store»: граф знаний.
- **Multimodal RAG** — ось «retrieval store» + «generation»: несколько модальностей.
- **Vectorless RAG** — ось «retrieval store»: TOC-дерево вместо векторов.

### Конкретные архитектуры (инстанциации парадигм — значения по осям)
Self-RAG, CRAG, FLARE, Speculative RAG, REPLUG, HippoRAG, PathRAG, ArchRAG,
LightRAG, MSFT GraphRAG, TagRAG, S-Path-RAG, MemGraphRAG, OG-RAG, ToG, GNN-RAG,
RAPTOR, MemoRAG, xRAG, EdgeRAG, MuRAG, RA-CM3, IRCoT, ReAct, RA-DIT, RAFT,
SAIL, SimRAG, ChatQA, MA-RAG, MAPPO-RAG.

### Техники / примитивы (значения по одной оси — композируемые блоки)
- **Pre-retrieval**: HyDE, RAG-Fusion, step-back, multi-query.
- **Retrieval store**: BM25 (sparse), dense-vector, ColBERT late-interaction.
- **Chunking/indexing**: late-chunking, contextual retrieval, dense-X propositions, RAPTOR tree, community-summaries.
- **Rerank**: cross-encoder, G-RAG (GNN), OG-RAG (set-cover), PathRAG (path-prune).

### Фреймворки / тулинг (НЕ архитектуры — инструмент реализации)
DSPy, FlexRAG, nano-graphrag, RAGFlow.

---

## Типы, которые НЕ подтвердились как самостоятельные архитектуры

При исследовании ряда названий из популярных списков они **не всплыли** как
самостоятельные peer-reviewed системы. Фиксируем, чтобы не плодить фантомы:

| Название | Реальный статус / во что маппится |
|---|---|
| **Self-Propagating / Self-Proagagating RAG** | Не существует как RAG-архитектура. Термин встречается только в исследованиях AI-worm / prompt-injection (security). |
| **Self-RAGged / Self-RAGging** | Неформальный community-сленг, канонической системы нет. Ближайший — Self-RAG. |
| **ARISE** | Не всплыл как отдельный paper. Ближайший по смыслу — RA-ISF (Retrieval Augmented Iterative Self-Feedback). |
| **tox-RAG** | Не архитектура. Маппится в PoisonedRAG-литературу (атаки на RAG). |
| **KNN-RAG** | Встречается только как именованный baseline внутри embodied-AI работ (DéjàVu и др.), не как отдельная архитектура. |
| **SANTA** | Не найдено отчётливого distinct RAG-paper под этим именем. |
| **IRAX / OpenRAG / Hyrax / SeRTS / RAGAT** | Не подтвердились как distinct peer-reviewed RAG-архитектуры — скорее внутренние/нишевые имена или искажения. |
| **GraphChain / RaD** | Канонического paper нет; «RaD» неоднозначно (возможно retrieval-augmented diffusion). |

> Принцип реестра: тип попадает в основную таблицу, только если у него есть
> формальная публикация (arXiv/конференция) ИЛИ активная open-source
> реализация ИЛИ устоявшееся продуктовое воплощение. Концепты-фантомы сюда
> **не** добавляются.

---

## Связь с другими документами

- **Как из типов собрать конструктор** — [[rag-constructor]]: каждый тип
  декомпозируется в значения по 7 осям; матрица «тип → координаты».
- **Как подключить каждый тип к платформе и дебажить** —
  [[rag-platform-evolution]] блок A: маппинг всех типов на Tier 1/2/3/in-process.
- **Исполняемые стадии реализации** — `specs/stages/STAGE-1..5-*.md`.
