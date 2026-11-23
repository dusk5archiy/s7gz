"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { TransformControls } from "three/examples/jsm/controls/TransformControls.js";
import { ColladaLoader } from "three/examples/jsm/loaders/ColladaLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import {
  applyEnuPoseToObject,
  enuToThreePosition,
  threeQuaternionToEnuYawDeg,
  threeToEnuPosition,
} from "@/lib/three-math";
import { withGeometryOnlyParam } from "@/lib/thumb-worker-pool";
import { assetRefToKey } from "@/lib/asset-ref";
import type { FleetMember, GeoPose, WorldSceneResponse, WorldSceneVisual } from "@/lib/types";

interface WorldViewport3DProps {
  sceneData: WorldSceneResponse | null;
  members: FleetMember[];
  baseStation: GeoPose | null;
  effectiveCenter: GeoPose | null;
  fitMode?: "world" | "object";
  selectedTarget?: "anchor" | string | null;
  onSelectTarget?: (target: "anchor" | string | null) => void;
  onCenterChange?: (nextPose: GeoPose) => void;
  onMemberPoseChange?: (namespace: string, nextPose: GeoPose) => void;
  className?: string;
}

type EditTool = "select" | "pick_floor";
type GizmoMode = "translate" | "rotate";

const DAE_CACHE = new Map<string, Promise<THREE.Object3D | null>>();
const GLTF_CACHE = new Map<string, Promise<THREE.Object3D | null>>();
const STL_CACHE = new Map<string, Promise<THREE.BufferGeometry>>();
const OBJ_CACHE = new Map<string, Promise<THREE.Object3D>>();
const TEX_CACHE = new Map<string, Promise<THREE.Texture>>();
const SHARED_DAE_TEX_CACHE = new Map<string, THREE.Texture>();

let activeViewportCount = 0;
let viewerCachePurgeTimer: number | null = null;

function disposeTemplateDeep(root: THREE.Object3D): void {
  const seenGeoms = new Set<THREE.BufferGeometry>();
  const seenMats = new Set<THREE.Material>();
  root.traverse((node) => {
    if (!(node instanceof THREE.Mesh)) return;
    if (node.geometry && !seenGeoms.has(node.geometry)) {
      seenGeoms.add(node.geometry);
      node.geometry.dispose();
    }
    const mats = Array.isArray(node.material) ? node.material : [node.material];
    for (const mat of mats) {
      if (!mat || seenMats.has(mat)) continue;
      seenMats.add(mat);
      const rec = mat as unknown as Record<string, unknown>;
      for (const k of Object.keys(rec)) {
        if (rec[k] instanceof THREE.Texture) {
          (rec[k] as THREE.Texture).dispose();
        }
      }
      mat.dispose();
    }
  });
}

function purgeTexturedViewerCaches(): void {
  for (const [k, p] of Array.from(DAE_CACHE.entries())) {
    if (!k.endsWith("::tex")) continue;
    DAE_CACHE.delete(k);
    void p.then((obj) => {
      if (obj) disposeTemplateDeep(obj);
    });
  }
  for (const [k, p] of Array.from(GLTF_CACHE.entries())) {
    if (!k.endsWith("::tex")) continue;
    GLTF_CACHE.delete(k);
    void p.then((obj) => {
      if (obj) disposeTemplateDeep(obj);
    });
  }
  for (const [k, p] of Array.from(OBJ_CACHE.entries())) {
    if (!k.endsWith("::tex")) continue;
    OBJ_CACHE.delete(k);
    void p.then((obj) => {
      disposeTemplateDeep(obj);
    });
  }
  for (const p of TEX_CACHE.values()) {
    void p.then((tex) => tex.dispose()).catch(() => {});
  }
  TEX_CACHE.clear();
  for (const tex of SHARED_DAE_TEX_CACHE.values()) {
    tex.dispose();
  }
  SHARED_DAE_TEX_CACHE.clear();
}

function purgeAllViewerCaches(): void {
  viewerCachePurgeTimer = null;
  if (activeViewportCount > 0) return;
  for (const p of DAE_CACHE.values()) {
    void p.then((obj) => {
      if (obj) disposeTemplateDeep(obj);
    });
  }
  DAE_CACHE.clear();
  for (const p of GLTF_CACHE.values()) {
    void p.then((obj) => {
      if (obj) disposeTemplateDeep(obj);
    });
  }
  GLTF_CACHE.clear();
  for (const p of OBJ_CACHE.values()) {
    void p.then((obj) => disposeTemplateDeep(obj)).catch(() => {});
  }
  OBJ_CACHE.clear();
  for (const p of STL_CACHE.values()) {
    void p.then((geom) => geom.dispose()).catch(() => {});
  }
  STL_CACHE.clear();
  for (const p of TEX_CACHE.values()) {
    void p.then((tex) => tex.dispose()).catch(() => {});
  }
  TEX_CACHE.clear();
  for (const tex of SHARED_DAE_TEX_CACHE.values()) {
    tex.dispose();
  }
  SHARED_DAE_TEX_CACHE.clear();
}

const DISCARDED_DETAIL_MAPS = [
  "normalMap",
  "bumpMap",
  "roughnessMap",
  "metalnessMap",
  "aoMap",
  "specularMap",
  "displacementMap",
] as const;

const KEEP_SHARED_MAPS = ["map", "emissiveMap"] as const;

const SHARED_ASSET_MANAGER = new THREE.LoadingManager();
SHARED_ASSET_MANAGER.setURLModifier((rawUrl: string) => {
  const marker = "api/assets/";
  const firstIdx = rawUrl.indexOf(marker);
  const lastIdx = rawUrl.lastIndexOf(marker);
  const stripped =
    firstIdx >= 0 && lastIdx > firstIdx ? "/" + rawUrl.slice(lastIdx) : rawUrl;
  if (typeof window !== "undefined" && stripped.startsWith("/")) {
    try {
      const parsed = new URL(stripped, window.location.origin);
      return parsed.pathname + parsed.search;
    } catch {
      return stripped;
    }
  }
  return stripped;
});

const NO_TEX_ASSET_MANAGER = new THREE.LoadingManager();
NO_TEX_ASSET_MANAGER.setURLModifier((rawUrl: string) => {
  if (/\.(png|jpe?g|webp|tga|bmp|gif)(\?.*)?$/i.test(rawUrl)) {
    return "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
  }
  return rawUrl;
});

const ALL_TEXTURE_MAPS = [
  ...DISCARDED_DETAIL_MAPS,
  ...KEEP_SHARED_MAPS,
] as const;

function stripAllTextureMaps(root: THREE.Object3D): void {
  root.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return;
    const mats = Array.isArray(child.material) ? child.material : [child.material];
    for (const mat of mats) {
      if (!mat) continue;
      const rec = mat as unknown as Record<string, THREE.Texture | null | undefined>;
      let changed = false;
      for (const slot of ALL_TEXTURE_MAPS) {
        const tex = rec[slot];
        if (tex) {
          rec[slot] = null;
          tex.dispose();
          changed = true;
        }
      }
      if (mat instanceof THREE.MeshStandardMaterial && mat.metalness > 0.25) {
        mat.metalness = 0.25;
        mat.roughness = Math.max(mat.roughness, 0.55);
        changed = true;
      }
      if (changed) {
        mat.needsUpdate = true;
      }
    }
  });
}

function optimizeAndDedupeCollada(root: THREE.Object3D): void {
  root.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return;
    const mats = Array.isArray(child.material) ? child.material : [child.material];
    for (const mat of mats) {
      if (!mat) continue;
      const rec = mat as unknown as Record<string, THREE.Texture | null | undefined>;
      let strippedAny = false;
      let hadMetalnessMap = false;
      for (const slot of DISCARDED_DETAIL_MAPS) {
        const tex = rec[slot];
        if (tex) {
          if (slot === "metalnessMap") hadMetalnessMap = true;
          rec[slot] = null;
          tex.dispose();
          strippedAny = true;
        }
      }
      // Without an environment map, high metalness (e.g. glTF metallicFactor=1
      // left behind after stripping metallicRoughnessTexture) renders pitch black.
      if (mat instanceof THREE.MeshStandardMaterial && (hadMetalnessMap || mat.metalness > 0.6)) {
        mat.metalness = Math.min(mat.metalness, 0.25);
        mat.roughness = Math.max(mat.roughness, 0.55);
        strippedAny = true;
      }
      for (const slot of KEEP_SHARED_MAPS) {
        const tex = rec[slot];
        if (!tex) continue;
        const img = tex.image as { src?: string } | undefined;
        const srcKey = img?.src;
        if (!srcKey) continue;
        const cacheKey = `${srcKey}::${tex.colorSpace}::${tex.flipY ? 1 : 0}`;
        const existing = SHARED_DAE_TEX_CACHE.get(cacheKey);
        if (existing) {
          if (existing !== tex) {
            rec[slot] = existing;
            tex.dispose();
          }
        } else {
          SHARED_DAE_TEX_CACHE.set(cacheKey, tex);
        }
      }
      if (strippedAny) {
        mat.needsUpdate = true;
      }
    }
  });
}

function freezeStaticGroup(group: THREE.Object3D): void {
  group.updateMatrixWorld(true);
  group.traverse((obj) => {
    obj.matrixAutoUpdate = false;
  });
}

function raycastWorldFast(
  raycaster: THREE.Raycaster,
  worldGroup: THREE.Group,
): THREE.Intersection[] {
  const candidates: THREE.Object3D[] = [];
  for (const child of worldGroup.children) {
    const box = child.userData.worldBox as THREE.Box3 | undefined;
    if (!box || raycaster.ray.intersectsBox(box)) {
      candidates.push(child);
    }
  }
  if (candidates.length === 0) return [];
  return raycaster.intersectObjects(candidates, true);
}

function objectHasDiffuseMap(root: THREE.Object3D): boolean {
  let found = false;
  root.traverse((obj) => {
    if (found || !(obj instanceof THREE.Mesh)) return;
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    for (const mat of mats) {
      if (mat && "map" in mat && mat.map) {
        found = true;
        return;
      }
    }
  });
  return found;
}

function applyMaterialTweaks(
  root: THREE.Object3D,
  options: {
    wireframe: boolean;
    doubleSided: boolean;
    albedoTex?: THREE.Texture | null;
    diffuseRgba?: number[] | null;
  },
): void {
  const hasMap = objectHasDiffuseMap(root);
  const applyFallbackAlbedo = Boolean(options.albedoTex) && !hasMap;
  const applyDiffuseTint =
    !hasMap && !applyFallbackAlbedo && Array.isArray(options.diffuseRgba) && options.diffuseRgba.length >= 3;
  root.traverse((obj) => {
    if (!(obj instanceof THREE.Mesh)) return;
    obj.castShadow = false;
    obj.receiveShadow = false;
    const rawMats = Array.isArray(obj.material) ? obj.material : [obj.material];
    const mats = applyDiffuseTint
      ? rawMats.map((m) => (m ? m.clone() : m))
      : rawMats;
    if (applyDiffuseTint) {
      obj.material = Array.isArray(obj.material) ? mats : mats[0];
    }
    for (const mat of mats) {
      if (!mat) continue;
      if (
        applyFallbackAlbedo &&
        options.albedoTex &&
        (mat instanceof THREE.MeshStandardMaterial ||
          mat instanceof THREE.MeshPhongMaterial ||
          mat instanceof THREE.MeshLambertMaterial) &&
        !mat.map
      ) {
        mat.map = options.albedoTex;
      }
      if (applyDiffuseTint && options.diffuseRgba && "color" in mat && mat.color instanceof THREE.Color) {
        mat.color.setRGB(
          options.diffuseRgba[0],
          options.diffuseRgba[1],
          options.diffuseRgba[2],
        );
      }
      mat.side = options.doubleSided ? THREE.DoubleSide : THREE.FrontSide;
      if ("wireframe" in mat) {
        (mat as THREE.MeshStandardMaterial).wireframe = options.wireframe;
      }
      mat.needsUpdate = true;
    }
  });
}

function loadTextureCached(assetUrl: string): Promise<THREE.Texture> {
  const cached = TEX_CACHE.get(assetUrl);
  if (cached) return cached;
  const promise = new THREE.TextureLoader().loadAsync(assetUrl).then((tex) => {
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  });
  TEX_CACHE.set(assetUrl, promise);
  return promise;
}

function loadColladaCached(
  assetUrl: string,
  loadTextures: boolean,
): Promise<THREE.Object3D | null> {
  const cacheKey = `${assetUrl}::${loadTextures ? "tex" : "clay"}`;
  const cached = DAE_CACHE.get(cacheKey);
  if (cached) return cached;
  if (!loadTextures) {
    const glbUrl = `${withGeometryOnlyParam(assetUrl)}&as_glb=1&gv=2`;
    const glbPromise = new GLTFLoader(NO_TEX_ASSET_MANAGER)
      .loadAsync(glbUrl)
      .then((res) => {
        if (!res?.scene) return null;
        const toRemove: THREE.Object3D[] = [];
        res.scene.traverse((child) => {
          if (child instanceof THREE.Light || child instanceof THREE.Camera) {
            toRemove.push(child);
          } else if (child instanceof THREE.Mesh && child.geometry && !child.geometry.attributes.normal) {
            child.geometry.computeVertexNormals();
          }
        });
        for (const node of toRemove) node.removeFromParent();
        res.scene.rotation.set(-Math.PI / 2, 0, 0);
        stripAllTextureMaps(res.scene);
        return res.scene;
      })
      .catch(() =>
        new ColladaLoader(NO_TEX_ASSET_MANAGER)
          .loadAsync(withGeometryOnlyParam(assetUrl))
          .then((res) => {
            if (!res?.scene) return null;
            const toRemove: THREE.Object3D[] = [];
            res.scene.traverse((child) => {
              if (child instanceof THREE.Light || child instanceof THREE.Camera) {
                toRemove.push(child);
              }
            });
            for (const node of toRemove) node.removeFromParent();
            res.scene.rotation.set(-Math.PI / 2, 0, 0);
            stripAllTextureMaps(res.scene);
            return res.scene;
          })
          .catch(() => null),
      );
    DAE_CACHE.set(cacheKey, glbPromise);
    return glbPromise;
  }
  const loader = new ColladaLoader(SHARED_ASSET_MANAGER);
  const promise = loader
    .loadAsync(assetUrl)
    .then((res) => {
      if (!res?.scene) return null;
      const toRemove: THREE.Object3D[] = [];
      res.scene.traverse((child) => {
        if (child instanceof THREE.Light || child instanceof THREE.Camera) {
          toRemove.push(child);
        }
      });
      for (const node of toRemove) {
        node.removeFromParent();
      }
      res.scene.rotation.set(-Math.PI / 2, 0, 0);
      optimizeAndDedupeCollada(res.scene);
      return res.scene;
    })
    .catch(() => null);
  DAE_CACHE.set(cacheKey, promise);
  return promise;
}

function loadGltfCached(
  assetUrl: string,
  loadTextures: boolean,
): Promise<THREE.Object3D | null> {
  const cacheKey = `${assetUrl}::${loadTextures ? "tex" : "clay"}`;
  const cached = GLTF_CACHE.get(cacheKey);
  if (cached) return cached;
  const loader = new GLTFLoader(loadTextures ? SHARED_ASSET_MANAGER : NO_TEX_ASSET_MANAGER);
  const fetchUrl = loadTextures ? assetUrl : withGeometryOnlyParam(assetUrl);
  const promise = loader
    .loadAsync(fetchUrl)
    .then((res) => {
      if (!res?.scene) return null;
      const toRemove: THREE.Object3D[] = [];
      res.scene.traverse((child) => {
        if (child instanceof THREE.Light || child instanceof THREE.Camera) {
          toRemove.push(child);
        }
      });
      for (const node of toRemove) {
        node.removeFromParent();
      }
      res.scene.rotation.set(-Math.PI / 2, 0, 0);
      if (loadTextures) {
        optimizeAndDedupeCollada(res.scene);
      } else {
        stripAllTextureMaps(res.scene);
      }
      return res.scene;
    })
    .catch(() => null);
  GLTF_CACHE.set(cacheKey, promise);
  return promise;
}

function loadStlCached(assetUrl: string): Promise<THREE.BufferGeometry> {
  const cached = STL_CACHE.get(assetUrl);
  if (cached) return cached;
  const promise = new STLLoader().loadAsync(assetUrl);
  STL_CACHE.set(assetUrl, promise);
  return promise;
}

function loadObjCached(assetUrl: string, loadTextures: boolean): Promise<THREE.Object3D> {
  const cacheKey = `${assetUrl}::${loadTextures ? "tex" : "clay"}`;
  const cached = OBJ_CACHE.get(cacheKey);
  if (cached) return cached;
  const loader = new OBJLoader(loadTextures ? SHARED_ASSET_MANAGER : NO_TEX_ASSET_MANAGER);
  const promise = loader.loadAsync(assetUrl).then((obj) => {
    if (!loadTextures) {
      stripAllTextureMaps(obj);
    }
    return obj;
  });
  OBJ_CACHE.set(cacheKey, promise);
  return promise;
}

function buildEnuTriad(size = 1.5): THREE.Group {
  const g = new THREE.Group();
  const headLen = size * 0.22;
  const shaftLen = size - headLen;
  const shaftRadius = 0.045;
  const headRadius = 0.14;

  const makeAxis = (dir: THREE.Vector3, color: number) => {
    const axis = new THREE.Group();
    const mat = new THREE.MeshBasicMaterial({ color });
    const shaft = new THREE.Mesh(
      new THREE.CylinderGeometry(shaftRadius, shaftRadius, shaftLen, 12),
      mat,
    );
    shaft.position.y = shaftLen / 2;
    shaft.userData.ownsGpuResources = true;

    const head = new THREE.Mesh(
      new THREE.ConeGeometry(headRadius, headLen, 14),
      mat,
    );
    head.position.y = shaftLen + headLen / 2;
    head.userData.ownsGpuResources = true;

    axis.add(shaft, head);
    axis.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
    return axis;
  };

  g.add(makeAxis(new THREE.Vector3(1, 0, 0), 0xef4444));
  g.add(makeAxis(new THREE.Vector3(0, 0, -1), 0x22c55e));
  g.add(makeAxis(new THREE.Vector3(0, 1, 0), 0x3b82f6));
  return g;
}

function disposeObject(root: THREE.Object3D, skipTextures = true) {
  root.traverse((node) => {
    if (node.parent instanceof THREE.ArrowHelper) return;
    if (node instanceof THREE.Mesh) {
      if (!node.userData?.ownsGpuResources) return;
      node.geometry.dispose();
      const mats = Array.isArray(node.material) ? node.material : [node.material];
      for (const mat of mats) {
        if (!mat) continue;
        if (!skipTextures) {
          const rec = mat as unknown as Record<string, unknown>;
          for (const k of Object.keys(rec)) {
            const v = rec[k];
            if (v instanceof THREE.Texture) v.dispose();
          }
        }
        mat.dispose();
      }
    }
  });
}

function disposeGroup(group: THREE.Group) {
  while (group.children.length > 0) {
    const child = group.children[0];
    group.remove(child);
    disposeObject(child, true);
  }
}

async function instantiateVisual(
  vis: WorldSceneVisual,
  options: { color: number; wireframe: boolean; doubleSided: boolean; showTextures: boolean },
): Promise<THREE.Object3D> {
  const linkObj = new THREE.Group();
  const visObj = new THREE.Group();
  applyEnuPoseToObject(linkObj, vis.link_pose);
  applyEnuPoseToObject(visObj, vis.visual_pose);
  linkObj.add(visObj);

  const g = vis.geometry;
  if (g.type === "mesh" && g.asset_url && g.ext) {
    if (g.ext === ".dae") {
      const template = await loadColladaCached(g.asset_url, options.showTextures);
      if (template) {
        const cloned = template.clone(true);
        const scaleGroup = new THREE.Group();
        if (g.scale && g.scale.length === 3) {
          scaleGroup.scale.set(g.scale[0], g.scale[2], g.scale[1]);
        }
        scaleGroup.add(cloned);
        let albedoTex: THREE.Texture | null = null;
        if (options.showTextures && vis.albedo_url && !objectHasDiffuseMap(cloned)) {
          albedoTex = await loadTextureCached(vis.albedo_url).catch(() => null);
        }
        applyMaterialTweaks(cloned, {
          wireframe: options.wireframe,
          doubleSided: options.doubleSided,
          albedoTex,
          diffuseRgba: vis.diffuse_rgba,
        });
        visObj.add(scaleGroup);
        return linkObj;
      }
    } else if (g.ext === ".glb" || g.ext === ".gltf") {
      const template = await loadGltfCached(g.asset_url, options.showTextures);
      if (template) {
        const cloned = template.clone(true);
        const scaleGroup = new THREE.Group();
        if (g.scale && g.scale.length === 3) {
          scaleGroup.scale.set(g.scale[0], g.scale[2], g.scale[1]);
        }
        scaleGroup.add(cloned);
        let albedoTex: THREE.Texture | null = null;
        if (options.showTextures && vis.albedo_url && !objectHasDiffuseMap(cloned)) {
          albedoTex = await loadTextureCached(vis.albedo_url).catch(() => null);
        }
        applyMaterialTweaks(cloned, {
          wireframe: options.wireframe,
          doubleSided: options.doubleSided,
          albedoTex,
          diffuseRgba: vis.diffuse_rgba,
        });
        visObj.add(scaleGroup);
        return linkObj;
      }
    } else if (g.ext === ".stl") {
      try {
        const geom = await loadStlCached(g.asset_url);
        const rgb = vis.diffuse_rgba;
        const stlColor = rgb ? new THREE.Color(rgb[0], rgb[1], rgb[2]) : new THREE.Color(options.color);
        const mesh = new THREE.Mesh(
          geom.clone(),
          new THREE.MeshStandardMaterial({
            color: stlColor,
            roughness: 0.55,
            metalness: 0.25,
            wireframe: options.wireframe,
            side: options.doubleSided ? THREE.DoubleSide : THREE.FrontSide,
          }),
        );
        mesh.userData.ownsGpuResources = true;
        mesh.rotation.x = -Math.PI / 2;
        if (g.scale && g.scale.length === 3) {
          mesh.scale.set(g.scale[0], g.scale[1], g.scale[2]);
        }
        visObj.add(mesh);
        return linkObj;
      } catch {
        // Fallback below
      }
    } else if (g.ext === ".obj") {
      try {
        const obj = (await loadObjCached(g.asset_url, options.showTextures)).clone(true);
        obj.rotation.x = -Math.PI / 2;
        if (g.scale && g.scale.length === 3) {
          obj.scale.set(g.scale[0], g.scale[1], g.scale[2]);
        }
        applyMaterialTweaks(obj, {
          wireframe: options.wireframe,
          doubleSided: options.doubleSided,
        });
        visObj.add(obj);
        return linkObj;
      } catch {
        // Fallback below
      }
    }
  }

  let geom: THREE.BufferGeometry;
  if (g.type === "box" && g.size) {
    geom = new THREE.BoxGeometry(g.size[0], g.size[2], g.size[1]);
  } else if (g.type === "cylinder" && g.radius && g.length) {
    geom = new THREE.CylinderGeometry(g.radius, g.radius, g.length, 16);
  } else if (g.type === "sphere" && g.radius) {
    geom = new THREE.SphereGeometry(g.radius, 16, 12);
  } else {
    geom = new THREE.BoxGeometry(1.2, 0.8, 1.2);
  }

  const rgb = vis.diffuse_rgba;
  const primColor = rgb
    ? new THREE.Color(rgb[0], rgb[1], rgb[2])
    : new THREE.Color(options.color);
  let primAlbedoTex: THREE.Texture | null = null;
  if (options.showTextures && vis.albedo_url) {
    primAlbedoTex = await loadTextureCached(vis.albedo_url).catch(() => null);
  }
  const fallbackMesh = new THREE.Mesh(
    geom,
    new THREE.MeshStandardMaterial({
      color: primAlbedoTex ? 0xffffff : primColor,
      map: primAlbedoTex,
      roughness: 0.6,
      metalness: 0.2,
      wireframe: options.wireframe,
      side: options.doubleSided ? THREE.DoubleSide : THREE.FrontSide,
    }),
  );
  fallbackMesh.userData.ownsGpuResources = true;
  visObj.add(fallbackMesh);
  return linkObj;
}

export function WorldViewport3D({
  sceneData,
  members,
  baseStation,
  effectiveCenter,
  fitMode = "world",
  selectedTarget = null,
  onSelectTarget,
  onCenterChange,
  onMemberPoseChange,
  className,
}: WorldViewport3DProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const transformRef = useRef<TransformControls | null>(null);
  const centerMarkerRef = useRef<THREE.Group | null>(null);
  const worldGroupRef = useRef<THREE.Group | null>(null);
  const fleetGroupRef = useRef<THREE.Group | null>(null);
  const gridRef = useRef<THREE.GridHelper | null>(null);
  const triadRef = useRef<THREE.Group | null>(null);
  const pinSphereRef = useRef<THREE.Mesh | null>(null);
  const ambientLightRef = useRef<THREE.AmbientLight | null>(null);
  const hemiLightRef = useRef<THREE.HemisphereLight | null>(null);
  const dirLightRef = useRef<THREE.DirectionalLight | null>(null);
  const airframeTemplatesRef = useRef<Map<string, THREE.Group>>(new Map());
  const airframeFetchingRef = useRef<Set<string>>(new Set());
  const selectableObjectsRef = useRef<Map<string, THREE.Object3D>>(new Map());
  const scheduleRenderRef = useRef<(() => void) | null>(null);
  const onCenterChangeRef = useRef(onCenterChange);
  const onMemberPoseChangeRef = useRef(onMemberPoseChange);
  const onSelectTargetRef = useRef(onSelectTarget);
  const selectedTargetRef = useRef(selectedTarget);
  const effectiveCenterRef = useRef(effectiveCenter);
  const hasAutoFocusedRef = useRef(false);
  const prevSceneRef = useRef<WorldSceneResponse | null>(null);

  const [editTool, setEditTool] = useState<EditTool>("select");
  const [gizmoMode, setGizmoMode] = useState<GizmoMode>("translate");
  const [showOverlays, setShowOverlays] = useState(true);
  const [showAxes, setShowAxes] = useState(false);
  const [showTextures, setShowTextures] = useState(false);
  const [doubleSided, setDoubleSided] = useState(false);
  const [brightness, setBrightness] = useState(1.1);
  const [droneReadyTick, setDroneReadyTick] = useState(0);
  const [loadedCount, setLoadedCount] = useState(0);
  const [hoverEnu, setHoverEnu] = useState<{
    east_m: number;
    north_m: number;
    up_m: number;
  } | null>(null);
  const [pinEnu, setPinEnu] = useState<{
    east_m: number;
    north_m: number;
    up_m: number;
  } | null>(null);
  const [pinCopied, setPinCopied] = useState(false);
  const [jumpInput, setJumpInput] = useState("");
  const [jumpError, setJumpError] = useState(false);

  const clearPin = useCallback(() => {
    setPinEnu(null);
    setPinCopied(false);
    if (pinSphereRef.current) {
      pinSphereRef.current.visible = false;
    }
    scheduleRenderRef.current?.();
  }, []);

  const copyPin = useCallback(() => {
    if (!pinEnu) return;
    const fmt = (v: number) => (Math.abs(v) < 0.005 ? 0 : v).toFixed(2);
    const text = `[${fmt(pinEnu.east_m)}, ${fmt(pinEnu.north_m)}, ${fmt(pinEnu.up_m)}]`;
    void navigator.clipboard?.writeText(text).then(() => {
      setPinCopied(true);
      window.setTimeout(() => setPinCopied(false), 1500);
    });
  }, [pinEnu]);

  const editToolRef = useRef(editTool);
  const doubleSidedRef = useRef(doubleSided);
  const fitModeRef = useRef(fitMode);

  useEffect(() => {
    editToolRef.current = editTool;
    doubleSidedRef.current = doubleSided;
    fitModeRef.current = fitMode;
  }, [editTool, doubleSided, fitMode]);

  useEffect(() => {
    onCenterChangeRef.current = onCenterChange;
    onMemberPoseChangeRef.current = onMemberPoseChange;
    onSelectTargetRef.current = onSelectTarget;
    selectedTargetRef.current = selectedTarget;
    effectiveCenterRef.current = effectiveCenter;
  }, [onCenterChange, onMemberPoseChange, onSelectTarget, selectedTarget, effectiveCenter]);

  useEffect(() => {
    if (!selectedTarget) return;
    const id = window.requestAnimationFrame(() => setShowOverlays(true));
    return () => window.cancelAnimationFrame(id);
  }, [selectedTarget]);

  const focusPose = useCallback((pose: GeoPose | null, distance = 14) => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;
    if (pose) {
      enuToThreePosition(pose.east_m, pose.north_m, pose.up_m, controls.target);
    } else {
      controls.target.set(0, 0, 0);
    }
    camera.position.set(
      controls.target.x - distance * 0.75,
      controls.target.y + distance * 0.65,
      controls.target.z + distance * 0.75,
    );
    controls.update();
    scheduleRenderRef.current?.();
  }, []);

  const handleJump = useCallback(() => {
    const raw = jumpInput.trim();
    if (!raw) {
      setJumpError(true);
      return;
    }
    try {
      const parsed: unknown = JSON.parse(raw);
      let east: number | null = null;
      let north: number | null = null;
      let up: number | null = null;
      if (Array.isArray(parsed) && (parsed.length === 2 || parsed.length === 3)) {
        const e = parsed[0];
        const n = parsed[1];
        const u = parsed.length === 3 ? parsed[2] : 0;
        if (
          typeof e === "number" &&
          Number.isFinite(e) &&
          typeof n === "number" &&
          Number.isFinite(n) &&
          typeof u === "number" &&
          Number.isFinite(u)
        ) {
          east = e;
          north = n;
          up = u;
        }
      } else if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        const rec = parsed as Record<string, unknown>;
        const e = rec.east_m;
        const n = rec.north_m;
        const u = rec.up_m ?? 0;
        if (
          typeof e === "number" &&
          Number.isFinite(e) &&
          typeof n === "number" &&
          Number.isFinite(n) &&
          typeof u === "number" &&
          Number.isFinite(u)
        ) {
          east = e;
          north = n;
          up = u;
        }
      }
      if (east === null || north === null || up === null) {
        setJumpError(true);
        return;
      }
      setJumpError(false);
      focusPose(
        {
          east_m: east,
          north_m: north,
          up_m: up,
          roll_deg: 0,
          pitch_deg: 0,
          yaw_deg: 0,
        },
        fitMode === "object" ? 2.5 : 10,
      );
    } catch {
      setJumpError(true);
    }
  }, [jumpInput, focusPose, fitMode]);

  const fitCameraToWorldGroup = useCallback(() => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    const wg = worldGroupRef.current;
    if (!camera || !controls || !wg || wg.children.length === 0) return;
    wg.updateMatrixWorld(true);
    const box = new THREE.Box3();
    for (const child of wg.children) {
      if (child.name === "ground_plane") continue;
      box.expandByObject(child);
    }
    if (box.isEmpty()) {
      box.setFromObject(wg);
    }
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    if (fitMode === "object") {
      const radius = Math.max(size.length() * 0.5, 0.25);
      const dist = Math.min(radius * 2.2, 180);
      controls.target.copy(center);
      camera.position.set(
        center.x - dist * 0.72,
        center.y + dist * 0.52,
        center.z + dist * 0.72,
      );
    } else {
      const dist = Math.min(Math.max(size.length() * 0.7, 2.5), 180);
      controls.target.copy(center);
      camera.position.set(
        center.x - dist * 0.65,
        center.y + dist * 0.55,
        center.z + dist * 0.65,
      );
    }
    controls.update();
    scheduleRenderRef.current?.();
  }, [fitMode]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    activeViewportCount += 1;
    if (viewerCachePurgeTimer !== null) {
      window.clearTimeout(viewerCachePurgeTimer);
      viewerCachePurgeTimer = null;
    }
    const airframeTemplates = airframeTemplatesRef.current;
    const airframeFetching = airframeFetchingRef.current;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x070a0f);

    const width = Math.max(1, container.clientWidth);
    const height = Math.max(1, container.clientHeight);
    const initialObjectMode = fitModeRef.current === "object";
    const camera = new THREE.PerspectiveCamera(
      initialObjectMode ? 45 : 55,
      width / height,
      initialObjectMode ? 0.05 : 0.2,
      3000,
    );
    if (initialObjectMode) {
      camera.position.set(-2.2, 1.6, 2.2);
    } else {
      camera.position.set(-10, 14, 14);
    }
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      powerPreference: "high-performance",
    });
    const hiDpr = Math.min(window.devicePixelRatio || 1, 1.5);
    let currentDpr = hiDpr;
    let idleRestoreTimer: number | null = null;
    renderer.setPixelRatio(hiDpr);
    renderer.setSize(width, height);
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1.1;
    rendererRef.current = renderer;
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.12;
    controls.minDistance = initialObjectMode ? 0.1 : 0.25;
    controls.maxDistance = 1500;
    controls.zoomToCursor = true;
    controls.zoomSpeed = 1.25;
    controls.panSpeed = 1.15;
    controls.screenSpacePanning = true;
    controls.mouseButtons = {
      LEFT: THREE.MOUSE.PAN,
      MIDDLE: THREE.MOUSE.ROTATE,
      RIGHT: THREE.MOUSE.ROTATE,
    };
    controlsRef.current = controls;

    const setInteractiveDpr = (active: boolean) => {
      if (hiDpr <= 1.05) return;
      const next = active ? 1 : hiDpr;
      if (currentDpr !== next) {
        currentDpr = next;
        renderer.setPixelRatio(next);
        const w = Math.max(1, container.clientWidth);
        const h = Math.max(1, container.clientHeight);
        renderer.setSize(w, h, false);
      }
      if (idleRestoreTimer !== null) {
        window.clearTimeout(idleRestoreTimer);
        idleRestoreTimer = null;
      }
      if (active) {
        idleRestoreTimer = window.setTimeout(() => {
          idleRestoreTimer = null;
          setInteractiveDpr(false);
          scheduleRenderRef.current?.();
        }, 160);
      }
    };

    let rafId = 0;
    const tick = () => {
      rafId = 0;
      const moving = controls.update();
      renderer.render(scene, camera);
      if (moving) {
        scheduleRender();
      }
    };
    const scheduleRender = () => {
      if (!rafId) {
        rafId = window.requestAnimationFrame(tick);
      }
    };
    scheduleRenderRef.current = scheduleRender;

    const onOrbitStart = () => setInteractiveDpr(true);
    const onOrbitChange = () => {
      if (controls.enabled) scheduleRender();
    };
    controls.addEventListener("start", onOrbitStart);
    controls.addEventListener("change", onOrbitChange);

    const transform = new TransformControls(camera, renderer.domElement);
    transform.setMode("translate");
    transform.setSize(0.75);
    scene.add(transform.getHelper());
    transformRef.current = transform;

    let isDraggingGizmo = false;
    const onDraggingChanged = (event: { value: unknown }) => {
      isDraggingGizmo = Boolean(event.value);
      controls.enabled = !isDraggingGizmo;
      if (isDraggingGizmo) setInteractiveDpr(true);
      if (!isDraggingGizmo && transform.object) {
        const key = (transform.object.userData?.pickTarget as string | undefined) ?? "anchor";
        const enu = threeToEnuPosition(transform.object.position);
        const yaw = threeQuaternionToEnuYawDeg(transform.object.quaternion);
        if (key === "anchor") {
          const base = effectiveCenterRef.current;
          onCenterChangeRef.current?.({
            east_m: Number(enu.east_m.toFixed(3)),
            north_m: Number(enu.north_m.toFixed(3)),
            up_m: Number(enu.up_m.toFixed(3)),
            roll_deg: base?.roll_deg ?? 0,
            pitch_deg: base?.pitch_deg ?? 0,
            yaw_deg: Number(yaw.toFixed(2)),
          });
        } else {
          onMemberPoseChangeRef.current?.(key, {
            east_m: Number(enu.east_m.toFixed(3)),
            north_m: Number(enu.north_m.toFixed(3)),
            up_m: Number(enu.up_m.toFixed(3)),
            roll_deg: 0,
            pitch_deg: 0,
            yaw_deg: Number(yaw.toFixed(2)),
          });
        }
      }
      scheduleRender();
    };
    const onTransformChange = () => scheduleRender();
    transform.addEventListener("dragging-changed", onDraggingChanged);
    transform.addEventListener("change", onTransformChange);
    transform.addEventListener("objectChange", onTransformChange);

    const ambient = new THREE.AmbientLight(0xffffff, 0.85);
    const hemi = new THREE.HemisphereLight(0xf1f5f9, 0x94a3b8, 0.5);
    const dir = new THREE.DirectionalLight(0xfffbeb, 0.65);
    dir.position.set(35, 60, 25);
    ambientLightRef.current = ambient;
    hemiLightRef.current = hemi;
    dirLightRef.current = dir;
    scene.add(ambient, hemi, dir);

    const grid = new THREE.GridHelper(240, 120, 0x334155, 0x1e293b);
    grid.position.y = -0.02;
    grid.visible = false;
    scene.add(grid);
    gridRef.current = grid;

    const triad = buildEnuTriad(2.0);
    triad.visible = false;
    scene.add(triad);
    triadRef.current = triad;

    const worldGroup = new THREE.Group();
    scene.add(worldGroup);
    worldGroupRef.current = worldGroup;

    const fleetGroup = new THREE.Group();
    scene.add(fleetGroup);
    fleetGroupRef.current = fleetGroup;

    const centerMarker = new THREE.Group();
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.65, 0.82, 36),
      new THREE.MeshBasicMaterial({
        color: 0xf97316,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.9,
      }),
    );
    ring.rotation.x = -Math.PI / 2;
    ring.userData.ownsGpuResources = true;
    const pillar = new THREE.Mesh(
      new THREE.CylinderGeometry(0.05, 0.05, 0.9, 12),
      new THREE.MeshBasicMaterial({ color: 0xf97316, transparent: true, opacity: 0.85 }),
    );
    pillar.position.y = 0.45;
    pillar.userData.ownsGpuResources = true;
    const dirArrow = new THREE.ArrowHelper(
      new THREE.Vector3(1, 0, 0),
      new THREE.Vector3(0, 0.05, 0),
      1.25,
      0xf97316,
      0.3,
      0.18,
    );
    centerMarker.add(ring, pillar, dirArrow);
    centerMarker.visible = false;
    scene.add(centerMarker);
    centerMarkerRef.current = centerMarker;

    const hoverRing = new THREE.Mesh(
      new THREE.RingGeometry(0.35, 0.48, 24),
      new THREE.MeshBasicMaterial({
        color: 0x38bdf8,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.85,
      }),
    );
    hoverRing.rotation.x = -Math.PI / 2;
    hoverRing.visible = false;
    hoverRing.userData.ownsGpuResources = true;
    scene.add(hoverRing);

    const pinSphere = new THREE.Mesh(
      new THREE.SphereGeometry(1, 20, 16),
      new THREE.MeshStandardMaterial({
        color: 0xef4444,
        emissive: 0x991b1b,
        emissiveIntensity: 0.55,
        roughness: 0.35,
        metalness: 0.1,
      }),
    );
    pinSphere.visible = false;
    pinSphere.userData.ownsGpuResources = true;
    scene.add(pinSphere);
    pinSphereRef.current = pinSphere;

    const raycaster = new THREE.Raycaster();
    const pointerNdc = new THREE.Vector2();
    const lookDir = new THREE.Vector3();
    let pointerDownXY: { x: number; y: number } | null = null;

    const updateNdc = (ev: { clientX: number; clientY: number }) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointerNdc.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      pointerNdc.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    };

    const syncTargetDepthToCursor = (ev: { clientX: number; clientY: number }) => {
      if (worldGroup.children.length === 0) return null;
      updateNdc(ev);
      raycaster.setFromCamera(pointerNdc, camera);
      const hits = raycastWorldFast(raycaster, worldGroup);
      if (hits.length === 0) return null;
      const hitDist = hits[0].distance;
      const curDist = camera.position.distanceTo(controls.target);
      const targetDepth = Math.min(Math.max(hitDist, 1.5), 450);
      if (Math.abs(curDist - targetDepth) > Math.max(2.0, curDist * 0.25)) {
        camera.getWorldDirection(lookDir);
        controls.target.copy(camera.position).addScaledVector(lookDir, targetDepth);
      }
      return hits[0];
    };

    const onWheelCapture = (ev: WheelEvent) => {
      setInteractiveDpr(true);
      scheduleRender();
      if (worldGroup.children.length === 0) return;
      updateNdc(ev);
      raycaster.setFromCamera(pointerNdc, camera);
      const hits = raycastWorldFast(raycaster, worldGroup);
      if (hits.length === 0) return;
      const hitDist = hits[0].distance;
      const curDist = camera.position.distanceTo(controls.target);
      if (ev.deltaY < 0 && hitDist < 0.75 && curDist < 1.0) {
        ev.preventDefault();
        ev.stopPropagation();
        const step = 0.65;
        camera.position.addScaledVector(raycaster.ray.direction, step);
        controls.target.addScaledVector(raycaster.ray.direction, step);
        scheduleRender();
        return;
      }
      const targetDepth = Math.min(Math.max(hitDist, 1.2), 450);
      if (Math.abs(curDist - targetDepth) > Math.max(1.5, curDist * 0.25)) {
        camera.getWorldDirection(lookDir);
        controls.target.copy(camera.position).addScaledVector(lookDir, targetDepth);
      }
    };

    const onPointerDown = (ev: PointerEvent) => {
      scheduleRender();
      if (ev.button !== 0) return;
      if (!isDraggingGizmo && transform.axis === null) {
        syncTargetDepthToCursor(ev);
      }
      pointerDownXY = { x: ev.clientX, y: ev.clientY };
    };

    let lastRaycastMs = 0;
    let lastHoverKey: string | null = null;

    const clearHover = () => {
      if (lastHoverKey !== null) {
        lastHoverKey = null;
        setHoverEnu(null);
      }
      if (hoverRing.visible) {
        hoverRing.visible = false;
        scheduleRender();
      }
    };

    const onPointerMove = (ev: PointerEvent) => {
      const isPickFloor =
        editToolRef.current === "pick_floor" && Boolean(onCenterChangeRef.current);

      if (!isPickFloor && hoverRing.visible) {
        hoverRing.visible = false;
        scheduleRender();
      }

      if (ev.buttons !== 0 || isDraggingGizmo || worldGroup.children.length === 0) {
        if (lastHoverKey !== null) {
          lastHoverKey = null;
          setHoverEnu(null);
        }
        return;
      }

      const now = performance.now();
      if (!isPickFloor && now - lastRaycastMs < 40) return;
      lastRaycastMs = now;

      updateNdc(ev);
      raycaster.setFromCamera(pointerNdc, camera);
      const hits = raycastWorldFast(raycaster, worldGroup);
      if (hits.length > 0) {
        const enu = threeToEnuPosition(hits[0].point);
        const key = `${enu.east_m.toFixed(2)},${enu.north_m.toFixed(2)},${enu.up_m.toFixed(2)}`;
        if (key !== lastHoverKey) {
          lastHoverKey = key;
          setHoverEnu(enu);
        }
        if (isPickFloor) {
          hoverRing.position.copy(hits[0].point);
          hoverRing.position.y += 0.03;
          hoverRing.visible = true;
          scheduleRender();
        }
      } else {
        clearHover();
      }
    };

    const onPointerLeave = () => {
      clearHover();
    };

    const onPointerUp = (ev: PointerEvent) => {
      if (ev.button !== 0 || !pointerDownXY) return;
      const dist = Math.hypot(ev.clientX - pointerDownXY.x, ev.clientY - pointerDownXY.y);
      pointerDownXY = null;
      if (dist > 5 || isDraggingGizmo) return;
      updateNdc(ev);
      raycaster.setFromCamera(pointerNdc, camera);
      if (ev.shiftKey) {
        const hits = raycastWorldFast(raycaster, worldGroup);
        if (hits.length > 0) {
          const pt = hits[0].point;
          const r = Math.min(Math.max(hits[0].distance * 0.012, 0.015), 0.35);
          pinSphere.position.copy(pt);
          pinSphere.scale.setScalar(r);
          pinSphere.visible = true;
          setPinEnu(threeToEnuPosition(pt));
          scheduleRender();
        }
        return;
      }
      if (editToolRef.current === "pick_floor" || ev.altKey) {
        const hits = raycastWorldFast(raycaster, worldGroup);
        if (hits.length > 0) {
          const enu = threeToEnuPosition(hits[0].point);
          const targetKey = selectedTargetRef.current ?? "anchor";
          if (targetKey !== "anchor" && onMemberPoseChangeRef.current) {
            onMemberPoseChangeRef.current(targetKey, {
              east_m: Number(enu.east_m.toFixed(3)),
              north_m: Number(enu.north_m.toFixed(3)),
              up_m: Number((enu.up_m + 0.3).toFixed(3)),
              roll_deg: 0,
              pitch_deg: 0,
              yaw_deg: 0,
            });
          } else if (onCenterChangeRef.current) {
            const base = effectiveCenterRef.current;
            onCenterChangeRef.current({
              east_m: Number(enu.east_m.toFixed(3)),
              north_m: Number(enu.north_m.toFixed(3)),
              up_m: Number((enu.up_m + 0.3).toFixed(3)),
              roll_deg: base?.roll_deg ?? 0,
              pitch_deg: base?.pitch_deg ?? 0,
              yaw_deg: base?.yaw_deg ?? 0,
            });
          }
        }
        return;
      }

      if (onSelectTargetRef.current) {
        const pickHits = raycaster.intersectObjects(
          [...fleetGroup.children, centerMarker],
          true,
        );
        for (const hit of pickHits) {
          const targetKey = hit.object.userData?.pickTarget as string | undefined;
          if (targetKey) {
            onSelectTargetRef.current(targetKey);
            return;
          }
        }
      }
    };

    const onDoubleClick = (ev: MouseEvent) => {
      if (isDraggingGizmo || editToolRef.current === "pick_floor") return;
      updateNdc(ev);
      raycaster.setFromCamera(pointerNdc, camera);
      const hits = raycastWorldFast(raycaster, worldGroup);
      if (hits.length === 0) return;
      const hitPoint = hits[0].point;
      const curDist = camera.position.distanceTo(controls.target);
      const focusDist = Math.min(Math.max(4, hits[0].distance * 0.45), Math.min(curDist, 14));
      const dirToCam = camera.position.clone().sub(hitPoint);
      if (dirToCam.lengthSq() > 1e-6) {
        dirToCam.normalize();
      } else {
        camera.getWorldDirection(dirToCam).negate();
      }
      controls.target.copy(hitPoint);
      camera.position.copy(hitPoint).addScaledVector(dirToCam, focusDist);
      controls.update();
      scheduleRender();
    };

    renderer.domElement.addEventListener("wheel", onWheelCapture, { capture: true, passive: false });
    renderer.domElement.addEventListener("pointerdown", onPointerDown, { capture: true });
    renderer.domElement.addEventListener("pointermove", onPointerMove);
    renderer.domElement.addEventListener("pointerleave", onPointerLeave);
    renderer.domElement.addEventListener("pointerup", onPointerUp);
    renderer.domElement.addEventListener("dblclick", onDoubleClick);

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const w = Math.max(1, entry.contentRect.width);
      const h = Math.max(1, entry.contentRect.height);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
      scheduleRender();
    });
    resizeObserver.observe(container);
    scheduleRender();

    return () => {
      scheduleRenderRef.current = null;
      if (idleRestoreTimer !== null) window.clearTimeout(idleRestoreTimer);
      if (rafId) window.cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
      controls.removeEventListener("start", onOrbitStart);
      controls.removeEventListener("change", onOrbitChange);
      transform.removeEventListener("dragging-changed", onDraggingChanged);
      transform.removeEventListener("change", onTransformChange);
      transform.removeEventListener("objectChange", onTransformChange);
      renderer.domElement.removeEventListener("wheel", onWheelCapture, { capture: true });
      renderer.domElement.removeEventListener("pointerdown", onPointerDown, { capture: true });
      renderer.domElement.removeEventListener("pointermove", onPointerMove);
      renderer.domElement.removeEventListener("pointerleave", onPointerLeave);
      renderer.domElement.removeEventListener("pointerup", onPointerUp);
      renderer.domElement.removeEventListener("dblclick", onDoubleClick);
      transform.dispose();
      controls.dispose();
      disposeGroup(worldGroup);
      disposeGroup(fleetGroup);
      disposeObject(centerMarker);
      disposeObject(hoverRing);
      disposeObject(pinSphere);
      pinSphereRef.current = null;
      grid.geometry.dispose();
      (grid.material as THREE.Material).dispose();
      renderer.renderLists.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
      rendererRef.current = null;
      airframeTemplates.clear();
      airframeFetching.clear();
      activeViewportCount = Math.max(0, activeViewportCount - 1);
      if (activeViewportCount === 0) {
        if (viewerCachePurgeTimer !== null) {
          window.clearTimeout(viewerCachePurgeTimer);
        }
        viewerCachePurgeTimer = window.setTimeout(purgeAllViewerCaches, 5000);
      }
    };
  }, []);

  useEffect(() => {
    const triad = triadRef.current;
    if (!triad) return;
    if (baseStation) {
      applyEnuPoseToObject(triad, baseStation);
    } else {
      triad.position.set(0, 0, 0);
      triad.quaternion.identity();
    }
    scheduleRenderRef.current?.();
  }, [baseStation]);

  useEffect(() => {
    const triad = triadRef.current;
    if (!triad) return;
    triad.visible = showAxes;
    scheduleRenderRef.current?.();
  }, [showAxes]);

  useEffect(() => {
    if (worldGroupRef.current) {
      applyMaterialTweaks(worldGroupRef.current, { wireframe: false, doubleSided });
      scheduleRenderRef.current?.();
    }
  }, [doubleSided]);

  useEffect(() => {
    if (rendererRef.current) rendererRef.current.toneMappingExposure = brightness;
    if (ambientLightRef.current) ambientLightRef.current.intensity = 0.8 * brightness;
    if (hemiLightRef.current) hemiLightRef.current.intensity = 0.8 * brightness;
    if (dirLightRef.current) dirLightRef.current.intensity = 0.95 * brightness;
    scheduleRenderRef.current?.();
  }, [brightness]);

  useEffect(() => {
    const tc = transformRef.current;
    if (!tc) return;
    if (gizmoMode === "rotate") {
      tc.setMode("rotate");
      tc.showX = false;
      tc.showY = true;
      tc.showZ = false;
    } else {
      tc.setMode("translate");
      tc.showX = true;
      tc.showY = true;
      tc.showZ = true;
    }
    scheduleRenderRef.current?.();
  }, [gizmoMode]);

  useEffect(() => {
    const worldGroup = worldGroupRef.current;
    if (!worldGroup) return;
    const sceneChanged = prevSceneRef.current !== sceneData;
    prevSceneRef.current = sceneData;

    disposeGroup(worldGroup);
    setLoadedCount(0);
    if (sceneChanged) {
      setPinEnu(null);
      if (pinSphereRef.current) {
        pinSphereRef.current.visible = false;
      }
      if (fitMode === "object") {
        hasAutoFocusedRef.current = false;
      }
    }

    if (!sceneData || sceneData.models.length === 0) {
      scheduleRenderRef.current?.();
      return;
    }

    let cancelled = false;
    const refEnu = sceneData.base_station ?? { east_m: 0, north_m: 0, up_m: 0 };
    const distSq = (m: (typeof sceneData.models)[number]) =>
      (m.pose.east_m - refEnu.east_m) ** 2 +
      (m.pose.north_m - refEnu.north_m) ** 2 +
      (m.pose.up_m - refEnu.up_m) ** 2;
    const queue = [...sceneData.models].sort((a, b) => {
      if (a.is_base_station !== b.is_base_station) return a.is_base_station ? -1 : 1;
      return distSq(a) - distSq(b);
    });

    let nextIdx = 0;
    let completed = 0;
    const concurrency = Math.min(3, queue.length);

    const runWorker = async () => {
      while (!cancelled) {
        const idx = nextIdx++;
        if (idx >= queue.length) return;
        const model = queue[idx];
        const modelObj = new THREE.Group();
        modelObj.name = model.name;
        applyEnuPoseToObject(modelObj, model.pose);

        const color = model.is_base_station ? 0xf59e0b : 0x64748b;
        const built = await Promise.all(
          model.visuals.map((vis) =>
            instantiateVisual(vis, {
              color,
              wireframe: false,
              doubleSided: doubleSidedRef.current,
              showTextures,
            }),
          ),
        );
        if (cancelled) {
          built.forEach((b) => disposeObject(b));
          return;
        }
        for (const v of built) modelObj.add(v);

        if (model.is_base_station) {
          const halo = new THREE.Mesh(
            new THREE.RingGeometry(1.1, 1.35, 32),
            new THREE.MeshBasicMaterial({
              color: 0xf59e0b,
              side: THREE.DoubleSide,
              transparent: true,
              opacity: 0.75,
            }),
          );
          halo.rotation.x = -Math.PI / 2;
          halo.position.y = 0.05;
          halo.userData.ownsGpuResources = true;
          modelObj.add(halo);
        }

        worldGroup.add(modelObj);
        freezeStaticGroup(modelObj);
        const box = new THREE.Box3().setFromObject(modelObj);
        if (!box.isEmpty()) modelObj.userData.worldBox = box;

        completed += 1;
        setLoadedCount(completed);
        scheduleRenderRef.current?.();
        await new Promise((r) => setTimeout(r, 0));
      }
    };

    void Promise.all(Array.from({ length: concurrency }, () => runWorker())).then(() => {
      if (!cancelled && !hasAutoFocusedRef.current && !sceneData.base_station) {
        hasAutoFocusedRef.current = true;
        fitCameraToWorldGroup();
      }
    });

    return () => {
      cancelled = true;
    };
  }, [sceneData, fitCameraToWorldGroup, fitMode, showTextures]);

  useEffect(() => {
    if (!showTextures && activeViewportCount <= 1) {
      purgeTexturedViewerCaches();
    }
  }, [showTextures]);

  useEffect(() => {
    const modeTag = showTextures ? "tex" : "clay";
    const needed = Array.from(
      new Set(
        members
          .map((m) => assetRefToKey(m.vehicle.airframe))
          .filter((k): k is string => Boolean(k)),
      ),
    );
    for (const airframeKey of needed) {
      const tmplKey = `${airframeKey}::${modeTag}`;
      if (
        airframeTemplatesRef.current.has(tmplKey) ||
        airframeFetchingRef.current.has(tmplKey)
      ) {
        continue;
      }
      airframeFetchingRef.current.add(tmplKey);
      const encodedPath = airframeKey
        .split("/")
        .map((seg) => encodeURIComponent(seg))
        .join("/");
      const loadVisuals = fetch(`/api/vehicles/airframe-visuals/${encodedPath}`)
        .then((r) => (r.ok ? (r.json() as Promise<{ visuals?: WorldSceneVisual[] }>) : null))
        .then((payload) => payload?.visuals ?? [])
        .catch(() => [] as WorldSceneVisual[]);

      void loadVisuals
        .then(async (visuals) => {
          if (visuals.length === 0) return;
          const built = await Promise.all(
            visuals.map((vis) =>
              instantiateVisual(vis, {
                color: 0x475569,
                wireframe: false,
                doubleSided: false,
                showTextures,
              }),
            ),
          );
          const tmpl = new THREE.Group();
          for (const obj of built) tmpl.add(obj);
          airframeTemplatesRef.current.set(tmplKey, tmpl);
          setDroneReadyTick((v) => v + 1);
        })
        .finally(() => {
          airframeFetchingRef.current.delete(tmplKey);
        });
    }
  }, [members, showTextures]);

  useEffect(() => {
    const fleetGroup = fleetGroupRef.current;
    const marker = centerMarkerRef.current;
    const transform = transformRef.current;
    if (!fleetGroup || !marker) return;
    if (transform) transform.detach();
    disposeGroup(fleetGroup);
    selectableObjectsRef.current.clear();

    if (effectiveCenter) {
      const anchorSelected = selectedTarget === "anchor";
      const anchorColor = anchorSelected ? 0xf97316 : 0xfb923c;
      const anchorOpacity = anchorSelected ? 0.95 : 0.4;
      marker.visible = showOverlays;
      marker.userData = { pickTarget: "anchor" };
      marker.traverse((c) => {
        c.userData.pickTarget = "anchor";
        if (
          (c instanceof THREE.Mesh || c instanceof THREE.Line) &&
          (c.material instanceof THREE.MeshBasicMaterial ||
            c.material instanceof THREE.LineBasicMaterial)
        ) {
          c.material.color.setHex(anchorColor);
          c.material.transparent = true;
          c.material.opacity = anchorOpacity;
        }
      });
      applyEnuPoseToObject(marker, effectiveCenter);
      selectableObjectsRef.current.set("anchor", marker);
      if (gridRef.current) {
        gridRef.current.position.y = Math.max(-0.02, effectiveCenter.up_m - 0.3);
      }
    } else {
      marker.visible = false;
    }

    for (const m of members) {
      const ns = m.vehicle.namespace;
      const isSelected = selectedTarget === ns;
      const drone = new THREE.Group();
      drone.name = `spawn-drone-${ns}`;
      drone.userData = { pickTarget: ns };
      applyEnuPoseToObject(drone, m.pose);

      const hitSphere = new THREE.Mesh(
        new THREE.SphereGeometry(0.55, 10, 8),
        new THREE.MeshBasicMaterial({ visible: false }),
      );
      hitSphere.userData = { pickTarget: ns, ownsGpuResources: true };
      drone.add(hitSphere);

      const ring = new THREE.Mesh(
        new THREE.RingGeometry(isSelected ? 0.4 : 0.42, isSelected ? 0.52 : 0.48, 28),
        new THREE.MeshBasicMaterial({
          color: isSelected ? 0x38bdf8 : 0x10b981,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: isSelected ? 1.0 : 0.85,
        }),
      );
      ring.rotation.x = -Math.PI / 2;
      ring.position.y = 0.02;
      ring.visible = showOverlays;
      ring.userData = { pickTarget: ns, ownsGpuResources: true };
      drone.add(ring);

      const airframeKey = assetRefToKey(m.vehicle.airframe) ?? "";
      const tmplKey = `${airframeKey}::${showTextures ? "tex" : "clay"}`;
      const tmpl = airframeTemplatesRef.current.get(tmplKey);
      if (tmpl) {
        const meshClone = tmpl.clone(true);
        meshClone.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.userData = { pickTarget: ns };
          }
        });
        drone.add(meshClone);
      } else {
        const body = new THREE.Mesh(
          new THREE.BoxGeometry(0.45, 0.14, 0.45),
          new THREE.MeshStandardMaterial({ color: isSelected ? 0x38bdf8 : 0x10b981 }),
        );
        body.userData = { pickTarget: ns, ownsGpuResources: true };
        drone.add(body);
      }

      const arrow = new THREE.ArrowHelper(
        new THREE.Vector3(1, 0, 0),
        new THREE.Vector3(0, 0.04, 0),
        0.75,
        isSelected ? 0x38bdf8 : 0xfacc15,
        0.2,
        0.12,
      );
      arrow.visible = showOverlays;
      drone.add(arrow);
      fleetGroup.add(drone);
      selectableObjectsRef.current.set(ns, drone);
    }

    if (transform && selectedTarget && showOverlays && (onCenterChange || onMemberPoseChange)) {
      const targetObj = selectableObjectsRef.current.get(selectedTarget);
      if (targetObj) {
        transform.attach(targetObj);
      }
    }
    scheduleRenderRef.current?.();
  }, [members, effectiveCenter, selectedTarget, showOverlays, showTextures, onCenterChange, onMemberPoseChange, droneReadyTick]);

  useEffect(() => {
    hasAutoFocusedRef.current = false;
  }, [sceneData?.source_world]);

  useEffect(() => {
    if (hasAutoFocusedRef.current) return;
    if (effectiveCenter) {
      hasAutoFocusedRef.current = true;
      focusPose(effectiveCenter, 14);
    } else if (baseStation) {
      hasAutoFocusedRef.current = true;
      focusPose(baseStation, 16);
    }
  }, [effectiveCenter, baseStation, focusPose]);

  const totalModels = sceneData?.models.length ?? 0;
  const pct = totalModels > 0 ? Math.round((Math.min(loadedCount, totalModels) / totalModels) * 100) : 100;

  return (
    <div
      className={
        className ??
        "flex h-[580px] flex-col overflow-hidden rounded-xl border border-zinc-800 bg-[#070a0f] text-slate-200"
      }
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 bg-zinc-950 px-3 py-2 text-xs">
        <div className="flex flex-wrap items-center gap-1.5">
          {onCenterChange && (
            <>
              <div className="flex rounded-lg border border-zinc-800 bg-zinc-900 p-0.5 font-mono text-[11px]">
                <button
                  type="button"
                  onClick={() => setEditTool("select")}
                  className={`rounded px-2 py-1 transition ${
                    editTool === "select"
                      ? "bg-orange-500/20 text-orange-300"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Select/Gizmo
                </button>
                <button
                  type="button"
                  onClick={() => setEditTool("pick_floor")}
                  className={`rounded px-2 py-1 transition ${
                    editTool === "pick_floor"
                      ? "bg-sky-500/20 text-sky-300"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Pick Floor
                </button>
              </div>
              <div className="flex rounded-lg border border-zinc-800 bg-zinc-900 p-0.5 font-mono text-[11px]">
                <button
                  type="button"
                  onClick={() => setGizmoMode("translate")}
                  className={`rounded px-2 py-1 transition ${
                    gizmoMode === "translate"
                      ? "bg-slate-700 text-white"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  XYZ
                </button>
                <button
                  type="button"
                  onClick={() => setGizmoMode("rotate")}
                  className={`rounded px-2 py-1 transition ${
                    gizmoMode === "rotate"
                      ? "bg-slate-700 text-white"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Yaw
                </button>
              </div>
            </>
          )}
          <button
            type="button"
            onClick={() => {
              if (fitMode === "object") {
                fitCameraToWorldGroup();
                return;
              }
              const target = effectiveCenter ?? members[0]?.pose ?? baseStation ?? null;
              if (target) focusPose(target, 12);
              else fitCameraToWorldGroup();
            }}
            className="rounded-md border border-zinc-800 bg-zinc-900 px-2 py-1 font-mono text-[11px] text-slate-300 hover:border-orange-500/50 hover:text-orange-200"
          >
            Focus
          </button>
          {fitMode !== "object" && baseStation && (
            <button
              type="button"
              onClick={() => focusPose(baseStation, 14)}
              className="rounded-md border border-zinc-800 bg-zinc-900 px-2 py-1 font-mono text-[11px] text-amber-300 hover:border-amber-500/50"
            >
              Base
            </button>
          )}
          <button
            type="button"
            onClick={() => fitCameraToWorldGroup()}
            className="rounded-md border border-zinc-800 bg-zinc-900 px-2 py-1 font-mono text-[11px] text-slate-300 hover:border-sky-500/50"
          >
            {fitMode === "object" ? "Fit" : "Fit World"}
          </button>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleJump();
            }}
            className="flex items-center gap-1"
          >
            <input
              type="text"
              value={jumpInput}
              onChange={(e) => {
                setJumpInput(e.target.value);
                if (jumpError) setJumpError(false);
              }}
              placeholder="[E, N, U]"
              aria-label="Jump to JSON coordinates"
              title="JSON coordinates [E, N, U], e.g. [6.04, -3.62, 0.00]"
              className={`w-36 rounded-md border bg-zinc-900 px-2 py-1 font-mono text-[11px] text-slate-200 placeholder:text-zinc-500 outline-none transition ${
                jumpError
                  ? "border-rose-500 focus:border-rose-400"
                  : "border-zinc-800 focus:border-sky-500/70"
              }`}
            />
            <button
              type="submit"
              className="rounded-md border border-zinc-800 bg-zinc-900 px-2 py-1 font-mono text-[11px] text-sky-300 hover:border-sky-500/50 hover:text-sky-200"
            >
              Jump
            </button>
          </form>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
          <label className="flex items-center gap-1.5 rounded-md border border-zinc-800 bg-zinc-900 px-2 py-1">
            <span className="text-amber-300">Brightness</span>
            <input
              type="range"
              min={0.3}
              max={2.8}
              step={0.05}
              value={brightness}
              onChange={(e) => setBrightness(Number(e.target.value))}
              className="w-16 accent-orange-500"
            />
          </label>
          <button
            type="button"
            onClick={() => setShowTextures((v) => !v)}
            className={`rounded-md border px-2 py-1 transition ${
              showTextures
                ? "border-amber-500/50 bg-amber-500/15 text-amber-200"
                : "border-zinc-800 bg-zinc-900 text-slate-400 hover:text-white"
            }`}
          >
            Textures
          </button>
          <button
            type="button"
            onClick={() => setDoubleSided((v) => !v)}
            className={`rounded-md border px-2 py-1 transition ${
              doubleSided
                ? "border-purple-500/50 bg-purple-500/15 text-purple-200"
                : "border-zinc-800 bg-zinc-900 text-slate-400 hover:text-white"
            }`}
          >
            2-Sided
          </button>
          <button
            type="button"
            onClick={() => setShowAxes((v) => !v)}
            className={`rounded-md border px-2 py-1 transition ${
              showAxes
                ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
                : "border-zinc-800 bg-zinc-900 text-slate-400 hover:text-white"
            }`}
          >
            Axes
          </button>
          {(onCenterChange || members.length > 0) && (
            <button
              type="button"
              onClick={() => {
                const next = !showOverlays;
                setShowOverlays(next);
                if (!next) onSelectTarget?.(null);
              }}
              className={`rounded-md border px-2 py-1 transition ${
                showOverlays
                  ? "border-cyan-500/40 bg-cyan-500/15 text-cyan-300"
                  : "border-zinc-800 bg-zinc-900 text-slate-400 hover:text-white"
              }`}
            >
              Overlays
            </button>
          )}
          {onSelectTarget && (
            <button
              type="button"
              disabled={!selectedTarget}
              onClick={() => onSelectTarget(null)}
              className={`rounded-md border px-2 py-1 transition ${
                selectedTarget
                  ? "border-zinc-800 bg-zinc-900 text-rose-300 hover:border-rose-500/50"
                  : "cursor-not-allowed border-zinc-600 bg-zinc-600 text-white opacity-75"
              }`}
            >
              Deselect
            </button>
          )}
        </div>
      </div>

      <div className="relative min-h-0 flex-1">
        <div ref={containerRef} className="h-full w-full" />

        {totalModels > 0 && loadedCount < totalModels && (
          <div className="pointer-events-none absolute left-3 top-3 rounded-lg border border-zinc-800 bg-[#0b1017]/90 px-3 py-1.5 font-mono text-[11px] text-sky-300 backdrop-blur-sm">
            Loading 3D meshes: {loadedCount}/{totalModels} ({pct}%)
          </div>
        )}

        {hoverEnu && editTool === "pick_floor" && Boolean(onCenterChange) && (
          <div className="pointer-events-none absolute right-3 top-3 rounded-lg border border-sky-500/50 bg-[#0b1017]/90 px-3 py-1.5 font-mono text-[11px] text-sky-200 backdrop-blur-sm">
            Click to place at ENU: E={hoverEnu.east_m.toFixed(2)}m · N={hoverEnu.north_m.toFixed(2)}m · U={hoverEnu.up_m.toFixed(2)}m
          </div>
        )}

        {pinEnu && (
          <div className="pointer-events-none absolute bottom-3 right-3 flex items-center gap-2 rounded-lg border border-rose-500/60 bg-[#0b1017]/95 px-2.5 py-1.5 font-mono text-[11px] tabular-nums text-slate-100 shadow-lg backdrop-blur-sm">
            <button
              type="button"
              onClick={copyPin}
              aria-label="Copy pinned coordinates"
              title={pinCopied ? "Copied!" : "Copy JSON coordinates [E, N, U]"}
              className="pointer-events-auto flex h-5 w-5 shrink-0 items-center justify-center rounded bg-red-600 text-white transition hover:bg-red-500"
            >
              {pinCopied ? (
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2.5}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-3 w-3"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-3 w-3"
                >
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
              )}
            </button>
            <span>
              <span className="text-rose-400">E</span> {pinEnu.east_m.toFixed(2)}
            </span>
            <span>
              <span className="text-emerald-400">N</span> {pinEnu.north_m.toFixed(2)}
            </span>
            <span>
              <span className="text-sky-400">U</span> {pinEnu.up_m.toFixed(2)}
            </span>
            <span className="text-slate-500">m</span>
            <button
              type="button"
              onClick={clearPin}
              aria-label="Remove pinned marker"
              title="Remove pin"
              className="pointer-events-auto ml-0.5 flex h-4 w-4 items-center justify-center rounded text-xs font-bold text-red-500 transition hover:bg-red-500/20 hover:text-red-400"
            >
              ✕
            </button>
          </div>
        )}

        <div className="pointer-events-none absolute bottom-3 left-3 flex flex-wrap items-center gap-2 rounded-lg border border-zinc-800/80 bg-[#0b1017]/85 px-2.5 py-1.5 font-mono text-[10px] text-slate-400 backdrop-blur-sm">
          <span>Left: Pan</span>
          <span>·</span>
          <span>Right/Middle: Rotate</span>
          <span>·</span>
          <span>Scroll: Zoom</span>
          <span>·</span>
          <span>Double-click: Focus</span>
          <span>·</span>
          <span>Shift+Click: Pin</span>
          {onCenterChange && (
            <>
              <span>·</span>
              <span className="text-orange-300">Alt+Click floor: Quick place</span>
            </>
          )}
          {hoverEnu && (
            <>
              <span>·</span>
              <span className="inline-flex items-center gap-1.5 tabular-nums text-slate-200">
                <span>
                  <span className="text-rose-400">E</span> {hoverEnu.east_m.toFixed(2)}
                </span>
                <span>
                  <span className="text-emerald-400">N</span> {hoverEnu.north_m.toFixed(2)}
                </span>
                <span>
                  <span className="text-sky-400">U</span> {hoverEnu.up_m.toFixed(2)}
                </span>
                <span className="text-slate-500">m</span>
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
