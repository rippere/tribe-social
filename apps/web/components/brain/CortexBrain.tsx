'use client'

import { useEffect, useMemo, useState } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { useGLTF } from '@react-three/drei'
import * as THREE from 'three'

// Real cortex: fsaverage6 pial surface exported by research/export_cortex.py.
// TRIBE v2 predicts on fsaverage5 (20484 vertices); each fsaverage6 vertex
// carries the 3 fsaverage5 indices + weights it blends, so a frame of TRIBE
// output is uploaded once as a 144×144 float texture and read per vertex.

const N_VERTS = 20484
const TEX = 144 // 144² = 20736 ≥ 20484

export interface ActivityMeta {
  frames: number
  vertices: number
  hz: number
  source: 'tribe' | 'illustrative'
  label: string
  note: string
}

export interface Activity {
  meta: ActivityMeta
  data: Uint8Array // [frames, 20484], 128 = 0
}

// Mutable playback clock shared with the UI; mutated in the render loop so
// playback never re-renders React at 60 fps.
export interface CortexClock {
  t: number // seconds
  playing: boolean
  speed: number
}

export function useActivity(base = '/cortex'): Activity | null {
  const [activity, setActivity] = useState<Activity | null>(null)
  useEffect(() => {
    let alive = true
    Promise.all([
      fetch(`${base}/activity.json`).then(r => r.json() as Promise<ActivityMeta>),
      fetch(`${base}/activity.bin`).then(r => r.arrayBuffer()),
    ])
      .then(([meta, buf]) => {
        if (alive) setActivity({ meta, data: new Uint8Array(buf) })
      })
      .catch(err => console.error('cortex activity failed to load', err))
    return () => {
      alive = false
    }
  }, [base])
  return activity
}

const vertexShader = /* glsl */ `
  attribute float aSulc;
  attribute vec3 aIdx;
  attribute vec3 aW;
  uniform sampler2D uAct;
  varying float vAct;
  varying float vSulc;
  varying vec3 vNormal;
  varying vec3 vView;

  float act(float i) {
    int k = int(i + 0.5);
    return texelFetch(uAct, ivec2(k % ${TEX}, k / ${TEX}), 0).r;
  }

  void main() {
    vAct = dot(aW, vec3(act(aIdx.x), act(aIdx.y), act(aIdx.z)));
    vSulc = aSulc;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vView = -mv.xyz;
    gl_Position = projectionMatrix * mv;
  }
`

const fragmentShader = /* glsl */ `
  uniform float uThreshold;
  uniform float uIntensity;
  varying float vAct;
  varying float vSulc;
  varying vec3 vNormal;
  varying vec3 vView;

  vec3 ramp(float x) {
    vec3 deep = vec3(0.0, 0.34, 0.40);   // #005766
    vec3 cyan = vec3(0.29, 0.85, 0.93);  // #4AD8EC
    vec3 hot  = vec3(0.94, 0.99, 1.0);
    return x < 0.8 ? mix(deep, cyan, x / 0.8) : mix(cyan, hot, (x - 0.8) / 0.2 * 0.6);
  }

  void main() {
    vec3 n = normalize(vNormal);
    vec3 v = normalize(vView);
    vec3 l = normalize(vec3(0.35, 0.8, 0.6));
    float diffuse = 0.28 + 0.72 * max(dot(n, l), 0.0);
    float rim = pow(1.0 - max(dot(n, v), 0.0), 3.0);

    // Gyri light, sulci dark — the classic cortical-surface read.
    vec3 tissue = mix(vec3(0.36, 0.37, 0.40), vec3(0.11, 0.12, 0.14), vSulc);
    vec3 color = tissue * diffuse + rim * vec3(0.18, 0.22, 0.26);

    // Positive predicted response above threshold, cyan → white-hot.
    float a = clamp((vAct - uThreshold) / (1.0 - uThreshold), 0.0, 1.0) * uIntensity;
    vec3 glow = ramp(clamp(a, 0.0, 1.0));
    color = mix(color, glow * (0.55 + 0.45 * diffuse), smoothstep(0.0, 0.2, a));
    color += glow * a * 0.2;

    gl_FragColor = vec4(color, 1.0);
  }
`

interface Props {
  activity: Activity | null
  clock: CortexClock
  threshold?: number
  intensity?: number
  url?: string
}

export default function CortexBrain({
  activity,
  clock,
  threshold = 0.18,
  intensity = 1,
  url = '/cortex/cortex.glb',
}: Props) {
  const { scene } = useGLTF(url)

  const texture = useMemo(() => {
    const tex = new THREE.DataTexture(
      new Float32Array(TEX * TEX),
      TEX,
      TEX,
      THREE.RedFormat,
      THREE.FloatType,
    )
    tex.minFilter = THREE.NearestFilter
    tex.magFilter = THREE.NearestFilter
    tex.needsUpdate = true
    return tex
  }, [])

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader,
        fragmentShader,
        uniforms: {
          uAct: { value: texture },
          uThreshold: { value: threshold },
          uIntensity: { value: intensity },
        },
      }),
    // threshold/intensity are pushed through uniforms below, not a rebuild
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [texture],
  )

  // The node carries the KHR_mesh_quantization dequantisation transform once the
  // GLB has been through `gltf-transform meshopt`, so keep it with the geometry.
  const { geometry, node } = useMemo(() => {
    const node = (scene.getObjectByName('cortex') ?? scene.children[0]) as THREE.Mesh
    const g = node.geometry.clone()
    // GLTFLoader lower-cases custom attributes; give them shader-safe names.
    // _SULC/_FSA5_W may arrive as normalised uint16; WebGL hands the shader floats.
    g.setAttribute('aSulc', g.getAttribute('_sulc'))
    g.setAttribute('aIdx', g.getAttribute('_fsa5_idx'))
    g.setAttribute('aW', g.getAttribute('_fsa5_w'))
    g.computeVertexNormals()
    return { geometry: g, node }
  }, [scene])

  // On-demand canvases (reduced motion, paused hero) only redraw when asked.
  const invalidate = useThree(s => s.invalidate)
  useEffect(() => {
    material.uniforms.uThreshold.value = threshold
    material.uniforms.uIntensity.value = intensity
    invalidate()
  }, [material, threshold, intensity, invalidate])
  useEffect(() => {
    invalidate()
  }, [activity, invalidate])

  useEffect(() => () => {
    geometry.dispose()
    material.dispose()
    texture.dispose()
  }, [geometry, material, texture])

  useFrame((_, dt) => {
    if (!activity) return
    const { frames, hz } = activity.meta
    const duration = frames / hz
    // Clamp: a resumed or backgrounded tab must not jump the playhead.
    if (clock.playing) clock.t = (clock.t + Math.min(dt, 0.1) * clock.speed) % duration

    // Linear blend between the two bracketing TRIBE seconds.
    const f = clock.t * hz
    const f0 = Math.floor(f) % frames
    const f1 = (f0 + 1) % frames
    const a = f - Math.floor(f)
    const d = activity.data
    const out = texture.image.data as Float32Array
    const o0 = f0 * N_VERTS
    const o1 = f1 * N_VERTS
    for (let i = 0; i < N_VERTS; i++) {
      const v = d[o0 + i] + (d[o1 + i] - d[o0 + i]) * a
      out[i] = (v - 128) / 127
    }
    texture.needsUpdate = true
  })

  return (
    <mesh
      geometry={geometry}
      material={material}
      position={node.position}
      quaternion={node.quaternion}
      scale={node.scale}
    />
  )
}

useGLTF.preload('/cortex/cortex.glb')
