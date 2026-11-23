export interface DataclassFieldSchema {
  name: string;
  description?: string;
  default?: unknown;
  schema: SettingsFieldSchema;
}

export interface SettingsFieldSchema {
  type: string;
  nullable?: boolean;
  choices?: unknown[];
  min?: number;
  max?: number;
  gt?: number;
  lt?: number;
  items?: SettingsFieldSchema | SettingsFieldSchema[];
  key?: SettingsFieldSchema;
  value?: SettingsFieldSchema;
  name?: string;
  description?: string;
  fields?: DataclassFieldSchema[];
  variants?: SettingsFieldSchema[];
}

export interface SettingsField {
  name: string;
  env_key: string;
  has_default?: boolean;
  is_ui_overridden?: boolean;
  description?: string;
  schema: SettingsFieldSchema;
  default: unknown;
  base_value?: unknown;
  value: unknown;
}

export interface SettingsComputedProperty {
  name: string;
  value: unknown;
  description?: string;
}

export interface SettingsGroup {
  group: string;
  prefix: string;
  description?: string;
  fields: SettingsField[];
  properties?: SettingsComputedProperty[];
}

export interface SettingsResponse {
  groups: SettingsGroup[];
}

export interface SettingsUpdateResponse {
  saved: Record<string, unknown>;
  groups: SettingsGroup[];
}

export interface CatalogAssetRef {
  kind: "catalog";
  relative_path: string;
}

export interface PathAssetRef {
  kind: "path";
  path: string;
}

export type AssetRef = CatalogAssetRef | PathAssetRef;

export type WorldScope = "source" | "patched";

export interface WorldFileItem {
  provider: string;
  relative_path: string;
  display_path: string;
  world_key?: string;
  world_path?: string;
  name: string;
  has_3d?: boolean;
  thumbnail_url?: string | null;
  is_patched?: boolean;
  fleet_vehicle_count?: number;
  size_bytes: number;
  modified_at: string;
}

export interface WorldProviderGroup {
  key: string;
  label: string;
  supports_download: boolean;
  supports_sync: boolean;
  can_delete_source: boolean;
  source_dir: string;
  source_rel_dir: string;
  patched_dir: string;
  patched_rel_dir: string;
  source_worlds: WorldFileItem[];
  patched_worlds: WorldFileItem[];
}

export interface WorldsListResponse {
  source_dir: string;
  source_rel_dir: string;
  patched_dir: string;
  patched_rel_dir: string;
  active: {
    world_name: string | null;
    world_url: string | null;
    active_world?: AssetRef | null;
    active_world_key?: string | null;
    world_file?: string | null;
  };
  providers: Record<string, WorldProviderGroup>;
}

export interface WorldReadResponse {
  scope: WorldScope;
  relative_path: string;
  size_bytes: number;
  world_name: string | null;
  content: string;
}

export interface GeoPose {
  east_m: number;
  north_m: number;
  up_m: number;
  roll_deg: number;
  pitch_deg: number;
  yaw_deg: number;
}

export interface BodyPose {
  forward_m: number;
  left_m: number;
  up_m: number;
  roll_rad: number;
  pitch_rad: number;
  yaw_rad: number;
}

export type ScalarParamTuple = [string, string | number | boolean];

export interface AttachmentSpec {
  slot: string;
  kind: string;
  pose_offset: BodyPose | null;
  params: ScalarParamTuple[];
}

export interface DeviceSpec {
  name: string;
  kind: string;
  pose_offset: BodyPose | null;
  params: ScalarParamTuple[];
}

export interface VehicleSpec {
  namespace: string;
  airframe: AssetRef | null;
  attachments: AttachmentSpec[];
  devices: DeviceSpec[];
}

export interface FleetVehicle {
  namespace: string;
  airframe: AssetRef | null;
  attachments: AttachmentSpec[];
  devices: DeviceSpec[];
}

export interface AttachmentCatalogItem {
  kind: string;
  default_slot: string;
  default_pose: BodyPose;
  default_params: Record<string, unknown>;
  params_schema: DataclassFieldSchema[];
}

export interface DeviceCatalogItem {
  kind: string;
  default_name: string;
  default_pose: BodyPose;
  default_params: Record<string, unknown>;
  params_schema: DataclassFieldSchema[];
}

export interface VehiclePreset {
  id: string;
  label: string;
  description: string;
  vehicle: VehicleSpec;
}

export interface VehicleCatalogResponse {
  airframes: string[];
  attachments: AttachmentCatalogItem[];
  devices: DeviceCatalogItem[];
  presets: VehiclePreset[];
}

export type FormationConfig =
  | {
      kind: "line_abreast";
      spacing_m: number;
      min_separation_m: number;
    }
  | {
      kind: "ring";
      radius_m: number;
      min_separation_m: number;
    };

export type CenterConfig =
  | {
      kind: "base_station";
      base_station_half_m: number;
      gap_m: number;
      front_east: number;
      front_north: number;
      offset_up_m: number;
    }
  | {
      kind: "absolute";
      pose: GeoPose;
    };

export interface WorldFleetConfig {
  enabled: boolean;
  formation: FormationConfig;
  center: CenterConfig;
  pose_overrides: Record<string, GeoPose>;
  vehicles: VehicleSpec[];
}

export interface FleetMember {
  index: number;
  vehicle: FleetVehicle;
  pose: GeoPose;
  gz_model_name?: string;
}

export interface FleetPreviewResponse {
  world_ref: AssetRef | null;
  active_world_ref: AssetRef | null;
  world_key: string | null;
  active_world_key: string | null;
  has_saved_fleet: boolean;
  fleet_config: WorldFleetConfig;
  default_fleet_config: WorldFleetConfig;
  members: FleetMember[];
  base_station: GeoPose | null;
  effective_center: GeoPose;
  source_world: string | null;
}

export interface WorldSceneGeometry {
  type: "mesh" | "box" | "cylinder" | "sphere";
  asset_url?: string;
  ext?: string;
  scale?: number[];
  size?: number[];
  radius?: number;
  length?: number;
}

export interface WorldSceneVisual {
  link_pose: GeoPose;
  visual_pose: GeoPose;
  geometry: WorldSceneGeometry;
  albedo_url?: string | null;
  diffuse_rgba?: number[] | null;
}

export interface WorldSceneModel {
  name: string;
  is_base_station: boolean;
  pose: GeoPose;
  visuals: WorldSceneVisual[];
}

export interface WorldSceneResponse {
  source_world: string | null;
  base_station: GeoPose | null;
  thumbnail_url?: string | null;
  models: WorldSceneModel[];
  drone_visuals?: WorldSceneVisual[];
}

export interface VehicleModelItem {
  relative_path: string;
  world_scope: string;
  world_key: string;
  name: string;
  has_sdf: boolean;
  has_3d?: boolean;
  has_config: boolean;
  missing_files?: string[];
  size_bytes: number;
  modified_at: string;
  is_patched?: boolean;
}

export interface WorldGeneratedModelsGroup {
  world_scope: string;
  world_key: string;
  dir_rel: string;
  models: VehicleModelItem[];
}

export interface VehicleModelsListResponse {
  generated_models_dir: string;
  active_world_key?: string | null;
  worlds: WorldGeneratedModelsGroup[];
  generated_models: VehicleModelItem[];
}

export interface VehicleModelReadResponse {
  scope: "generated";
  relative_path?: string;
  name: string;
  size_bytes: number;
  content: string;
}

export type FuelModelScope = "source" | "patched";

export interface FuelModelItem {
  provider: string;
  scope?: FuelModelScope;
  relative_path: string;
  display_path: string;
  sdf_rel_path?: string | null;
  server?: string;
  owner?: string;
  name: string;
  version?: string;
  has_sdf: boolean;
  has_3d?: boolean;
  thumbnail_url?: string | null;
  has_config: boolean;
  is_patched?: boolean;
  missing_files?: string[];
  size_bytes: number;
  modified_at: string;
}

export interface ModelProviderGroup {
  key: string;
  label: string;
  model_layout: "fuel_tree" | "flat";
  supports_download: boolean;
  supports_sync: boolean;
  can_delete_source: boolean;
  source_dir: string;
  source_rel_dir: string;
  patched_dir: string;
  patched_rel_dir: string;
  patched_models: FuelModelItem[];
  source_models: FuelModelItem[];
}

export interface FuelModelsListResponse {
  source_dir: string;
  source_rel_dir: string;
  patched_dir: string;
  patched_rel_dir: string;
  providers: Record<string, ModelProviderGroup>;
}

export interface FuelModelReadResponse {
  scope: FuelModelScope;
  provider?: string;
  relative_path: string;
  name: string;
  size_bytes: number;
  content: string;
}
