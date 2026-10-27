"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { accentColor, expertMorphWeights, resolveClip, type BotRole, type BotState } from "@/lib/avatars/playback";

const CROSSFADE_S = 0.2;

type Props = {
  role: BotRole;
  state: BotState;
  url: string;
  accent?: string;
  ttsAmplitude: number;
  onReady: () => void;
  onError: () => void;
};

function applyMorph(root: THREE.Object3D, name: string, weight: number) {
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    const dict = mesh.morphTargetDictionary;
    const influences = mesh.morphTargetInfluences;
    if (!dict || !influences || dict[name] === undefined) return;
    influences[dict[name]] = weight;
  });
}

function AvatarModel({ role, state, url, accent, ttsAmplitude, onReady, onError }: Props) {
  const root = useRef<THREE.Group>(null);
  const mixer = useRef<THREE.AnimationMixer | null>(null);
  const actions = useRef<Record<string, THREE.AnimationAction>>({});
  const current = useRef<string | null>(null);
  const blinkAt = useRef(3 + Math.random() * 3);
  const blink = useRef(0);
  const elapsed = useRef(0);
  const stateRef = useRef(state);
  const amplitudeRef = useRef(ttsAmplitude);
  stateRef.current = state;
  amplitudeRef.current = ttsAmplitude;

  useEffect(() => {
    const group = root.current;
    if (!group) return;
    let alive = true;
    const loader = new GLTFLoader();
    loader.load(
      url,
      (gltf) => {
        if (!alive) return;
        const box = new THREE.Box3().setFromObject(gltf.scene);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        gltf.scene.position.sub(center);
        const maxDim = Math.max(size.x, size.y, size.z) || 1;
        gltf.scene.scale.setScalar(1.7 / maxDim);
        const tint = accentColor(role, accent);
        gltf.scene.traverse((obj) => {
          const mesh = obj as THREE.Mesh;
          const materials = Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : [];
          for (const material of materials) {
            if (material.name === "accent" && "color" in material) {
              (material as THREE.MeshStandardMaterial).color.set(tint);
            }
          }
        });
        group.add(gltf.scene);
        const mix = new THREE.AnimationMixer(gltf.scene);
        mixer.current = mix;
        for (const clip of gltf.animations) {
          actions.current[clip.name] = mix.clipAction(clip);
        }
        mix.addEventListener("finished", (event) => {
          const action = (event as { action?: THREE.AnimationAction }).action;
          const name = action?.getClip().name;
          if (!name || name !== current.current) return;
          const { loop } = resolveClip(role, name as BotState);
          if (!loop) play("idle");
        });
        play(stateRef.current);
        onReady();
      },
      undefined,
      () => {
        if (alive) onError();
      },
    );
    return () => {
      alive = false;
      mixer.current?.stopAllAction();
      mixer.current = null;
      actions.current = {};
      current.current = null;
      group.clear();
    };
    // Reload only when the file or the specialist tint changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, role, accent]);

  function play(nextState: BotState) {
    const { clip, loop } = resolveClip(role, nextState);
    const next = actions.current[clip];
    if (!next || clip === current.current) return;
    const prev = current.current ? actions.current[current.current] : undefined;
    next.reset();
    next.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, loop ? Infinity : 1);
    next.clampWhenFinished = !loop;
    if (prev) next.crossFadeFrom(prev, CROSSFADE_S, true);
    next.play();
    current.current = clip;
  }

  useEffect(() => {
    play(state);
    // play closes over the latest mixer; state changes are the only trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  useFrame((_, delta) => {
    mixer.current?.update(delta);
    const model = root.current;
    if (!model || role !== "expert") return;
    elapsed.current += delta;
    if (elapsed.current >= blinkAt.current) {
      blink.current = 1;
      blinkAt.current = elapsed.current + 3 + Math.random() * 3;
    } else if (blink.current > 0) {
      blink.current = Math.max(0, blink.current - delta / 0.12);
    }
    const weights = expertMorphWeights(role, stateRef.current, amplitudeRef.current, blink.current);
    applyMorph(model, "blink", weights.blink);
    applyMorph(model, "browUp", weights.browUp);
    applyMorph(model, "browDown", weights.browDown);
    applyMorph(model, "smile", weights.smile);
    if (weights.mouthOpen > 0) applyMorph(model, "mouthOpen", weights.mouthOpen);
  });

  return <group ref={root} />;
}

function StudioLights() {
  const { gl, scene } = useThree();
  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = env;
    gl.toneMapping = THREE.ACESFilmicToneMapping;
    return () => {
      env.dispose();
      pmrem.dispose();
    };
  }, [gl, scene]);
  return <directionalLight position={[2, 3, 2]} intensity={1.15} />;
}

export function BotAvatarCanvas(props: Props) {
  return (
    <Canvas
      camera={{ position: [0, 0.15, 2.5], fov: 32 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      onCreated={({ gl }) => {
        gl.setClearColor(0x000000, 0);
        gl.domElement.addEventListener("webglcontextlost", (event) => {
          event.preventDefault();
          props.onError();
        });
      }}
    >
      <StudioLights />
      <AvatarModel {...props} />
    </Canvas>
  );
}
