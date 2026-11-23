"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { ColladaLoader } from "three/examples/jsm/loaders/ColladaLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { applyEnuPoseToObject } from "@/lib/three-math";
import {
  canUseThumbWorker,
  renderModelThumbInWorker,
  withGeometryOnlyParam,
} from "@/lib/thumb-worker-pool";
import type { WorldSceneVisual } from "@/lib/types";

const THUMB_CONCURRENCY = 4;
const THUMB_QUEUE: Array<() => Promise<void>> = [];
let activeWorkers = 0;

let sharedRenderer: THREE.WebGLRenderer | null = null;
let sharedScene: THREE.Scene | null = null;
let sharedCamera: THREE.PerspectiveCamera | null = null;

const NO_TEX_MANAGER = new THREE.LoadingManager();
NO_TEX_MANAGER.setURLModifier((url: string) => {
  if (/\.(png|jpe?g|webp|tga|bmp|gif)(\?.*)?$/i.test(url)) {
    return "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
  }
  return url;
});

function getSharedRig() {
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
    sharedScene.add(
      new THREE.AmbientLight(0xffffff, 0.7),
      new THREE.HemisphereLight(0xf1f5f9, 0x334155, 0.65),
    );
    const dir = new THREE.DirectionalLight(0xfffbeb, 0.9);
    dir.position.set(20, 35, 20);
    sharedScene.add(dir);

    sharedCamera = new THREE.PerspectiveCamera(45, 240 / 150, 0.05, 800);
  }
  return { renderer: sharedRenderer, scene: sharedScene!, camera: sharedCamera! };
}

function toLightMaterial(root: THREE.Object3D): void {
  root.traverse((obj) => {
    if (!(obj instanceof THREE.Mesh)) return;
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    const next = mats.map((mat) => {
      let colorHex = 0x64748b;
      if (mat && "color" in mat && mat.color instanceof THREE.Color) {
        colorHex = mat.color.getHex();
      }
      if (mat) {
        const rec = mat as unknown as Record<string, unknown>;
        for (const k of Object.keys(rec)) {
          if (rec[k] instanceof THREE.Texture) (rec[k] as THREE.Texture).dispose();
        }
        mat.dispose();
      }
      return new THREE.MeshLambertMaterial({ color: colorHex });
    });
    obj.material = Array.isArray(obj.material) ? next : next[0];
  });
}

function disposeDeep(root: THREE.Object3D): void {
  root.traverse((obj) => {
    if (obj instanceof THREE.Mesh) {
      obj.geometry.dispose();
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      for (const m of mats) if (m) m.dispose();
    }
  });
}

async function buildLightVisual(vis: WorldSceneVisual): Promise<THREE.Object3D | null> {
  const linkObj = new THREE.Group();
  const visObj = new THREE.Group();
  applyEnuPoseToObject(linkObj, vis.link_pose);
  applyEnuPoseToObject(visObj, vis.visual_pose);
  linkObj.add(visObj);

  const g = vis.geometry;
  if (g.type === "mesh" && g.asset_url && g.ext) {
    const geomUrl = withGeometryOnlyParam(g.asset_url);
    if (g.ext === ".dae") {
      try {
        const res = await new ColladaLoader(NO_TEX_MANAGER).loadAsync(geomUrl);
        if (res?.scene) {
          const remove: THREE.Object3D[] = [];
          res.scene.traverse((c) => {
            if (c instanceof THREE.Light || c instanceof THREE.Camera) remove.push(c);
          });
          for (const n of remove) n.removeFromParent();
          res.scene.rotation.set(-Math.PI / 2, 0, 0);
          toLightMaterial(res.scene);
          const scaleGroup = new THREE.Group();
          if (g.scale && g.scale.length === 3) {
            scaleGroup.scale.set(g.scale[0], g.scale[2], g.scale[1]);
          }
          scaleGroup.add(res.scene);
          visObj.add(scaleGroup);
          return linkObj;
        }
      } catch {
        return null;
      }
    } else if (g.ext === ".glb" || g.ext === ".gltf") {
      try {
        const res = await new GLTFLoader(NO_TEX_MANAGER).loadAsync(geomUrl);
        if (res?.scene) {
          const remove: THREE.Object3D[] = [];
          res.scene.traverse((c) => {
            if (c instanceof THREE.Light || c instanceof THREE.Camera) remove.push(c);
          });
          for (const n of remove) n.removeFromParent();
          res.scene.rotation.set(-Math.PI / 2, 0, 0);
          toLightMaterial(res.scene);
          const scaleGroup = new THREE.Group();
          if (g.scale && g.scale.length === 3) {
            scaleGroup.scale.set(g.scale[0], g.scale[2], g.scale[1]);
          }
          scaleGroup.add(res.scene);
          visObj.add(scaleGroup);
          return linkObj;
        }
      } catch {
        return null;
      }
    } else if (g.ext === ".stl") {
      try {
        const geom = await new STLLoader().loadAsync(geomUrl);
        const mesh = new THREE.Mesh(geom, new THREE.MeshLambertMaterial({ color: 0x64748b }));
        mesh.rotation.x = -Math.PI / 2;
        if (g.scale && g.scale.length === 3) mesh.scale.set(g.scale[0], g.scale[1], g.scale[2]);
        visObj.add(mesh);
        return linkObj;
      } catch {
        return null;
      }
    } else if (g.ext === ".obj") {
      try {
        const obj = await new OBJLoader(NO_TEX_MANAGER).loadAsync(geomUrl);
        obj.rotation.x = -Math.PI / 2;
        toLightMaterial(obj);
        if (g.scale && g.scale.length === 3) obj.scale.set(g.scale[0], g.scale[1], g.scale[2]);
        visObj.add(obj);
        return linkObj;
      } catch {
        return null;
      }
    }
  }

  let geom: THREE.BufferGeometry | null = null;
  if (g.type === "box" && g.size) {
    geom = new THREE.BoxGeometry(g.size[0], g.size[2], g.size[1]);
  } else if (g.type === "cylinder" && g.radius && g.length) {
    geom = new THREE.CylinderGeometry(g.radius, g.radius, g.length, 12);
  } else if (g.type === "sphere" && g.radius) {
    geom = new THREE.SphereGeometry(g.radius, 12, 8);
  }
  if (!geom) return null;
  visObj.add(new THREE.Mesh(geom, new THREE.MeshLambertMaterial({ color: 0x64748b })));
  return linkObj;
}

function pumpQueue() {
  while (activeWorkers < THUMB_CONCURRENCY && THUMB_QUEUE.length > 0) {
    const task = THUMB_QUEUE.shift();
    if (!task) break;
    activeWorkers += 1;
    void task()
      .catch(() => {})
      .finally(() => {
        activeWorkers -= 1;
        pumpQueue();
      });
  }
}

export function FuelModelThumbnail({
  relativePath,
  scope = "source",
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
    const encoded = relativePath.split("/").map(encodeURIComponent).join("/");

    const run = async () => {
      const res = await fetch(`/api/models/visuals/${encoded}?scope=${scope}`);
      if (cancelled) return;
      if (!res.ok) {
        setEmpty(true);
        return;
      }
      const data = (await res.json()) as {
        thumbnail_url?: string | null;
        visuals?: WorldSceneVisual[];
      };
      if (cancelled) return;

      if (data.thumbnail_url && !nativeFailed) {
        setRenderedSrc(data.thumbnail_url);
        return;
      }

      const visuals = data.visuals ?? [];
      if (visuals.length === 0) {
        setEmpty(true);
        return;
      }

      // Deduplicate identical asset_url visuals (e.g. SubT <submesh> splits)
      const seen = new Set<string>();
      const uniqueVis = visuals.filter((v) => {
        const key = v.geometry.asset_url ?? JSON.stringify(v.geometry);
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });

      if (canUseThumbWorker(uniqueVis)) {
        try {
          const workerUrl = await renderModelThumbInWorker(uniqueVis, 240, 150);
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

      THUMB_QUEUE.push(async () => {
        if (cancelled) return;
        const root = new THREE.Group();
        try {
          const built = await Promise.all(uniqueVis.map((v) => buildLightVisual(v)));
          if (cancelled) return;
          for (const obj of built) if (obj) root.add(obj);
          if (root.children.length === 0) {
            setEmpty(true);
            return;
          }
          const { renderer, scene, camera } = getSharedRig();
          scene.add(root);
          root.updateMatrixWorld(true);
          const box = new THREE.Box3().setFromObject(root);
          if (!box.isEmpty()) {
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const radius = Math.max(size.length() * 0.5, 0.25);
            const dist = Math.min(radius * 2.25, 250);
            camera.position.set(
              center.x - dist * 0.72,
              center.y + dist * 0.52,
              center.z + dist * 0.72,
            );
            camera.lookAt(center);
            camera.updateProjectionMatrix();
            renderer.render(scene, camera);
            const url = renderer.domElement.toDataURL("image/jpeg", 0.85);
            if (!cancelled) setRenderedSrc(url);
          } else if (!cancelled) {
            setEmpty(true);
          }
          scene.remove(root);
          renderer.renderLists.dispose();
        } finally {
          disposeDeep(root);
        }
      });
      pumpQueue();
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
          alt={`${relativePath} 3D model preview`}
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
          {empty ? "No 3D mesh" : visible ? "Rendering 3D..." : "Queued..."}
        </div>
      )}
    </div>
  );
}
