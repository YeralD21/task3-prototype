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
