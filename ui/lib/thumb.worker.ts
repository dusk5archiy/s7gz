/// <reference lib="webworker" />

import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { enuPoseToThreeQuaternion, enuToThreePosition } from "@/lib/three-math";
import type { GeoPose, WorldSceneModel, WorldSceneVisual } from "@/lib/types";

type WorkerRequest =
  | {
      id: number;
      kind: "model";
      origin: string;
      width: number;
      height: number;
      visuals: WorldSceneVisual[];
    }
  | {
      id: number;
      kind: "world";
      origin: string;
      width: number;
      height: number;
      models: WorldSceneModel[];
    };

type WorkerResponse =
  | { id: number; blob: Blob }
  | { id: number; empty: true }
  | { id: number; error: string };

interface BakedPart {
  geometry: THREE.BufferGeometry;
  localMatrix: THREE.Matrix4;
  colorHex: number | null;
}

const ctx = self as unknown as DedicatedWorkerGlobalScope;

const NO_TEX_MANAGER = new THREE.LoadingManager();
NO_TEX_MANAGER.setURLModifier((url: string) => {
  if (/\.(png|jpe?g|webp|tga|bmp|gif)(\?.*)?$/i.test(url)) {
    return "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
  }
  return url;
});

// Short-lived burst-scoped geometry cache: reuses parsed geometry across cards
// rendered in the same burst (e.g. 11 x500 variants sharing NXP-HGD-CF.dae),
// then automatically disposes everything after 3.5s idle so GPU memory returns to 0.
const BURST_CACHE_MAX = 20;
const BURST_IDLE_MS = 3500;
const burstCache = new Map<string, BakedPart[]>();
const burstInflight = new Map<string, Promise<BakedPart[] | null>>();
let idlePurgeTimer: ReturnType<typeof setTimeout> | null = null;

function disposeBakedParts(parts: BakedPart[]): void {
  const seen = new Set<THREE.BufferGeometry>();
  for (const part of parts) {
    if (!seen.has(part.geometry)) {
      seen.add(part.geometry);
      part.geometry.dispose();
    }
  }
}

function purgeBurstCache(): void {
  idlePurgeTimer = null;
  for (const parts of burstCache.values()) {
    disposeBakedParts(parts);
  }
  burstCache.clear();
}

function scheduleIdlePurge(): void {
  if (idlePurgeTimer !== null) clearTimeout(idlePurgeTimer);
  idlePurgeTimer = setTimeout(purgeBurstCache, BURST_IDLE_MS);
}

function cachePut(key: string, parts: BakedPart[]): void {
  if (burstCache.has(key)) {
    burstCache.delete(key);
  } else if (burstCache.size >= BURST_CACHE_MAX) {
    const oldestKey = burstCache.keys().next().value;
    if (oldestKey !== undefined) {
      const oldest = burstCache.get(oldestKey);
      burstCache.delete(oldestKey);
      if (oldest) disposeBakedParts(oldest);
    }
  }
  burstCache.set(key, parts);
}

let renderer: THREE.WebGLRenderer | null = null;
let canvas: OffscreenCanvas | null = null;
let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;

function getRig(width: number, height: number, isWorld: boolean) {
  if (!canvas || !renderer || !scene || !camera) {
    canvas = new OffscreenCanvas(width, height);
    renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: false,
      alpha: false,
      powerPreference: "low-power",
    });
    renderer.setPixelRatio(1);
    renderer.setSize(width, height, false);
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1.15;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b1017);
    scene.add(
      new THREE.AmbientLight(0xffffff, 0.72),
      new THREE.HemisphereLight(0xf1f5f9, 0x334155, 0.65),
    );
    const dir = new THREE.DirectionalLight(0xfffbeb, 0.9);
    dir.position.set(45, 80, 35);
    scene.add(dir);

    camera = new THREE.PerspectiveCamera(50, width / height, 0.05, 2000);
  } else if (canvas.width !== width || canvas.height !== height) {
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
  }

  camera.fov = isWorld ? 50 : 45;
  camera.near = isWorld ? 0.5 : 0.05;
  camera.far = isWorld ? 2000 : 800;
  camera.updateProjectionMatrix();

  return { renderer, canvas, scene, camera };
}

function buildGeometryUrl(assetUrl: string, ext: string, origin: string): string {
  const full = new URL(assetUrl, origin);
  full.searchParams.set("geometry_only", "1");
  if (ext === ".dae") {
    full.searchParams.set("as_glb", "1");
    full.searchParams.set("gv", "2");
  }
  return full.href;
}

function poseToMatrix(pose: GeoPose): THREE.Matrix4 {
  const pos = enuToThreePosition(pose.east_m, pose.north_m, pose.up_m);
  const quat = enuPoseToThreeQuaternion(pose);
  return new THREE.Matrix4().compose(pos, quat, new THREE.Vector3(1, 1, 1));
}

function extractMaterialColorHex(mat: THREE.Material | null | undefined): number | null {
  if (mat && "color" in mat && mat.color instanceof THREE.Color) {
    return mat.color.getHex();
  }
  return null;
}

function disposeMaterialDeep(mat: THREE.Material | null | undefined): void {
  if (!mat) return;
  const rec = mat as unknown as Record<string, unknown>;
  for (const k of Object.keys(rec)) {
    if (rec[k] instanceof THREE.Texture) {
      (rec[k] as THREE.Texture).dispose();
    }
  }
  mat.dispose();
}

function bakeObjectParts(root: THREE.Object3D): BakedPart[] {
  const parts: BakedPart[] = [];
  root.updateMatrixWorld(true);
  root.traverse((obj) => {
    if (!(obj instanceof THREE.Mesh) || !obj.geometry) return;
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    const colorHex = extractMaterialColorHex(mats[0]);
    for (const m of mats) disposeMaterialDeep(m);
    const geom = obj.geometry;
    if (!geom.attributes.normal) geom.computeVertexNormals();
    if (!geom.boundingBox) geom.computeBoundingBox();
    parts.push({
      geometry: geom,
      localMatrix: obj.matrixWorld.clone(),
      colorHex,
    });
  });
  return parts;
}

async function loadMeshPartsUncached(
  assetUrl: string,
  ext: string,
  origin: string,
): Promise<BakedPart[] | null> {
  const url = buildGeometryUrl(assetUrl, ext, origin);
  try {
    if (ext === ".glb" || ext === ".gltf" || ext === ".dae") {
      const res = await new GLTFLoader(NO_TEX_MANAGER).loadAsync(url);
      if (!res?.scene) return null;
      const remove: THREE.Object3D[] = [];
      res.scene.traverse((c) => {
        if (c instanceof THREE.Light || c instanceof THREE.Camera) remove.push(c);
      });
      for (const n of remove) n.removeFromParent();
      res.scene.rotation.set(-Math.PI / 2, 0, 0);
      return bakeObjectParts(res.scene);
    }
    if (ext === ".stl") {
      const geom = await new STLLoader().loadAsync(url);
      if (!geom.attributes.normal) geom.computeVertexNormals();
      if (!geom.boundingBox) geom.computeBoundingBox();
      const rot = new THREE.Matrix4().makeRotationX(-Math.PI / 2);
      return [{ geometry: geom, localMatrix: rot, colorHex: null }];
    }
    if (ext === ".obj") {
      const obj = await new OBJLoader(NO_TEX_MANAGER).loadAsync(url);
      obj.rotation.x = -Math.PI / 2;
      return bakeObjectParts(obj);
    }
  } catch {
    return null;
  }
  return null;
}

function loadMeshParts(
  assetUrl: string,
  ext: string,
  origin: string,
): Promise<BakedPart[] | null> {
  const cached = burstCache.get(assetUrl);
  if (cached) {
    // Refresh LRU order
    burstCache.delete(assetUrl);
    burstCache.set(assetUrl, cached);
    return Promise.resolve(cached);
  }
  const inflight = burstInflight.get(assetUrl);
  if (inflight) return inflight;

  const p = loadMeshPartsUncached(assetUrl, ext, origin)
    .then((parts) => {
      if (parts && parts.length > 0) {
        cachePut(assetUrl, parts);
      }
      return parts;
    })
    .finally(() => {
      burstInflight.delete(assetUrl);
    });
  burstInflight.set(assetUrl, p);
  return p;
}

function buildPrimitiveGeometry(vis: WorldSceneVisual): THREE.BufferGeometry | null {
  const g = vis.geometry;
  if (g.type === "box" && g.size) {
    return new THREE.BoxGeometry(g.size[0], g.size[2], g.size[1]);
  }
  if (g.type === "cylinder" && g.radius && g.length) {
    return new THREE.CylinderGeometry(g.radius, g.radius, g.length, 12);
  }
  if (g.type === "sphere" && g.radius) {
    return new THREE.SphereGeometry(g.radius, 12, 8);
  }
  return null;
}

function visualLocalMatrix(vis: WorldSceneVisual): THREE.Matrix4 {
  const m = poseToMatrix(vis.link_pose).multiply(poseToMatrix(vis.visual_pose));
  const sc = vis.geometry.scale;
  if (sc && sc.length === 3) {
    // Baked mesh parts are already rotated from Gazebo Z-up to Three.js Y-up,
    // so Gazebo (sx, sy, sz) scales Three.js (sx, sz, sy).
    m.multiply(new THREE.Matrix4().makeScale(sc[0], sc[2], sc[1]));
  }
  return m;
}

async function renderSceneItems(
  items: Array<{
    modelMatrix: THREE.Matrix4;
    fallbackHex: number;
    visuals: WorldSceneVisual[];
    isGround?: boolean;
  }>,
  width: number,
  height: number,
  isWorld: boolean,
  origin: string,
): Promise<Blob | null> {
  // Collect unique mesh URLs and load them once (in parallel, bounded).
  const uniqueMeshSpecs = new Map<string, { assetUrl: string; ext: string }>();
  for (const item of items) {
    for (const vis of item.visuals) {
      const g = vis.geometry;
      if (g.type === "mesh" && g.asset_url && g.ext && !uniqueMeshSpecs.has(g.asset_url)) {
        uniqueMeshSpecs.set(g.asset_url, { assetUrl: g.asset_url, ext: g.ext.toLowerCase() });
      }
    }
  }

  const loadedTemplates = new Map<string, BakedPart[]>();
  const meshEntries = Array.from(uniqueMeshSpecs.values());
  const loadConcurrency = Math.min(4, Math.max(1, meshEntries.length));
  let loadCursor = 0;

  await Promise.all(
    Array.from({ length: loadConcurrency }, async () => {
      while (loadCursor < meshEntries.length) {
        const spec = meshEntries[loadCursor++];
        const parts = await loadMeshParts(spec.assetUrl, spec.ext, origin);
        if (parts && parts.length > 0) {
          loadedTemplates.set(spec.assetUrl, parts);
        }
      }
    }),
  );

  // Group placements per (assetUrl, fallbackHex) so repeated parts render via InstancedMesh.
  const instanceGroups = new Map<
    string,
    { assetUrl: string; fallbackHex: number; placements: Array<{ mat: THREE.Matrix4; isGround: boolean }> }
  >();
  const primitiveMeshes: Array<{ mesh: THREE.Mesh; isGround: boolean }> = [];
  const ownedPrimitiveGeometries: THREE.BufferGeometry[] = [];
  const ownedMaterials: THREE.Material[] = [];

  for (const item of items) {
    for (const vis of item.visuals) {
      const g = vis.geometry;
      const rgb = vis.diffuse_rgba;
      const visFallbackHex =
        rgb && rgb.length >= 3
          ? new THREE.Color(rgb[0], rgb[1], rgb[2]).getHex()
          : item.fallbackHex;
      if (g.type === "mesh" && g.asset_url) {
        if (!loadedTemplates.has(g.asset_url)) continue;
        const placement = item.modelMatrix.clone().multiply(visualLocalMatrix(vis));
        const key = `${g.asset_url}::${visFallbackHex}`;
        let grp = instanceGroups.get(key);
        if (!grp) {
          grp = { assetUrl: g.asset_url, fallbackHex: visFallbackHex, placements: [] };
          instanceGroups.set(key, grp);
        }
        grp.placements.push({ mat: placement, isGround: Boolean(item.isGround) });
      } else {
        const geom = buildPrimitiveGeometry(vis);
        if (!geom) continue;
        if (!geom.boundingBox) geom.computeBoundingBox();
        ownedPrimitiveGeometries.push(geom);
        const mat = new THREE.MeshLambertMaterial({ color: visFallbackHex });
        ownedMaterials.push(mat);
        const mesh = new THREE.Mesh(geom, mat);
        const m = item.modelMatrix
          .clone()
          .multiply(poseToMatrix(vis.link_pose))
          .multiply(poseToMatrix(vis.visual_pose));
        mesh.matrixAutoUpdate = false;
        mesh.matrix.copy(m);
        primitiveMeshes.push({ mesh, isGround: Boolean(item.isGround) });
      }
    }
  }

  const root = new THREE.Group();
  const worldBox = new THREE.Box3();
  const focusBox = new THREE.Box3();
  const tmpBox = new THREE.Box3();
  const tmpMat = new THREE.Matrix4();

  for (const grp of instanceGroups.values()) {
    const parts = loadedTemplates.get(grp.assetUrl);
    if (!parts) continue;
    const count = grp.placements.length;
    for (const part of parts) {
      const mat = new THREE.MeshLambertMaterial({
        color: part.colorHex ?? grp.fallbackHex,
      });
      ownedMaterials.push(mat);

      if (count === 1) {
        const mesh = new THREE.Mesh(part.geometry, mat);
        tmpMat.multiplyMatrices(grp.placements[0].mat, part.localMatrix);
        mesh.matrixAutoUpdate = false;
        mesh.matrix.copy(tmpMat);
        root.add(mesh);
        if (part.geometry.boundingBox) {
          tmpBox.copy(part.geometry.boundingBox).applyMatrix4(tmpMat);
          worldBox.union(tmpBox);
          if (!grp.placements[0].isGround) focusBox.union(tmpBox);
        }
      } else {
        const inst = new THREE.InstancedMesh(part.geometry, mat, count);
        inst.frustumCulled = false;
        for (let i = 0; i < count; i++) {
          tmpMat.multiplyMatrices(grp.placements[i].mat, part.localMatrix);
          inst.setMatrixAt(i, tmpMat);
          if (part.geometry.boundingBox) {
            tmpBox.copy(part.geometry.boundingBox).applyMatrix4(tmpMat);
            worldBox.union(tmpBox);
            if (!grp.placements[i].isGround) focusBox.union(tmpBox);
          }
        }
        inst.instanceMatrix.needsUpdate = true;
        root.add(inst);
      }
    }
  }

  for (const { mesh: prim, isGround } of primitiveMeshes) {
    root.add(prim);
    if (prim.geometry.boundingBox) {
      tmpBox.copy(prim.geometry.boundingBox).applyMatrix4(prim.matrix);
      worldBox.union(tmpBox);
      if (!isGround) focusBox.union(tmpBox);
    }
  }

  try {
    if (root.children.length === 0 || worldBox.isEmpty()) {
      return null;
    }

    const rig = getRig(width, height, isWorld);
    rig.scene.add(root);

    const frameBox = focusBox.isEmpty() ? worldBox : focusBox;
    const center = frameBox.getCenter(new THREE.Vector3());
    const size = frameBox.getSize(new THREE.Vector3());
    const dist = isWorld
      ? Math.min(Math.max(size.length() * 0.65, 2.5), 280)
      : Math.min(Math.max(size.length() * 0.5, 0.25) * 2.25, 250);

    if (isWorld) {
      rig.camera.position.set(
        center.x - dist * 0.65,
        center.y + dist * 0.55,
        center.z + dist * 0.65,
      );
    } else {
      rig.camera.position.set(
        center.x - dist * 0.72,
        center.y + dist * 0.52,
        center.z + dist * 0.72,
      );
    }
    rig.camera.lookAt(center);
    rig.camera.updateProjectionMatrix();

    rig.renderer.render(rig.scene, rig.camera);
    rig.scene.remove(root);
    rig.renderer.renderLists.dispose();

    const blob = await rig.canvas
      .convertToBlob({ type: "image/webp", quality: 0.82 })
      .catch(() => rig.canvas.convertToBlob({ type: "image/jpeg", quality: 0.85 }));
    return blob;
  } finally {
    for (const g of ownedPrimitiveGeometries) g.dispose();
    for (const m of ownedMaterials) m.dispose();
  }
}

ctx.onmessage = async (ev: MessageEvent<WorkerRequest>) => {
  if (idlePurgeTimer !== null) {
    clearTimeout(idlePurgeTimer);
    idlePurgeTimer = null;
  }
  const req = ev.data;
  try {
    let blob: Blob | null = null;
    if (req.kind === "model") {
      blob = await renderSceneItems(
        [
          {
            modelMatrix: new THREE.Matrix4(),
            fallbackHex: 0x64748b,
            visuals: req.visuals,
          },
        ],
        req.width,
        req.height,
        false,
        req.origin,
      );
    } else {
      const items = req.models
        .filter((m) => m.visuals.length > 0)
        .map((m) => ({
          modelMatrix: poseToMatrix(m.pose),
          fallbackHex: m.is_base_station ? 0xf59e0b : 0x64748b,
          visuals: m.visuals,
          isGround: m.name === "ground_plane",
        }));
      blob = await renderSceneItems(items, req.width, req.height, true, req.origin);
    }
    const resp: WorkerResponse = blob ? { id: req.id, blob } : { id: req.id, empty: true };
    ctx.postMessage(resp);
  } catch (err) {
    const resp: WorkerResponse = {
      id: req.id,
      error: err instanceof Error ? err.message : String(err),
    };
    ctx.postMessage(resp);
  } finally {
    scheduleIdlePurge();
  }
};
