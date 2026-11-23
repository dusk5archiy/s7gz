"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { ColladaLoader } from "three/examples/jsm/loaders/ColladaLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { enuPoseToThreeQuaternion, enuToThreePosition } from "@/lib/three-math";
import {
  canUseThumbWorker,
  renderWorldThumbInWorker,
  withGeometryOnlyParam,
} from "@/lib/thumb-worker-pool";
import type { GeoPose, WorldSceneModel, WorldSceneResponse, WorldSceneVisual } from "@/lib/types";

const WORLD_THUMB_QUEUE: Array<() => Promise<void>> = [];
let worldQueueRunning = false;

let sharedRenderer: THREE.WebGLRenderer | null = null;
let sharedScene: THREE.Scene | null = null;
let sharedCamera: THREE.PerspectiveCamera | null = null;

// Skip loading 2K/4K image textures in tiny 240x150 thumbnails to keep memory near zero.
const THUMB_NO_TEX_MANAGER = new THREE.LoadingManager();
THUMB_NO_TEX_MANAGER.setURLModifier((url: string) => {
  if (/\.(png|jpe?g|webp|tga|bmp|gif)(\?.*)?$/i.test(url)) {
    return "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
  }
  return url;
});

interface BakedPart {
  geometry: THREE.BufferGeometry;
  localMatrix: THREE.Matrix4;
  colorHex: number | null;
}

const BAKED_TEMPLATE_CACHE = new Map<string, Promise<BakedPart[] | null>>();

function getSharedWorldThumbRig() {
  if (!sharedRenderer) {
    sharedRenderer = new THREE.WebGLRenderer({
      antialias: false,
      alpha: false,
      preserveDrawingBuffer: true,
      powerPreference: "low-power",
    });
    sharedRenderer.setPixelRatio(1);
    sharedRenderer.setSize(240, 150);
    sharedRenderer.toneMapping = THREE.NeutralToneMapping;
    sharedRenderer.toneMappingExposure = 1.15;

    sharedScene = new THREE.Scene();
    sharedScene.background = new THREE.Color(0x0b1017);
    const ambient = new THREE.AmbientLight(0xffffff, 0.7);
    const hemi = new THREE.HemisphereLight(0xf1f5f9, 0x334155, 0.65);
    const dir = new THREE.DirectionalLight(0xfffbeb, 0.9);
    dir.position.set(45, 80, 35);
    sharedScene.add(ambient, hemi, dir);

    sharedCamera = new THREE.PerspectiveCamera(50, 240 / 150, 0.5, 2000);
  }
  return {
    renderer: sharedRenderer,
    scene: sharedScene!,
    camera: sharedCamera!,
  };
}

function poseToMatrix(pose: GeoPose): THREE.Matrix4 {
  const pos = enuToThreePosition(pose.east_m, pose.north_m, pose.up_m);
  const quat = enuPoseToThreeQuaternion(pose);
  return new THREE.Matrix4().compose(pos, quat, new THREE.Vector3(1, 1, 1));
}

function disposeMaterialDeep(mat: THREE.Material | null | undefined): void {
  if (!mat) return;
  const rec = mat as unknown as Record<string, unknown>;
  for (const k of Object.keys(rec)) {
    if (rec[k] instanceof THREE.Texture) (rec[k] as THREE.Texture).dispose();
  }
  mat.dispose();
}

function bakeObjectParts(root: THREE.Object3D): BakedPart[] {
  const parts: BakedPart[] = [];
  root.updateMatrixWorld(true);
  root.traverse((obj) => {
    if (!(obj instanceof THREE.Mesh) || !obj.geometry) return;
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    let colorHex: number | null = null;
    const m0 = mats[0];
    if (m0 && "color" in m0 && m0.color instanceof THREE.Color) {
      colorHex = m0.color.getHex();
    }
    for (const m of mats) disposeMaterialDeep(m);
    if (!obj.geometry.boundingBox) obj.geometry.computeBoundingBox();
    parts.push({
      geometry: obj.geometry,
      localMatrix: obj.matrixWorld.clone(),
      colorHex,
    });
  });
  return parts;
}

function loadBakedTemplate(assetUrl: string, ext: string): Promise<BakedPart[] | null> {
  const cached = BAKED_TEMPLATE_CACHE.get(assetUrl);
  if (cached) return cached;
  const url = withGeometryOnlyParam(assetUrl);
  let p: Promise<BakedPart[] | null>;
  if (ext === ".dae") {
    p = new ColladaLoader(THUMB_NO_TEX_MANAGER)
      .loadAsync(url)
      .then((res) => {
        if (!res?.scene) return null;
        const remove: THREE.Object3D[] = [];
        res.scene.traverse((c) => {
          if (c instanceof THREE.Light || c instanceof THREE.Camera) remove.push(c);
        });
        for (const n of remove) n.removeFromParent();
        res.scene.rotation.set(-Math.PI / 2, 0, 0);
        return bakeObjectParts(res.scene);
      })
      .catch(() => null);
  } else if (ext === ".glb" || ext === ".gltf") {
    p = new GLTFLoader(THUMB_NO_TEX_MANAGER)
      .loadAsync(url)
      .then((res) => {
        if (!res?.scene) return null;
        const remove: THREE.Object3D[] = [];
        res.scene.traverse((c) => {
          if (c instanceof THREE.Light || c instanceof THREE.Camera) remove.push(c);
        });
        for (const n of remove) n.removeFromParent();
        res.scene.rotation.set(-Math.PI / 2, 0, 0);
        return bakeObjectParts(res.scene);
      })
      .catch(() => null);
  } else if (ext === ".stl") {
    p = new STLLoader()
      .loadAsync(url)
      .then((geom) => {
        if (!geom.boundingBox) geom.computeBoundingBox();
        return [
          {
            geometry: geom,
            localMatrix: new THREE.Matrix4().makeRotationX(-Math.PI / 2),
            colorHex: null,
          },
        ];
      })
      .catch(() => null);
  } else if (ext === ".obj") {
    p = new OBJLoader(THUMB_NO_TEX_MANAGER)
      .loadAsync(url)
      .then((obj) => {
        obj.rotation.x = -Math.PI / 2;
        return bakeObjectParts(obj);
      })
      .catch(() => null);
  } else {
    p = Promise.resolve(null);
  }
  BAKED_TEMPLATE_CACHE.set(assetUrl, p);
  return p;
}

function visualLocalMatrix(vis: WorldSceneVisual): THREE.Matrix4 {
  const m = poseToMatrix(vis.link_pose).multiply(poseToMatrix(vis.visual_pose));
  const sc = vis.geometry.scale;
  if (sc && sc.length === 3) {
    m.multiply(new THREE.Matrix4().makeScale(sc[0], sc[2], sc[1]));
  }
  return m;
}

async function clearTemplateCaches(): Promise<void> {
  for (const p of BAKED_TEMPLATE_CACHE.values()) {
    const parts = await p.catch(() => null);
    if (parts) {
      for (const part of parts) part.geometry.dispose();
    }
  }
  BAKED_TEMPLATE_CACHE.clear();
}

async function renderWorldOnMainThread(withVis: WorldSceneModel[]): Promise<string | null> {
  const uniqueSpecs = new Map<string, { assetUrl: string; ext: string }>();
  for (const m of withVis) {
    for (const v of m.visuals) {
      const g = v.geometry;
      if (g.type === "mesh" && g.asset_url && g.ext && !uniqueSpecs.has(g.asset_url)) {
        uniqueSpecs.set(g.asset_url, { assetUrl: g.asset_url, ext: g.ext });
      }
    }
  }

  await Promise.all(
    Array.from(uniqueSpecs.values()).map((s) => loadBakedTemplate(s.assetUrl, s.ext)),
  );

  const instanceGroups = new Map<
    string,
    { assetUrl: string; fallbackHex: number; placements: Array<{ mat: THREE.Matrix4; isGround: boolean }> }
  >();
  const ownedPrimitives: Array<{ mesh: THREE.Mesh; isGround: boolean }> = [];
  const ownedMaterials: THREE.Material[] = [];

  for (const m of withVis) {
    const isGround = m.name === "ground_plane";
    const modelMat = poseToMatrix(m.pose);
    const fallbackHex = m.is_base_station ? 0xf59e0b : 0x64748b;
    for (const vis of m.visuals) {
      const g = vis.geometry;
      if (g.type === "mesh" && g.asset_url) {
        const placement = modelMat.clone().multiply(visualLocalMatrix(vis));
        const key = `${g.asset_url}::${fallbackHex}`;
        let grp = instanceGroups.get(key);
        if (!grp) {
          grp = { assetUrl: g.asset_url, fallbackHex, placements: [] };
          instanceGroups.set(key, grp);
        }
        grp.placements.push({ mat: placement, isGround });
      } else {
        let geom: THREE.BufferGeometry | null = null;
        if (g.type === "box" && g.size) {
          geom = new THREE.BoxGeometry(g.size[0], g.size[2], g.size[1]);
        } else if (g.type === "cylinder" && g.radius && g.length) {
          geom = new THREE.CylinderGeometry(g.radius, g.radius, g.length, 12);
        } else if (g.type === "sphere" && g.radius) {
          geom = new THREE.SphereGeometry(g.radius, 12, 8);
        }
        if (!geom) continue;
        if (!geom.boundingBox) geom.computeBoundingBox();
        const rgb = vis.diffuse_rgba;
        const primColor = rgb
          ? new THREE.Color(rgb[0], rgb[1], rgb[2]).getHex()
          : fallbackHex;
        const mat = new THREE.MeshLambertMaterial({ color: primColor });
        ownedMaterials.push(mat);
        const mesh = new THREE.Mesh(geom, mat);
        mesh.matrixAutoUpdate = false;
        mesh.matrix.copy(
          modelMat
            .clone()
            .multiply(poseToMatrix(vis.link_pose))
            .multiply(poseToMatrix(vis.visual_pose)),
        );
        ownedPrimitives.push({ mesh, isGround });
      }
    }
  }

  const root = new THREE.Group();
  const worldBox = new THREE.Box3();
  const focusBox = new THREE.Box3();
  const tmpBox = new THREE.Box3();
  const tmpMat = new THREE.Matrix4();

  try {
    for (const grp of instanceGroups.values()) {
      const parts = await BAKED_TEMPLATE_CACHE.get(grp.assetUrl);
      if (!parts || parts.length === 0) continue;
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

    for (const { mesh: prim, isGround } of ownedPrimitives) {
      root.add(prim);
      if (prim.geometry.boundingBox) {
        tmpBox.copy(prim.geometry.boundingBox).applyMatrix4(prim.matrix);
        worldBox.union(tmpBox);
        if (!isGround) focusBox.union(tmpBox);
      }
    }

    if (root.children.length === 0 || worldBox.isEmpty()) return null;

    const { renderer, scene, camera } = getSharedWorldThumbRig();
    scene.add(root);
    const frameBox = focusBox.isEmpty() ? worldBox : focusBox;
    const center = frameBox.getCenter(new THREE.Vector3());
    const size = frameBox.getSize(new THREE.Vector3());
    const dist = Math.min(Math.max(size.length() * 0.65, 2.5), 280);
    camera.position.set(
      center.x - dist * 0.65,
      center.y + dist * 0.55,
      center.z + dist * 0.65,
    );
    camera.lookAt(center);
    camera.updateProjectionMatrix();
    renderer.render(scene, camera);
    const dataUrl = renderer.domElement.toDataURL("image/jpeg", 0.85);
    scene.remove(root);
    renderer.renderLists.dispose();
    return dataUrl;
  } finally {
    for (const { mesh: prim } of ownedPrimitives) prim.geometry.dispose();
    for (const mat of ownedMaterials) mat.dispose();
  }
}

async function processWorldQueue() {
  if (worldQueueRunning) return;
  worldQueueRunning = true;
  try {
    while (WORLD_THUMB_QUEUE.length > 0) {
      const task = WORLD_THUMB_QUEUE.shift();
      if (task) {
        await task().catch(() => {});
      }
    }
  } finally {
    await clearTemplateCaches();
    worldQueueRunning = false;
  }
}

export function WorldThumbnail({
  relativePath,
  scope = "patched",
  thumbnailUrl,
}: {
  relativePath: string;
  scope?: "source" | "patched";
  thumbnailUrl?: string | null;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);
  const [nativeFailed, setNativeFailed] = useState(false);
  const [renderedSrc, setRenderedSrc] = useState<string | null>(null);
  const [empty, setEmpty] = useState(false);

  const directThumb = !nativeFailed && thumbnailUrl ? thumbnailUrl : null;

  useEffect(() => {
    if (directThumb) return;
    const el = containerRef.current;
    if (!el || visible) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "240px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [visible, directThumb]);

  useEffect(() => {
    if (directThumb || !visible) return;
    let cancelled = false;
    let createdObjectUrl: string | null = null;

    const run = async () => {
      const res = await fetch(
        `/api/worlds/scene?scope=${scope}&relative_path=${encodeURIComponent(relativePath)}`,
      );
      if (cancelled) return;
      if (!res.ok) {
        setEmpty(true);
        return;
      }
      const sceneData = (await res.json()) as WorldSceneResponse;
      if (cancelled) return;

      if (sceneData.thumbnail_url && !nativeFailed) {
        setRenderedSrc(sceneData.thumbnail_url);
        return;
      }

      const withVis = sceneData.models.filter((m) => m.visuals.length > 0);
      if (withVis.length === 0) {
        setEmpty(true);
        return;
      }

      const allVisuals = withVis.flatMap((m) => m.visuals);
      if (canUseThumbWorker(allVisuals)) {
        try {
          const workerUrl = await renderWorldThumbInWorker(withVis, 240, 150);
          if (cancelled) {
            if (workerUrl) URL.revokeObjectURL(workerUrl);
            return;
          }
          if (workerUrl) {
            createdObjectUrl = workerUrl;
            setRenderedSrc(workerUrl);
            return;
          }
          setEmpty(true);
          return;
        } catch {
          // Fall through to main-thread renderer below.
        }
      }

      WORLD_THUMB_QUEUE.push(async () => {
        if (cancelled) return;
        const url = await renderWorldOnMainThread(withVis);
        if (cancelled) return;
        if (url) {
          setRenderedSrc(url);
        } else {
          setEmpty(true);
        }
      });
      void processWorldQueue();
    };

    void run().catch(() => {
      if (!cancelled) setEmpty(true);
    });

    return () => {
      cancelled = true;
      if (createdObjectUrl) URL.revokeObjectURL(createdObjectUrl);
    };
  }, [visible, relativePath, scope, directThumb, nativeFailed]);

  const activeSrc = directThumb ?? renderedSrc;

  return (
    <div
      ref={containerRef}
      className="relative aspect-[16/10] w-full overflow-hidden rounded-t-lg bg-[#0b1017]"
    >
      {activeSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={activeSrc}
          alt={`${relativePath} 3D world preview`}
          loading="lazy"
          onError={() => {
            if (directThumb) {
              setNativeFailed(true);
              setVisible(true);
            } else {
              setRenderedSrc(null);
              setEmpty(true);
            }
          }}
          className="h-full w-full object-cover"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center font-mono text-[11px] text-zinc-500">
          {empty ? "No 3D mesh" : "Rendering 3D..."}
        </div>
      )}
    </div>
  );
}
