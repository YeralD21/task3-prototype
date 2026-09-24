export interface Language {
  name: string;
  iso_code: string | null;
}
export interface LanguageVariety {
  id: string;
  name: string;
  language_code: string | null;
  region: string | null;
  country: string | null;
  glottocode: string | null;
  metadata: Record<string, unknown> | null;
}
export interface LicenseInfo {
  name: string | null;
  url: string | null;
  commercial_use: boolean | null;
  redistribution: boolean | null;
  derivatives: boolean | null;
  attribution_required: boolean | null;
  notes: string | null;
}
export interface ProvenanceInfo {
  source_name: string | null;
  source_url: string | null;
  organization: string | null;
  original_dataset_id: string | null;
  citation: string | null;
  retrieved_at: string | null;
  notes: string | null;
}
export interface Dataset {
  id: string;
  name: string;
  description: string | null;
  languages: Language[] | null;
  language_varieties: LanguageVariety[] | null;
  countries: string[] | null;
  regions: string[] | null;
  modalities: string[] | null;
  tasks: string[] | null;
  domains: string[] | null;
  source_url: string | null;
  source_organization: string | null;
  license: LicenseInfo;
  provenance: ProvenanceInfo;
  citation: string | null;
  record_count: number | null;
  token_count: number | null;
  speaker_count: number | null;
  audio_hours: number | null;
  created_at: string | null;
  updated_at: string | null;
  metadata: Record<string, unknown> | null;
}
export interface Filters {
  language: string;
  modality: string;
  task: string;
}

export interface CorpusRecord {
  id: string;
  dataset_id: string;
  source_record_id: string;
  provenance: ProvenanceInfo;
  language: Language | null;
  language_code: string | null;
  language_variety: LanguageVariety | null;
  text: string;
  translation: string | null;
  translation_language: Language | null;
  audio_id: string | null;
  metadata: Record<string, unknown> | null;
}

export interface CorpusRecordPage {
  items: CorpusRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface RecordFilters {
  q?: string;
  language?: string;
  limit: number;
  offset: number;
}

export interface SemanticSearchRequest {
  query: string;
  dataset_id: string;
  limit: number;
}

export interface SemanticSearchItem {
  record: CorpusRecord;
  score: number;
}

export interface SemanticSearchResponse {
  query: string;
  dataset_id: string;
  items: SemanticSearchItem[];
}

export type AtlasReducer = "pca" | "umap" | (string & {});

export interface AtlasPoint {
  record_id: string;
  dataset_id: string;
  source_record_id: string;
  x: number;
  y: number;
  record: CorpusRecord;
}

export interface AtlasSampling {
  applied: boolean;
  method: "none" | "sha256_record_id";
}

export interface AtlasResponse {
  dataset_id: string;
  reducer: AtlasReducer;
  created_at: string;
  source_embedding_model: string;
  source_embedding_dimension: number;
  parameters: Record<string, unknown>;
  diagnostics: Record<string, unknown>;
  total_records: number;
  returned_records: number;
  limit: number;
  sampling: AtlasSampling;
  items: AtlasPoint[];
}

export type PlaybookTaskId =
  | "machine_translation"
  | "automatic_speech_recognition"
  | "semantic_search"
  | "corpus_exploration"
  | "language_modeling"
  | "linguistic_research"
  | "educational_use";

export type PlaybookCompatibility = "compatible" | "potential" | "not_applicable" | "unknown";
export type LocalArtifactStatus = "available" | "stale" | "missing" | "unknown";

export interface PlaybookTaskAssessment {
  task: PlaybookTaskId;
  compatibility: PlaybookCompatibility;
  reasons: string[];
  limitations: string[];
  license_notes: string[];
  data_requirements: string[];
  next_steps: string[];
}

export interface PlaybookLicense {
  known: boolean;
  name: string | null;
  url: string | null;
  commercial_use: boolean | null;
  redistribution: boolean | null;
  derivatives: boolean | null;
  attribution_required: boolean | null;
  notes: string | null;
}

export interface PlaybookVariety {
  status: "specified" | "partial" | "unspecified";
  varieties: LanguageVariety[];
  note: string;
}

export interface PlaybookProvenance {
  source_organization: string | null;
  source_url: string | null;
  documentation_url: string | null;
  citation: string | null;
  provenance: ProvenanceInfo;
}

export interface PlaybookLocalStatus {
  available_locally: boolean | null;
  semantic_index: LocalArtifactStatus;
  atlas: LocalArtifactStatus;
}

export interface DatasetPlaybook {
  dataset_id: string;
  dataset_name: string;
  languages: Language[];
  variety: PlaybookVariety;
  license: PlaybookLicense;
  provenance: PlaybookProvenance;
  local: PlaybookLocalStatus;
  tasks: PlaybookTaskAssessment[];
  disclaimer: string;
}

export interface PlaybookDatasetMatch {
  dataset_id: string;
  dataset_name: string;
  compatibility: PlaybookCompatibility;
  reasons: string[];
  limitations: string[];
  available_locally: boolean | null;
  license_known: boolean;
}

export interface PlaybookDiscovery {
  task: PlaybookTaskId;
  data_requirements: string[];
  ordering: "dataset_id";
  compatible: PlaybookDatasetMatch[];
  potential: PlaybookDatasetMatch[];
  unknown: PlaybookDatasetMatch[];
  not_applicable_count: number;
  disclaimer: string;
}

export type RadioAudioStatus = "available" | "missing_file" | "unsupported_format" | "unavailable";

export interface RadioItem {
  record: CorpusRecord;
  has_audio: boolean;
  audio_status: RadioAudioStatus;
  audio_url: string | null;
  media_type: string | null;
}

export interface RadioPage {
  dataset_id: string;
  contains_audio: boolean;
  items: RadioItem[];
  total: number;
  limit: number;
  offset: number;
}
